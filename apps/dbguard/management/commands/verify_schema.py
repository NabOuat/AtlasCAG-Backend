"""Vérifie que le schéma réel de la base `default` correspond aux modèles Django, et corrige
automatiquement les écarts sûrs (qui ne peuvent pas faire perdre de données).

Contexte : on a découvert que des tables (`dtv`, `vague_envoi`) étaient marquées comme migrées
dans `django_migrations` sans que le DDL correspondant ait jamais été appliqué, et que la table
`dossier` portait des colonnes orphelines `NOT NULL` et des contraintes `CHECK` obsolètes
héritées d'un ancien schéma — bloquant purement et simplement toute création de ligne. Cette
commande automatise la détection (et, pour les cas sans risque de perte de données, la
correction) de ce type de dérive à chaque démarrage de l'application.

Règle de sécurité non négociable, même en mode `--fix` : **on ne supprime jamais de données**.
- Une colonne orpheline (absente du modèle) `NOT NULL` sans défaut n'est assouplie
  (`DROP NOT NULL`) que si elle ne contient aucune valeur non nulle sur toutes les lignes
  existantes. Si des lignes portent une vraie valeur, on se contente de journaliser un
  avertissement — jamais de suppression de colonne, jamais de perte de valeur.
- Une contrainte CHECK liée aux `choices` d'un champ n'est resynchronisée que si aucune ligne
  existante ne violerait la nouvelle contrainte.

Usage :
    python manage.py verify_schema            # rapport seul, aucune modification
    python manage.py verify_schema --fix       # applique les corrections sûres
Appelée automatiquement avec --fix au démarrage de l'application (apps/dbguard/apps.py),
protégée par un verrou Postgres pour éviter les courses entre plusieurs process/workers.
"""

import logging
import re

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger('dbguard')

ADVISORY_LOCK_KEY = 875_219_001  # clé arbitraire, propre à cette commande


