"""Logique métier partagée pour les tables attributaires CF et DTV : quelles tables
interroger pour chaque couche/statut, construction des filtres, agrégation des résultats.

Réutilisé par les endpoints de listing (`geo_cf_parcelles`, `geo_dtv_villages`), d'export
(`geo_cf_export`, `geo_dtv_export`) et de statistiques (`geo_cf_stats`, `geo_dtv_stats`,
`geo_resume`) pour éviter de dupliquer la logique de filtrage à chaque endpoint.
"""

from .db import discover_schema_tables, table_exists, non_geom_columns

# Tables dans le schéma public uniquement
SOUS_PREFECTURE_TABLES = ['Sous_prefecture']
DTV_FALLBACK_TABLES    = ['Villages_delimites']

# Tables CF dans le schéma public (statut fixe)
CF_PUBLIC_TABLES = ['cf_poly_parcelle_Def', 'CF_Existants']

# Tables CF par sous-préfecture — géoportail (carte)
CF_SCHEMA_TABLES = [
    'cf_poly_parcelle_leve',
    'cf_poly_parcelle_Prov',
]

# Tables CF par sous-préfecture — onglet attributaire / workflow de publicité uniquement
# (cf_parcelle_approuvee / cf_parcelle_validee créées par la commande de management
# `create_publicite_layers` — cf. apps/publicite)
CF_ONGLET_EXTRA_TABLES = [
    'cf_parcelle_en_publicite',
    'cf_parcelle_apres_publicite',
    'cf_parcelle_approuvee',
    'cf_parcelle_validee',
    'cf_parcelle_rejete',
]

# Tables DTV présentes dans chaque schéma sous-préfecture
DTV_SCHEMA_TABLES = [
    'dtv_poly_village_leve',
    'dtv_poly_village_Prov',
]

# Statut déduit du nom de table
TABLE_STATUT = {
    'cf_poly_parcelle_leve':       'LEVE',
    'cf_poly_parcelle_Prov':       'PROV',
    'cf_poly_parcelle_Def':        'DEF',
    'CF_Existants':                'EXISTANT',
    'cf_parcelle_en_publicite':    'EN_PUBLICITE',
    'cf_parcelle_apres_publicite': 'APRES_PUBLICITE',
    'cf_parcelle_approuvee':       'APPROUVEE',
    'cf_parcelle_validee':         'VALIDEE',
    'cf_parcelle_rejete':          'REJETE',
    'dtv_poly_village_leve':       'LEVE',
    'dtv_poly_village_Prov':       'PROV',
    'dtv_poly_village_Def':        'DEF',
    'Villages_delimites':          'EXISTANT',
}

CF_STATUTS  = ['LEVE', 'PROV', 'DEF', 'EXISTANT', 'EN_PUBLICITE', 'APRES_PUBLICITE', 'APPROUVEE', 'VALIDEE', 'REJETE']
DTV_STATUTS = ['LEVE', 'PROV', 'EXISTANT']

# Colonne attributaire portant la superficie (ha) dans les couches shapefile BNETD/IGT
SUPERFICIE_COL = 'SUPERF'

# Filtres à correspondance exacte (insensible à la casse) exposés par les endpoints CF/DTV.
# Convention de nommage des colonnes identique pour CF et DTV (même producteur shapefile
# BNETD/IGT) ; une colonne absente d'une table donnée est simplement ignorée par build_where.
#
# NB : le filtre « statut » (LEVE/PROV/DEF/EXISTANT/EN_PUBLICITE/...) n'est PAS un filtre sur
# une colonne attributaire — c'est la couche/table dont provient la ligne (cf. TABLE_STATUT
# et `filter_schema_tables_by_statut`). La colonne shapefile "STATUT" (si elle existe) porte
# une valeur métier différente et n'est pas exposée comme filtre ici pour éviter la confusion.
EXACT_FILTERS_CF = [
    ('region', 'NOM_REGION'), ('departement', 'NOM_DEPART'), ('sous_pref', 'NOM_SSPREF'),
    ('village', 'NOM_VILLAGE'), ('projet', 'NOM_PROJET'), ('operateur', 'NOM_OTA'),
    ('num_demande', 'NUM_DEMAND'), ('nom_demandeur', 'NOM_DEMAND'),
]
EXACT_FILTERS_DTV = [
    ('region', 'NOM_REGION'), ('departement', 'NOM_DEPART'), ('sous_pref', 'NOM_SSPREF'),
    ('village', 'NOM_VILLAGE'), ('projet', 'NOM_PROJET'), ('operateur', 'NOM_OTA'),
]


def discover_cf_schema_tables(cursor, *, include_onglet_extra: bool = True) -> list[tuple[str, str]]:
    schema_tables: list[tuple[str, str]] = []
    for t in CF_PUBLIC_TABLES:
        if table_exists(cursor, 'public', t):
            schema_tables.append(('public', t))
    names = CF_SCHEMA_TABLES + (CF_ONGLET_EXTRA_TABLES if include_onglet_extra else [])
    schema_tables.extend(discover_schema_tables(cursor, names))
    return schema_tables


def discover_dtv_schema_tables(cursor) -> list[tuple[str, str]]:
    schema_tables: list[tuple[str, str]] = []
    for t in DTV_FALLBACK_TABLES:
        if table_exists(cursor, 'public', t):
            schema_tables.append(('public', t))
    schema_tables.extend(discover_schema_tables(cursor, DTV_SCHEMA_TABLES))
    return schema_tables


def table_statut(table: str) -> str:
    return TABLE_STATUT.get(table, table.upper())


