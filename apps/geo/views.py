import json

from django.db import connections, OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter

VALID_ZONES = {'cavally', 'worodougou'}
VALID_TYPES = {'cf', 'dtv', 'sous_prefecture'}

# CRS source RGCI_TM_5_5_NW — BNETD/IGT Côte d'Ivoire, pas de code EPSG officiel.
PROJ_RGCI = (
    '+proj=tmerc +lat_0=0 +lon_0=-5.5 +k=0.9996 '
    '+x_0=500000 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
)

# Schemas système à ignorer lors de la découverte
_SKIP_SCHEMAS = frozenset({
    'information_schema', 'pg_catalog', 'topology',
    'admin', 'test', 'test_29n', 'test_30n',
})

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

# Tables CF par sous-préfecture — onglet attributaire uniquement
CF_ONGLET_EXTRA_TABLES = [
    'cf_parcelle_en_publicite',
    'cf_parcelle_apres_publicite',
    'cf_parcelle_rejete',
]

# Tables DTV présentes dans chaque schéma sous-préfecture
DTV_SCHEMA_TABLES = [
    'dtv_poly_village_leve',
    'dtv_poly_village_Prov',
]

# Statut déduit du nom de table
_TABLE_STATUT = {
    'cf_poly_parcelle_leve':       'LEVE',
    'cf_poly_parcelle_Prov':       'PROV',
    'cf_poly_parcelle_Def':        'DEF',
    'CF_Existants':                'EXISTANT',
    'cf_parcelle_en_publicite':    'EN_PUBLICITE',
    'cf_parcelle_apres_publicite': 'APRES_PUBLICITE',
    'cf_parcelle_rejete':          'REJETE',
    'dtv_poly_village_leve':       'LEVE',
    'dtv_poly_village_Prov':       'PROV',
    'dtv_poly_village_Def':        'DEF',
    'Villages_delimites':          'DELIMITE',
}

# CF_Existants Cavally : coordonnées hors zone → exclure du fitBounds
_EXCLUDE_BOUNDS_TABLES = {'CF_Existants'}

_CI_BOUNDS = (-9.5, 2.5, -2.0, 11.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_alias(zone: str) -> str:
    return f'{zone}_spatial'


def _discover_schema_tables(cursor, table_names: list[str]) -> list[tuple[str, str]]:
    """Retourne (schema, table_name) pour toutes les tables matchant les noms donnés
    dans tous les schémas non-système, triées par schema puis table."""
    placeholders = ','.join(['%s'] * len(table_names))
    skip = list(_SKIP_SCHEMAS)
    skip_ph = ','.join(['%s'] * len(skip))
    cursor.execute(
        f"SELECT table_schema, table_name "
        f"FROM information_schema.tables "
        f"WHERE table_type='BASE TABLE' "
        f"  AND table_name IN ({placeholders}) "
        f"  AND table_schema NOT IN ({skip_ph}) "
        f"ORDER BY table_schema, table_name",
        table_names + skip,
    )
    return [(row[0], row[1]) for row in cursor.fetchall()]


def _table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s",
        [schema, table],
    )
    return cursor.fetchone() is not None


def _non_geom_columns(cursor, schema: str, table: str) -> list[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s "
        "AND udt_name NOT IN ('geometry','geography') "
        "ORDER BY ordinal_position",
        [schema, table],
    )
    return [row[0] for row in cursor.fetchall()]