class Command(BaseCommand):
    help = "Vérifie (et corrige en mode --fix) les écarts entre les modèles Django et le schéma réel."

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Applique les corrections sûres (sinon, rapport seul).')

    def handle(self, *args, **options):
        fix = options['fix']

        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK_KEY])
            got_lock = cursor.fetchone()[0]
        if not got_lock:
            self._log("Un autre process vérifie déjà le schéma — vérification ignorée pour cette fois.")
            return

        try:
            summary = {'fixed': 0, 'warnings': 0, 'ok': 0}
            for model in django_apps.get_models():
                if model._meta.app_label in ('contenttypes', 'auth', 'sessions', 'admin', 'token_blacklist'):
                    continue  # tables gérées entièrement par Django/tiers, pas de dérive attendue
                self._check_model(model, fix, summary)

            self._log(
                f"Vérification du schéma terminée — {summary['fixed']} correction(s) appliquée(s), "
                f"{summary['warnings']} avertissement(s), {summary['ok']} table(s) conformes."
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK_KEY])

    # ── Helpers ──────────────────────────────────────────────────────────

    def _log(self, message, level='info'):
        getattr(logger, level)(message)
        style = self.style.SUCCESS if level == 'info' else self.style.WARNING
        self.stdout.write(style(message))

    def _check_model(self, model, fix, summary):
        table = model._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s",
                [table],
            )
            db_columns = {row[0]: {'nullable': row[1] == 'YES', 'default': row[2]} for row in cursor.fetchall()}

        if not db_columns:
            self._log(f"[{table}] table absente — devrait être créée par `migrate` (modèle {model.__name__}).", 'warning')
            summary['warnings'] += 1
            return

        model_fields = {f.column: f for f in model._meta.concrete_fields}
        touched = False

        # 1. Colonnes orphelines NOT NULL sans défaut (absentes du modèle actuel)
        orphan_columns = set(db_columns) - set(model_fields)
        for col in sorted(orphan_columns):
            info = db_columns[col]
            if info['nullable'] or info['default'] is not None:
                continue  # nullable ou avec défaut : n'empêche aucune insertion, rien à faire
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NOT NULL')
                non_null_count = cursor.fetchone()[0]
            if non_null_count > 0:
                self._log(
                    f"[{table}.{col}] colonne orpheline NOT NULL contenant {non_null_count} valeur(s) "
                    f"réelle(s) — laissée telle quelle (aucune suppression de donnée automatique). "
                    f"À traiter manuellement.",
                    'warning',
                )
                summary['warnings'] += 1
                continue
            if fix:
                with connection.cursor() as cursor:
                    cursor.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" DROP NOT NULL')
                self._log(f"[{table}.{col}] colonne orpheline vide rendue nullable (NOT NULL levé).")
                summary['fixed'] += 1
                touched = True
            else:
                self._log(f"[{table}.{col}] colonne orpheline NOT NULL vide — corrigible avec --fix.", 'warning')
                summary['warnings'] += 1

        # 2. Contraintes CHECK désynchronisées des `choices` du modèle
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = %s::regclass AND contype = 'c'",
                [table],
            )
            check_constraints = cursor.fetchall()

        for field in model._meta.concrete_fields:
            if not getattr(field, 'choices', None):
                continue
            expected = {str(c[0]) for c in field.choices}
            column_pattern = re.compile(
                r'(?<![A-Za-z0-9_"])"?' + re.escape(field.column) + r'"?(?![A-Za-z0-9_])'
            )
            for conname, condef in check_constraints:
                # Correspondance sur le nom de colonne complet (limites de mot), jamais une
                # simple sous-chaîne — sinon un champ "statut" matcherait aussi la contrainte
                # d'un champ "statut_cf" (bug réel rencontré : substring 'statut' présent dans
                # 'statut_cf', qui écrasait la mauvaise contrainte).
                if not column_pattern.search(condef):
                    continue
                found = set(re.findall(r"'([^']*)'::character varying", condef))
                if not found:
                    found = set(re.findall(r"'([^']+)'", condef))
                if not found or found == expected:
                    continue  # pas une contrainte d'énumération sur ce champ, ou déjà à jour

                with connection.cursor() as cursor:
                    if field.null:
                        cursor.execute(
                            f'SELECT COUNT(*) FROM "{table}" WHERE "{field.column}" IS NOT NULL '
                            f'AND "{field.column}"::text NOT IN %s',
                            [tuple(expected) or ('',)],
                        )
                    else:
                        cursor.execute(
                            f'SELECT COUNT(*) FROM "{table}" WHERE "{field.column}"::text NOT IN %s',
                            [tuple(expected) or ('',)],
                        )
                    violating = cursor.fetchone()[0]

                if violating > 0:
                    self._log(
                        f"[{table}.{field.column}] contrainte CHECK '{conname}' obsolète "
                        f"({sorted(found)} vs choix actuels {sorted(expected)}), mais {violating} ligne(s) "
                        f"violeraient la nouvelle contrainte — laissée telle quelle. À traiter manuellement.",
                        'warning',
                    )
                    summary['warnings'] += 1
                    continue

                values_sql = ', '.join(f"'{v}'" for v in sorted(expected))
                null_clause = f'"{field.column}" IS NULL OR ' if field.null else ''
                new_def = f'CHECK (({null_clause}("{field.column}")::text = ANY (ARRAY[{values_sql}]::text[])))'

                if fix:
                    with connection.cursor() as cursor:
                        cursor.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{conname}"')
                        cursor.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{conname}" {new_def}')
                    self._log(f"[{table}.{field.column}] contrainte CHECK '{conname}' resynchronisée avec les choix actuels.")
                    summary['fixed'] += 1
                    touched = True
                else:
                    self._log(
                        f"[{table}.{field.column}] contrainte CHECK '{conname}' obsolète "
                        f"({sorted(found)} vs {sorted(expected)}) — corrigible avec --fix.",
                        'warning',
                    )
                    summary['warnings'] += 1

        if not touched and not orphan_columns:
            summary['ok'] += 1