def filter_schema_tables_by_statut(
    schema_tables: list[tuple[str, str]], statut: str | None,
) -> list[tuple[str, str]]:
    """Ne conserve que les (schema, table) dont la couche correspond au statut demandé
    (LEVE/PROV/DEF/EXISTANT/EN_PUBLICITE/...). Contrairement aux autres filtres, le statut
    ne porte pas sur une colonne attributaire mais sur la table/couche d'origine de la ligne."""
    if not statut:
        return schema_tables
    return [(s, t) for s, t in schema_tables if table_statut(t) == statut]


def parse_float(value) -> float | None:
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def parse_exact_filters(request, spec: list[tuple[str, str]]) -> dict[str, str]:
    """Lit les query params GET listés dans `spec` (param_name, colonne) et renvoie
    {colonne: valeur_upper} pour ceux effectivement fournis."""
    result = {}
    for param, col in spec:
        value = (request.GET.get(param) or '').strip()
        if value:
            result[col] = value.upper()
    return result


def build_where(
    avail_cols: list[str],
    exact_filters: dict[str, str],
    *,
    superficie_eq: float | None = None,
    superficie_min: float | None = None,
    superficie_max: float | None = None,
    search: str | None = None,
    superficie_col: str = SUPERFICIE_COL,
) -> tuple[str, list]:
    where_parts = ['1=1']
    params: list = []

    for col, value in exact_filters.items():
        if col in avail_cols:
            where_parts.append(f'UPPER(CAST("{col}" AS TEXT)) = %s')
            params.append(value)

    if superficie_col in avail_cols:
        if superficie_eq is not None:
            where_parts.append(f'"{superficie_col}" = %s')
            params.append(superficie_eq)
        if superficie_min is not None:
            where_parts.append(f'"{superficie_col}" >= %s')
            params.append(superficie_min)
        if superficie_max is not None:
            where_parts.append(f'"{superficie_col}" <= %s')
            params.append(superficie_max)

    if search and avail_cols:
        search_sql = ' OR '.join(f'CAST("{c}" AS TEXT) ILIKE %s' for c in avail_cols)
        where_parts.append(f'({search_sql})')
        params.extend([f'%{search}%'] * len(avail_cols))

    return ' AND '.join(where_parts), params


def fetch_attribute_rows(
    cursor,
    schema_tables: list[tuple[str, str]],
    *,
    exact_filters: dict[str, str],
    superficie_eq: float | None = None,
    superficie_min: float | None = None,
    superficie_max: float | None = None,
    search: str | None = None,
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Interroge chaque (schema, table) avec les mêmes filtres et agrège les lignes.

    Retourne (results, totals_by_statut, columns). `columns` préserve l'ordre de première
    apparition des colonnes rencontrées, pour exposer une liste cohérente au frontend même
    si de nouveaux champs sont ajoutés à la couche (aucune liste de colonnes figée ici).
    """
    results: list[dict] = []
    totals_by_statut: dict[str, int] = {}
    columns_seen: dict[str, None] = {}

    for schema, table in schema_tables:
        statut = table_statut(table)
        avail = non_geom_columns(cursor, schema, table)
        if not avail:
            continue

        where_sql, params = build_where(
            avail, exact_filters,
            superficie_eq=superficie_eq, superficie_min=superficie_min,
            superficie_max=superficie_max, search=search,
        )
        col_sql = ', '.join(f'"{c}"' for c in avail)
        try:
            cursor.execute(f'SELECT {col_sql} FROM "{schema}"."{table}" WHERE {where_sql}', params)
            col_names = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        except Exception:
            continue

        totals_by_statut[statut] = totals_by_statut.get(statut, 0) + len(rows)
        for col in col_names:
            columns_seen.setdefault(col, None)
        for row in rows:
            rec = {col_names[i]: row[i] for i in range(len(col_names))}
            rec['_statut'] = statut
            rec['_schema'] = schema
            results.append(rec)

    return results, totals_by_statut, list(columns_seen.keys())


def sort_results(results: list[dict], ordering: str | None, columns: list[str]) -> list[dict]:
    if not ordering:
        return results
    field = ordering.lstrip('-')
    if field not in columns and field not in ('_statut', '_schema'):
        return results
    reverse = ordering.startswith('-')

    def _key(rec):
        v = rec.get(field)
        return (v is None, v if v is not None else '')

    return sorted(results, key=_key, reverse=reverse)


def compute_stats(
    cursor,
    schema_tables: list[tuple[str, str]],
    *,
    exact_filters: dict[str, str],
    superficie_eq: float | None = None,
    superficie_min: float | None = None,
    superficie_max: float | None = None,
    search: str | None = None,
) -> dict[str, dict]:
    """Compteurs + superficie totale (ha) par statut, en sommant la colonne attributaire
    SUPERF (pas de calcul géométrique ST_Area — cohérent avec des données directement
    issues de la table attributaire, comme demandé par le cahier des charges)."""
    stats: dict[str, dict] = {}
    for schema, table in schema_tables:
        statut = table_statut(table)
        avail = non_geom_columns(cursor, schema, table)
        if not avail:
            continue
        where_sql, params = build_where(
            avail, exact_filters,
            superficie_eq=superficie_eq, superficie_min=superficie_min,
            superficie_max=superficie_max, search=search,
        )
        superficie_expr = f'SUM("{SUPERFICIE_COL}")' if SUPERFICIE_COL in avail else 'NULL'
        try:
            cursor.execute(
                f'SELECT COUNT(*), {superficie_expr} FROM "{schema}"."{table}" WHERE {where_sql}',
                params,
            )
            count, superficie = cursor.fetchone()
        except Exception:
            continue
        entry = stats.setdefault(statut, {'nb': 0, 'superficie_ha': 0.0})
        entry['nb'] += count or 0
        entry['superficie_ha'] += float(superficie) if superficie else 0.0
    return stats
