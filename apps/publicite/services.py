"""Service de migration des parcelles CF entre couches PostGIS, piloté par le workflow de
publicité (apps/publicite/views.py). Toute transition de statut sur un `Dossier` déclenche
une migration physique de la parcelle correspondante (identifiée uniquement par `NUM_DEMAND`,
comme exigé par le cahier des charges) d'une table PostGIS vers une autre.

Stratégie de cohérence — « best-effort + compensation » (validée avec le métier) : la base
spatiale (`<zone>_spatial`) et la base métier (`default`) sont deux bases Postgres
physiquement séparées, donc aucune transaction atomique unique n'est possible entre les deux.
On isole donc deux transactions :
1. Sur la base spatiale : DELETE (couche source) + INSERT (couche cible), atomique.
2. Sur la base métier : mise à jour de `Dossier.statut_cf` + écriture de l'historique.
Si l'étape 1 échoue, aucune donnée n'est modifiée (rollback automatique) et l'étape 2 n'a
jamais lieu. Si l'étape 1 réussit mais l'étape 2 échoue (cas résiduel, rare), l'incohérence
est journalisée dans `HistoriqueMigrationCouche` pour réconciliation manuelle.
"""

from django.db import connections, transaction

from apps.geo.db import db_alias, discover_schema_tables, non_geom_columns, table_exists
from .models import HistoriqueMigrationCouche


class MigrationError(Exception):
    """Levée quand la migration spatiale ne peut pas être menée à bien (parcelle introuvable,
    couche cible inexistante, échec SQL). Ne modifie jamais `Dossier.statut_cf`."""


def _find_source_row(cursor, table_name, num_demand):
    """Cherche la ligne `NUM_DEMAND` dans toutes les occurrences de `table_name`
    (tous schémas). Retourne (schema, colonnes_non_geom, ligne_complète_avec_geom) ou None."""
    for schema, table in discover_schema_tables(cursor, [table_name]):
        avail = non_geom_columns(cursor, schema, table)
        if 'NUM_DEMAND' not in avail:
            continue
        col_sql = ', '.join(f'"{c}"' for c in avail)
        cursor.execute(
            f'SELECT {col_sql}, geom FROM "{schema}"."{table}" WHERE "NUM_DEMAND" = %s',
            [num_demand],
        )
        row = cursor.fetchone()
        if row:
            return schema, avail, row
    return None


def _resolve_target_schema(cursor, source_schema, table_cible, avail_cols, row):
    """Détermine le schéma (sous-préfecture) où insérer la ligne dans `table_cible`.

    - Si la table source est déjà scopée par sous-préfecture (schema != 'public'), la cible
      vit dans le même schéma (cas des transitions En publicité → Approuvée/Rejetée →
      Validée, qui restent toutes dans les tables par sous-préfecture).
    - Si la source est la table centralisée `public` (cas de `cf_poly_parcelle_Def`, qui
      agrège toutes les sous-préfectures d'une zone), on retrouve le schéma cible en
      comparant `NOM_SSPREF` de la ligne au nom des schémas candidats portant déjà une table
      `table_cible` ou une table CF par sous-préfecture de référence. À vérifier/affiner une
      fois la convention de nommage réelle des schémas confirmée côté base OVH.
    """
    if source_schema != 'public':
        return source_schema

    if 'NOM_SSPREF' not in avail_cols:
        raise MigrationError(
            "Impossible de déterminer le schéma cible : colonne NOM_SSPREF absente de la "
            "table source centralisée."
        )
    sspref = row[avail_cols.index('NOM_SSPREF')]
    if not sspref:
        raise MigrationError("Valeur NOM_SSPREF vide pour cette parcelle — migration impossible.")

    candidate_schemas = {s for s, _ in discover_schema_tables(cursor, [table_cible])}
    normalized = str(sspref).strip().lower().replace(' ', '_')
    for schema in candidate_schemas:
        if schema.strip().lower().replace(' ', '_') == normalized:
            return schema

    raise MigrationError(
        f"Aucun schéma correspondant à la sous-préfecture {sspref!r} trouvé parmi les schémas "
        f"portant la table {table_cible!r} — vérifier la convention de nommage des schémas."
    )


def migrer_parcelle(*, zone, dossier, table_source, table_cible, nouveau_statut, user):
    """Migre la parcelle `dossier.num_demand` de `table_source` vers `table_cible` sur la
    base spatiale de `zone`, puis met à jour `dossier.statut_cf`. Lève `MigrationError`
    sans modifier `dossier` si la migration spatiale échoue."""
    num_demand    = dossier.num_demand
    ancien_statut = dossier.statut_cf
    alias         = db_alias(zone)
    couche_source = couche_cible = ''

    try:
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cursor:
                found = _find_source_row(cursor, table_source, num_demand)
                if not found:
                    raise MigrationError(
                        f"Parcelle NUM_DEMAND={num_demand!r} introuvable dans la couche {table_source!r}."
                    )
                schema, avail, row = found
                target_schema = _resolve_target_schema(cursor, schema, table_cible, avail, row)

                couche_source = f'{schema}.{table_source}'
                couche_cible  = f'{target_schema}.{table_cible}'

                if not table_exists(cursor, target_schema, table_cible):
                    raise MigrationError(
                        f"Couche cible {couche_cible} inexistante — exécuter la commande "
                        f"'create_publicite_layers' avant d'utiliser ce workflow."
                    )

                cursor.execute(
                    f'DELETE FROM "{schema}"."{table_source}" WHERE "NUM_DEMAND" = %s',
                    [num_demand],
                )
                insert_cols = avail + ['geom']
                col_sql      = ', '.join(f'"{c}"' for c in insert_cols)
                placeholders = ', '.join(['%s'] * len(insert_cols))
                cursor.execute(
                    f'INSERT INTO "{target_schema}"."{table_cible}" ({col_sql}) VALUES ({placeholders})',
                    list(row),
                )
    except Exception as exc:
        HistoriqueMigrationCouche.objects.create(
            dossier=dossier, num_demand=num_demand,
            ancien_statut=ancien_statut, nouveau_statut=nouveau_statut,
            couche_source=couche_source, couche_cible=couche_cible,
            effectue_par=user, succes=False, message_erreur=str(exc),
        )
        raise MigrationError(str(exc)) from exc

    try:
        with transaction.atomic():
            dossier.statut_cf = nouveau_statut
            dossier.save(update_fields=['statut_cf'])
            HistoriqueMigrationCouche.objects.create(
                dossier=dossier, num_demand=num_demand,
                ancien_statut=ancien_statut, nouveau_statut=nouveau_statut,
                couche_source=couche_source, couche_cible=couche_cible,
                effectue_par=user, succes=True,
            )
    except Exception as exc:
        # Cas résiduel accepté par la stratégie best-effort : la migration spatiale a réussi
        # mais la mise à jour métier a échoué. Incohérence journalisée pour réconciliation
        # manuelle (la parcelle est déjà dans la couche cible, statut_cf pas encore à jour).
        HistoriqueMigrationCouche.objects.create(
            dossier=dossier, num_demand=num_demand,
            ancien_statut=ancien_statut, nouveau_statut=nouveau_statut,
            couche_source=couche_source, couche_cible=couche_cible,
            effectue_par=user, succes=False,
            message_erreur=f"Migration spatiale OK mais mise à jour du dossier échouée : {exc}",
        )
        raise MigrationError(
            f"Migration spatiale effectuée (couche cible {couche_cible}) mais la mise à jour "
            f"du dossier a échoué : {exc}. Réconciliation manuelle nécessaire."
        ) from exc

    return dossier
