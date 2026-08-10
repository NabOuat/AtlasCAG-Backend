"""Crée, une fois par schéma (sous-préfecture) et par zone, les couches PostGIS manquantes
nécessaires au workflow de publicité (CF – Approuvée, CF – Validée). Idempotent : peut être
relancée sans risque (CREATE TABLE IF NOT EXISTS ... LIKE ...).

Nécessite des privilèges DDL sur les bases OVH `cavally_spatial`/`worodougou_spatial` — à
exécuter manuellement une fois avant que les actions « Approuver »/« Valider » du workflow de
publicité (apps/publicite) ne puissent fonctionner. Sans ces tables, le service de migration
échoue proprement (MigrationError explicite) sans jamais modifier de données.

Usage : python manage.py create_publicite_layers [--zone cavally|worodougou] [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import connections

from apps.geo.db import VALID_ZONES, db_alias, discover_schema_tables, table_exists

# Table de référence dont la structure (colonnes + géométrie) est clonée pour créer les
# nouvelles couches — cf_poly_parcelle_Def est la table CF la plus complète/représentative.
REFERENCE_TABLE = 'cf_poly_parcelle_Def'
NEW_TABLES = ['cf_parcelle_approuvee', 'cf_parcelle_validee']


class Command(BaseCommand):
    help = "Crée les couches PostGIS cf_parcelle_approuvee/validee manquantes (une par sous-préfecture)."

    def add_arguments(self, parser):
        parser.add_argument('--zone', choices=sorted(VALID_ZONES), default=None,
                             help='Limiter à une zone (défaut : les deux).')
        parser.add_argument('--dry-run', action='store_true',
                             help='Affiche les instructions SQL sans les exécuter.')

    def handle(self, *args, **options):
        zones = [options['zone']] if options['zone'] else sorted(VALID_ZONES)
        dry_run = options['dry_run']

        for zone in zones:
            alias = db_alias(zone)
            self.stdout.write(self.style.MIGRATE_HEADING(f'== Zone {zone} =='))
            with connections[alias].cursor() as cursor:
                if not table_exists(cursor, 'public', REFERENCE_TABLE):
                    self.stderr.write(self.style.ERROR(
                        f"Table de référence 'public.{REFERENCE_TABLE}' absente sur {zone} — abandon."
                    ))
                    continue

                # Une sous-préfecture = un schéma non-système. On les découvre via les tables
                # CF déjà scopées par sous-préfecture (levé/provisoire/en_publicite/...).
                schemas = {
                    schema for schema, _ in discover_schema_tables(
                        cursor,
                        ['cf_poly_parcelle_leve', 'cf_poly_parcelle_Prov', 'cf_parcelle_en_publicite'],
                    )
                }

                if not schemas:
                    self.stdout.write(self.style.WARNING(f'Aucun schéma sous-préfecture découvert pour {zone}.'))
                    continue

                for schema in sorted(schemas):
                    for new_table in NEW_TABLES:
                        if table_exists(cursor, schema, new_table):
                            self.stdout.write(f'  [déjà présente] {schema}.{new_table}')
                            continue
                        sql = (
                            f'CREATE TABLE "{schema}"."{new_table}" '
                            f'(LIKE "public"."{REFERENCE_TABLE}" INCLUDING ALL)'
                        )
                        if dry_run:
                            self.stdout.write(f'  [dry-run] {sql}')
                            continue
                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f'  [créée] {schema}.{new_table}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run : aucune table n\'a été créée.'))