def _get_table_srid(cursor, schema: str, table: str) -> int:
    try:
        cursor.execute(
            f'SELECT ST_SRID(geom) FROM "{schema}"."{table}" WHERE geom IS NOT NULL LIMIT 1'
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _has_data_multi(cursor, schema_tables: list[tuple[str, str]]) -> bool:
    for sch, tbl in schema_tables:
        try:
            cursor.execute(f'SELECT 1 FROM "{sch}"."{tbl}" WHERE geom IS NOT NULL LIMIT 1')
            if cursor.fetchone():
                return True
        except Exception:
            pass
    return False


def _table_to_features(
    cursor,
    schema: str,
    table: str,
    statut_override: str | None = None,
) -> list[dict]:
    cols = _non_geom_columns(cursor, schema, table)
    if not cols:
        return []

    statut = statut_override or _TABLE_STATUT.get(table) or table.rsplit('_', 1)[-1].upper()

    col_sql = ', '.join(f'"{c}"' for c in cols)

    srid = _get_table_srid(cursor, schema, table)
    if srid == 0:
        geojson_expr = "ST_AsGeoJSON(ST_Transform(ST_MakeValid(geom), %s, 'EPSG:4326'), 6)"
        params: list = [PROJ_RGCI]
    else:
        geojson_expr = "ST_AsGeoJSON(ST_Transform(ST_MakeValid(geom), 4326), 6)"
        params = []

    cursor.execute(
        f'SELECT {geojson_expr} AS geojson, '
        f'{col_sql} FROM "{schema}"."{table}" WHERE geom IS NOT NULL LIMIT 8000',
        params,
    )
    col_names = [desc[0] for desc in cursor.description]

    exclude_bounds = table in _EXCLUDE_BOUNDS_TABLES

    features = []
    for row in cursor.fetchall():
        geom_raw = row[0]
        if not geom_raw:
            continue
        props = {col_names[i + 1]: row[i + 1] for i in range(len(cols))}
        props['_statut']              = statut
        props['_schema']              = schema
        props['_source_table']        = table
        props['_exclude_from_bounds'] = exclude_bounds
        features.append({
            'type':       'Feature',
            'geometry':   json.loads(geom_raw),
            'properties': props,
        })
    return features


def _compute_bounds(features: list[dict]) -> list | None:
    min_lon, min_lat, max_lon, max_lat = _CI_BOUNDS

    def _in_ci(lon, lat):
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

    all_coords = []

    def collect(geom, exclude):
        t = geom.get('type', '')
        c = geom.get('coordinates', [])
        candidates = []
        if t == 'Point':
            candidates = [c]
        elif t in ('LineString', 'MultiPoint'):
            candidates = c
        elif t in ('Polygon', 'MultiLineString'):
            for ring in c:
                candidates.extend(ring)
        elif t == 'MultiPolygon':
            for poly in c:
                for ring in poly:
                    candidates.extend(ring)
        if not exclude:
            for pt in candidates:
                if len(pt) >= 2 and _in_ci(pt[0], pt[1]):
                    all_coords.append(pt)

    for f in features:
        if f.get('geometry'):
            exclude = f.get('properties', {}).get('_exclude_from_bounds', False)
            collect(f['geometry'], exclude)

    if not all_coords:
        for f in features:
            if f.get('geometry'):
                collect(f['geometry'], False)

    if not all_coords:
        return None

    lngs = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    return [[min(lats), min(lngs)], [max(lats), max(lngs)]]


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Géoportail'],
    summary='Couche GeoJSON (CF / DTV / sous-préfectures)',
    description=(
        'Retourne un **GeoJSON FeatureCollection** pour la couche demandée dans la zone donnée.\n\n'
        '**Valeurs `zone`** : `cavally`, `worodougou`\n\n'
        '**Valeurs `layer_type`** :\n'
        '- `cf` — Certificats fonciers : levé, provisoire, définitif, existant (toutes tables)\n'
        '- `dtv` — Délimitations territoriales villageoises : délimités, levé, provisoire\n'
        '- `sous_prefecture` — Limites administratives des sous-préfectures\n\n'
        '**Propriétés de chaque Feature** : tous les champs attributaires de la table shapefile, '
        'plus `_statut` (LEVE/PROV/DEF/EXISTANT/DELIMITE), `_schema`, `_source_table`, `_exclude_from_bounds`.\n\n'
        '**`_meta`** dans la réponse : `zone`, `layer_type`, `tables` interrogées, '
        '`feature_count`, `bounds` ([[lat_min, lng_min], [lat_max, lng_max]]).\n\n'
        'Géométries reprojetées en WGS84 (EPSG:4326). Limite : 8 000 features par table.'
    ),
    parameters=[
        OpenApiParameter('zone',       location='path', description='Zone géographique : `cavally` ou `worodougou`'),
        OpenApiParameter('layer_type', location='path', description='Type de couche : `cf`, `dtv` ou `sous_prefecture`'),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'type':     {'type': 'string', 'example': 'FeatureCollection'},
                'features': {'type': 'array', 'items': {'type': 'object'}},
                '_meta': {
                    'type': 'object',
                    'properties': {
                        'zone':          {'type': 'string'},
                        'layer_type':    {'type': 'string'},
                        'tables':        {'type': 'array', 'items': {'type': 'string'}},
                        'feature_count': {'type': 'integer'},
                        'bounds':        {'type': 'array', 'nullable': True},
                    },
                },
            },
        },
        400: {'description': 'Zone ou type inconnu'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_layer(_request, zone: str, layer_type: str):
    zone       = zone.lower()
    layer_type = layer_type.lower()

    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)
    if layer_type not in VALID_TYPES:
        return Response({'detail': f'Type inconnu : {layer_type}'}, status=400)

    try:
        with connections[_db_alias(zone)].cursor() as cursor:

            schema_tables: list[tuple[str, str]] = []

            if layer_type == 'sous_prefecture':
                for t in SOUS_PREFECTURE_TABLES:
                    if _table_exists(cursor, 'public', t):
                        schema_tables.append(('public', t))

            elif layer_type == 'cf':
                # 1. Tables schéma public (Def + Existants)
                for t in CF_PUBLIC_TABLES:
                    if _table_exists(cursor, 'public', t):
                        schema_tables.append(('public', t))
                # 2. Tables par sous-préfecture (leve, Prov, publicite, rejete)
                schema_tables.extend(_discover_schema_tables(cursor, CF_SCHEMA_TABLES))

            elif layer_type == 'dtv':
                # Toujours inclure Villages_delimites (territoires délimités administratifs)
                for t in DTV_FALLBACK_TABLES:
                    if _table_exists(cursor, 'public', t):
                        schema_tables.append(('public', t))
                # Ajouter les tables levé/Prov par sous-préfecture quand elles ont des données
                schema_tables.extend(_discover_schema_tables(cursor, DTV_SCHEMA_TABLES))

            all_features: list[dict] = []
            for sch, tbl in schema_tables:
                try:
                    all_features.extend(_table_to_features(cursor, sch, tbl))
                except Exception:
                    pass

        bounds = _compute_bounds(all_features)
        tables_meta = [f'{s}.{t}' for s, t in schema_tables]

        return Response({
            'type':     'FeatureCollection',
            'features': all_features,
            '_meta': {
                'zone':          zone,
                'layer_type':    layer_type,
                'tables':        tables_meta,
                'feature_count': len(all_features),
                'bounds':        bounds,
            },
        })

    except OperationalError as exc:
        return Response(
            {'detail': f'Connexion impossible ({zone}) : {exc}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@extend_schema(
    tags=['Géoportail'],
    summary='Attributs tabulaires CF — onglet attributaire (sans géométrie)',
    description=(
        'Retourne les données attributaires des parcelles CF de la zone, **sans géométrie**. '
        'Utilisé pour l\'onglet tableau du géoportail.\n\n'
        '**Colonnes retournées** : `NUM_DEMAND`, `NOM_REGION`, `NOM_DEPART`, `NOM_SSPREF`, '
        '`NOM_VILLAGE`, `NOM_DEMAND`, `SUPERF`, `PERIM`, `NOM_PROJET`, `NOM_OTA`, `STATUT`, `N_DEMCGE`, `_statut`, `_schema`.\n\n'
        'Toutes les tables CF sont interrogées (levé, provisoire, définitif, existant, publicité, rejeté). '
        'La réponse inclut `totals_by_statut` pour connaître la répartition par type.\n\n'
        '**Pagination manuelle** : `page` (défaut 1) et `page_size` (défaut 100, max 500).'
    ),
    parameters=[
        OpenApiParameter('zone',       location='path', description='`cavally` ou `worodougou`'),
        OpenApiParameter('region',     description='Filtrer par nom de région (insensible à la casse)', required=False),
        OpenApiParameter('departement',description='Filtrer par nom de département', required=False),
        OpenApiParameter('sous_pref',  description='Filtrer par nom de sous-préfecture', required=False),
        OpenApiParameter('village',    description='Filtrer par nom de village', required=False),
        OpenApiParameter('statut',     description='Filtrer par statut : `LEVE`, `PROV`, `DEF`, `EXISTANT`, `EN_PUBLICITE`, `APRES_PUBLICITE`, `REJETE`', required=False),
        OpenApiParameter('page',       description='Numéro de page (défaut 1)', required=False, type=int),
        OpenApiParameter('page_size',  description='Taille de page (défaut 100, max 500)', required=False, type=int),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'total':            {'type': 'integer'},
                'page':             {'type': 'integer'},
                'page_size':        {'type': 'integer'},
                'totals_by_statut': {'type': 'object', 'description': 'Compteur par statut CF'},
                'results':          {'type': 'array', 'items': {'type': 'object'}},
            },
        },
        400: {'description': 'Zone inconnue'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_cf_parcelles(_request, zone: str):
    """Données tabulaires CF pour l'onglet attributaire (sans géométrie).
    Params GET optionnels : region, departement, sous_pref, village, statut, page, page_size.
    """
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    # Filtres
    q_region  = _request.GET.get('region', '').strip().upper()
    q_dept    = _request.GET.get('departement', '').strip().upper()
    q_sp      = _request.GET.get('sous_pref', '').strip().upper()
    q_village = _request.GET.get('village', '').strip().upper()
    q_statut  = _request.GET.get('statut', '').strip().upper()

    try:
        page      = max(1, int(_request.GET.get('page', 1)))
        page_size = min(500, max(1, int(_request.GET.get('page_size', 100))))
    except ValueError:
        page, page_size = 1, 100

    # Colonnes fixes retournées (sous-ensemble pertinent)
    COLS = [
        'NUM_DEMAND', 'NOM_REGION', 'NOM_DEPART', 'NOM_SSPREF',
        'NOM_VILLAGE', 'NOM_DEMAND', 'SUPERF', 'PERIM',
        'NOM_PROJET', 'NOM_OTA', 'STATUT', 'N_DEMCGE',
    ]

    results   = []
    totals_by_statut: dict[str, int] = {}

    try:
        with connections[_db_alias(zone)].cursor() as cursor:

            schema_tables: list[tuple[str, str]] = []
            for t in CF_PUBLIC_TABLES:
                if _table_exists(cursor, 'public', t):
                    schema_tables.append(('public', t))
            # Onglet = carte + tables publicite/rejete
            all_cf_schema = CF_SCHEMA_TABLES + CF_ONGLET_EXTRA_TABLES
            schema_tables.extend(_discover_schema_tables(cursor, all_cf_schema))

            for sch, tbl in schema_tables:
                statut = _TABLE_STATUT.get(tbl, tbl.upper())

                # filtre statut
                if q_statut and statut != q_statut:
                    continue

                # Colonnes disponibles dans cette table
                avail = _non_geom_columns(cursor, sch, tbl)
                cols_to_fetch = [c for c in COLS if c in avail]
                if not cols_to_fetch:
                    continue

                col_sql = ', '.join(f'"{c}"' for c in cols_to_fetch)
                where_parts = ['1=1']
                params: list = []

                if q_region and 'NOM_REGION' in avail:
                    where_parts.append('UPPER("NOM_REGION") = %s')
                    params.append(q_region)
                if q_dept and 'NOM_DEPART' in avail:
                    where_parts.append('UPPER("NOM_DEPART") = %s')
                    params.append(q_dept)
                if q_sp and 'NOM_SSPREF' in avail:
                    where_parts.append('UPPER("NOM_SSPREF") = %s')
                    params.append(q_sp)
                if q_village and 'NOM_VILLAGE' in avail:
                    where_parts.append('UPPER("NOM_VILLAGE") = %s')
                    params.append(q_village)

                where_sql = ' AND '.join(where_parts)

                try:
                    cursor.execute(
                        f'SELECT {col_sql} FROM "{sch}"."{tbl}" WHERE {where_sql}',
                        params,
                    )
                    col_names = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    n = len(rows)
                    totals_by_statut[statut] = totals_by_statut.get(statut, 0) + n
                    for row in rows:
                        rec = {col_names[i]: row[i] for i in range(len(col_names))}
                        rec['_statut'] = statut
                        rec['_schema'] = sch
                        results.append(rec)
                except Exception:
                    pass

    except OperationalError as exc:
        return Response(
            {'detail': f'Connexion impossible ({zone}) : {exc}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    total = len(results)
    start = (page - 1) * page_size
    page_data = results[start: start + page_size]

    return Response({
        'total':           total,
        'page':            page,
        'page_size':       page_size,
        'totals_by_statut': totals_by_statut,
        'results':         page_data,
    })


@extend_schema(
    tags=['Géoportail'],
    summary='Attributs shapefile par numéro de demande — usage contrôle qualité',
    description=(
        'Retourne tous les attributs shapefile d\'une parcelle CF identifiée par son `NUM_DEMAND`, '
        '**sans géométrie**. Interroge toutes les tables CF de la zone.\n\n'
        '**Usage** : panneau droit (Shapefile) de la fenêtre de contrôle qualité — '
        'compare les données DIGIFOR avec les données du shapefile (superficie, OTA, statut…).\n\n'
        'Chaque enregistrement inclut `_statut`, `_source_table` et `_schema` pour identifier l\'origine.'
    ),
    parameters=[
        OpenApiParameter('zone',       location='path', description='`cavally` ou `worodougou`'),
        OpenApiParameter('num_demand', description='Numéro de demande DIGIFOR (ex: CF-2024-00123)', required=True),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'zone':       {'type': 'string'},
                'num_demand': {'type': 'string'},
                'records': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'description': 'Tous les champs du shapefile + _statut, _source_table, _schema',
                    },
                },
            },
        },
        400: {'description': 'num_demand manquant ou zone inconnue'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_cf_detail(_request, zone: str):
    """Attributs shapefile (sans géométrie) pour un NUM_DEMAND donné — usage contrôle qualité."""
    zone = zone.lower()
    num_demand = _request.GET.get('num_demand', '').strip()
    if not num_demand:
        return Response({'detail': 'num_demand requis'}, status=400)
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    results = []
    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables: list[tuple[str, str]] = []
            for t in CF_PUBLIC_TABLES:
                if _table_exists(cursor, 'public', t):
                    schema_tables.append(('public', t))
            all_cf_schema = CF_SCHEMA_TABLES + CF_ONGLET_EXTRA_TABLES
            schema_tables.extend(_discover_schema_tables(cursor, all_cf_schema))

            for sch, tbl in schema_tables:
                avail = _non_geom_columns(cursor, sch, tbl)
                if 'NUM_DEMAND' not in avail:
                    continue
                col_sql = ', '.join(f'"{c}"' for c in avail)
                try:
                    cursor.execute(
                        f'SELECT {col_sql} FROM "{sch}"."{tbl}" WHERE "NUM_DEMAND" = %s',
                        [num_demand],
                    )
                    db_cols = [d[0] for d in cursor.description]
                    for row in cursor.fetchall():
                        rec = {db_cols[i]: row[i] for i in range(len(db_cols))}
                        rec['_statut']       = _TABLE_STATUT.get(tbl, tbl.upper())
                        rec['_source_table'] = tbl
                        rec['_schema']       = sch
                        results.append(rec)
                except Exception:
                    pass

    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response({'zone': zone, 'num_demand': num_demand, 'records': results})


@extend_schema(
    tags=['Géoportail'],
    summary='Tables PostGIS disponibles dans la zone',
    description=(
        'Retourne la liste de toutes les tables spatiales présentes dans la base PostGIS de la zone '
        '(via `geometry_columns`). Utilisé pour la découverte et le débogage.\n\n'
        'Chaque entrée contient : `schema`, `table`, `geom_col`, `type` (POLYGON, MULTIPOLYGON…), `srid`.'
    ),
    parameters=[
        OpenApiParameter('zone', location='path', description='`cavally` ou `worodougou`'),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'zone': {'type': 'string'},
                'tables': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'schema':   {'type': 'string'},
                            'table':    {'type': 'string'},
                            'geom_col': {'type': 'string'},
                            'type':     {'type': 'string'},
                            'srid':     {'type': 'integer'},
                        },
                    },
                },
            },
        },
        400: {'description': 'Zone inconnue'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_tables(_request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            cursor.execute(
                "SELECT f_table_schema, f_table_name, f_geometry_column, type, srid "
                "FROM geometry_columns "
                "WHERE f_table_schema NOT IN ("
                + ','.join(['%s'] * len(_SKIP_SCHEMAS))
                + ") ORDER BY f_table_schema, f_table_name",
                list(_SKIP_SCHEMAS),
            )
            tables = [
                {'schema': r[0], 'table': r[1], 'geom_col': r[2], 'type': r[3], 'srid': r[4]}
                for r in cursor.fetchall()
            ]
        return Response({'zone': zone, 'tables': tables})

    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
