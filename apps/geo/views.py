import csv
import json

from django.db import connections, OperationalError
from django.http import StreamingHttpResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .db import (
    VALID_ZONES,
    SKIP_SCHEMAS as _SKIP_SCHEMAS,
    db_alias as _db_alias,
    discover_schema_tables as _discover_schema_tables,
    table_exists as _table_exists,
    non_geom_columns as _non_geom_columns,
    get_table_srid as _get_table_srid,
)
from .queries import (
    SOUS_PREFECTURE_TABLES, DTV_FALLBACK_TABLES, CF_PUBLIC_TABLES,
    CF_SCHEMA_TABLES, CF_ONGLET_EXTRA_TABLES, DTV_SCHEMA_TABLES,
    TABLE_STATUT as _TABLE_STATUT, CF_STATUTS, DTV_STATUTS,
    EXACT_FILTERS_CF, EXACT_FILTERS_DTV,
    discover_cf_schema_tables, discover_dtv_schema_tables,
    parse_exact_filters, parse_float, filter_schema_tables_by_statut,
    fetch_attribute_rows, sort_results, compute_stats,
)

VALID_TYPES = {'cf', 'dtv', 'sous_prefecture'}

# CRS source RGCI_TM_5_5_NW — BNETD/IGT Côte d'Ivoire, pas de code EPSG officiel.
PROJ_RGCI = (
    '+proj=tmerc +lat_0=0 +lon_0=-5.5 +k=0.9996 '
    '+x_0=500000 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
)

# CF_Existants Cavally : coordonnées hors zone → exclure du fitBounds
_EXCLUDE_BOUNDS_TABLES = {'CF_Existants'}

_CI_BOUNDS = (-9.5, 2.5, -2.0, 11.0)


# ---------------------------------------------------------------------------
# Helpers (GeoJSON — pagination/tri/export tabulaires : voir apps/geo/queries.py)
# ---------------------------------------------------------------------------


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
        '- `dtv` — Délimitations territoriales villageoises : existant, levé, provisoire\n'
        '- `sous_prefecture` — Limites administratives des sous-préfectures\n\n'
        '**Propriétés de chaque Feature** : tous les champs attributaires de la table shapefile, '
        'plus `_statut` (LEVE/PROV/DEF/EXISTANT), `_schema`, `_source_table`, `_exclude_from_bounds`.\n\n'
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


def _parse_pagination(request):
    try:
        page      = max(1, int(request.GET.get('page', 1)))
        page_size = min(500, max(1, int(request.GET.get('page_size', 100))))
    except ValueError:
        page, page_size = 1, 100
    return page, page_size


def _parse_superficie_params(request):
    return (
        parse_float(request.GET.get('superficie')),
        parse_float(request.GET.get('superficie_min')),
        parse_float(request.GET.get('superficie_max')),
    )


CF_ATTR_PARAMETERS = [
    OpenApiParameter('zone',          location='path', description='`cavally` ou `worodougou`'),
    OpenApiParameter('region',        description='Filtrer par nom de région (insensible à la casse)', required=False),
    OpenApiParameter('departement',   description='Filtrer par nom de département', required=False),
    OpenApiParameter('sous_pref',     description='Filtrer par nom de sous-préfecture', required=False),
    OpenApiParameter('village',       description='Filtrer par nom de village', required=False),
    OpenApiParameter('projet',        description='Filtrer par projet', required=False),
    OpenApiParameter('operateur',     description='Filtrer par opérateur (OTA)', required=False),
    OpenApiParameter('num_demande',   description='Filtrer par numéro de demande exact', required=False),
    OpenApiParameter('nom_demandeur', description='Filtrer par nom du demandeur exact', required=False),
    OpenApiParameter('statut',        description=f'Filtrer par statut : {", ".join(f"`{s}`" for s in CF_STATUTS)}', required=False),
    OpenApiParameter('superficie',     description='Superficie exacte (ha)', required=False, type=float),
    OpenApiParameter('superficie_min', description='Superficie minimale (ha)', required=False, type=float),
    OpenApiParameter('superficie_max', description='Superficie maximale (ha)', required=False, type=float),
    OpenApiParameter('search', description='Recherche libre sur toutes les colonnes attributaires', required=False),
    OpenApiParameter('ordering', description='Tri, ex. `SUPERF` ou `-SUPERF`', required=False),
]

EXPORT_RESPONSE = {
    200: {'description': 'Fichier CSV ou XLSX'},
    400: {'description': 'Zone ou format inconnu'},
    503: {'description': 'Connexion PostGIS impossible'},
}

CF_STATS_RESPONSE = {
    200: {
        'type': 'object',
        'properties': {
            'zone':  {'type': 'string'},
            'stats': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'statut':               {'type': 'string'},
                        'nb_parcelles':         {'type': 'integer'},
                        'superficie_totale_ha': {'type': 'number'},
                    },
                },
            },
        },
    },
    400: {'description': 'Zone inconnue'},
    503: {'description': 'Connexion PostGIS impossible'},
}

DTV_STATS_RESPONSE = {
    200: {
        'type': 'object',
        'properties': {
            'zone':  {'type': 'string'},
            'stats': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'statut':               {'type': 'string'},
                        'nb_villages':          {'type': 'integer'},
                        'superficie_totale_ha': {'type': 'number'},
                    },
                },
            },
        },
    },
    400: {'description': 'Zone inconnue'},
    503: {'description': 'Connexion PostGIS impossible'},
}


@extend_schema(
    tags=['Géoportail'],
    summary='Table attributaire CF — module CF (sans géométrie)',
    description=(
        'Retourne les enregistrements de la couche **CF – Parcelles (Polygones)**, directement '
        'depuis la table attributaire (aucune donnée saisie manuellement). Toutes les tables CF '
        'sont interrogées (levé, provisoire, définitif, existant, en publicité, approuvée, '
        'rejetée, validée).\n\n'
        'La réponse inclut `columns` (liste des colonnes réellement disponibles dans les tables '
        'interrogées, pour un affichage dynamique côté frontend) et `totals_by_statut`.\n\n'
        '**Pagination manuelle** : `page` (défaut 1) et `page_size` (défaut 100, max 500). '
        'Tri via `ordering`, recherche libre via `search`, filtre de superficie via '
        '`superficie`/`superficie_min`/`superficie_max`.'
    ),
    parameters=CF_ATTR_PARAMETERS + [
        OpenApiParameter('page',      description='Numéro de page (défaut 1)', required=False, type=int),
        OpenApiParameter('page_size', description='Taille de page (défaut 100, max 500)', required=False, type=int),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'total':            {'type': 'integer'},
                'page':             {'type': 'integer'},
                'page_size':        {'type': 'integer'},
                'columns':          {'type': 'array', 'items': {'type': 'string'}},
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
def geo_cf_parcelles(request, zone: str):
    """Table attributaire CF (module CF) — filtrable, triable, paginée, sans géométrie."""
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_CF)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search   = (request.GET.get('search') or '').strip()
    ordering = (request.GET.get('ordering') or '').strip()
    page, page_size = _parse_pagination(request)

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_cf_schema_tables(cursor), q_statut)
            results, totals_by_statut, columns = fetch_attribute_rows(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response(
            {'detail': f'Connexion impossible ({zone}) : {exc}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    results = sort_results(results, ordering, columns)

    total = len(results)
    start = (page - 1) * page_size
    page_data = results[start: start + page_size]

    return Response({
        'total':            total,
        'page':             page,
        'page_size':        page_size,
        'columns':          columns,
        'totals_by_statut': totals_by_statut,
        'results':          page_data,
    })


def _export_response(results, columns, fmt: str, filename: str):
    export_cols = columns + ['_statut', '_schema']
    if fmt == 'xlsx':
        try:
            import openpyxl
        except ImportError:
            return Response(
                {'detail': "Export XLSX indisponible : dépendance 'openpyxl' non installée."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(export_cols)
        for rec in results:
            ws.append([rec.get(c) for c in export_cols])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        wb.save(response)
        return response

    class _Echo:
        def write(self, value):
            return value

    writer = csv.writer(_Echo())

    def _rows():
        yield writer.writerow(export_cols)
        for rec in results:
            yield writer.writerow([rec.get(c) for c in export_cols])

    response = StreamingHttpResponse(_rows(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    return response


@extend_schema(
    tags=['Géoportail'],
    summary='Export CF (CSV / XLSX)',
    description=(
        'Exporte les enregistrements de la table attributaire CF (mêmes filtres que '
        '`cf/parcelles/`, sans pagination) au format CSV ou XLSX.'
    ),
    parameters=CF_ATTR_PARAMETERS + [
        OpenApiParameter('format', description='`csv` (défaut) ou `xlsx`', required=False),
    ],
    responses=EXPORT_RESPONSE,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_cf_export(request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)
    fmt = (request.GET.get('format') or 'csv').strip().lower()
    if fmt not in ('csv', 'xlsx'):
        return Response({'detail': f'Format inconnu : {fmt}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_CF)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search = (request.GET.get('search') or '').strip()

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_cf_schema_tables(cursor), q_statut)
            results, _, columns = fetch_attribute_rows(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return _export_response(results, columns, fmt, f'cf_{zone}')


@extend_schema(
    tags=['Géoportail'],
    summary='Statistiques CF par statut (nombre + superficie)',
    description=(
        'Retourne, pour chaque statut CF, le nombre de parcelles et la superficie totale (ha) '
        '— somme de la colonne attributaire `SUPERF`. Accepte les mêmes filtres que '
        '`cf/parcelles/` pour rester cohérent avec la carte et les filtres actifs côté frontend.'
    ),
    parameters=CF_ATTR_PARAMETERS,
    responses=CF_STATS_RESPONSE,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_cf_stats(request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_CF)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search = (request.GET.get('search') or '').strip()

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_cf_schema_tables(cursor), q_statut)
            stats = compute_stats(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response({
        'zone':  zone,
        'stats': [
            {
                'statut':          s,
                'nb_parcelles':    stats.get(s, {}).get('nb', 0),
                'superficie_totale_ha': round(stats.get(s, {}).get('superficie_ha', 0.0), 2),
            }
            for s in CF_STATUTS
        ],
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


# ---------------------------------------------------------------------------
# Module DTV — table attributaire web (miroir du module CF)
# ---------------------------------------------------------------------------

DTV_ATTR_PARAMETERS = [
    OpenApiParameter('zone',        location='path', description='`cavally` ou `worodougou`'),
    OpenApiParameter('region',      description='Filtrer par nom de région (insensible à la casse)', required=False),
    OpenApiParameter('departement', description='Filtrer par nom de département', required=False),
    OpenApiParameter('sous_pref',   description='Filtrer par nom de sous-préfecture', required=False),
    OpenApiParameter('village',     description='Filtrer par nom de village', required=False),
    OpenApiParameter('projet',      description='Filtrer par projet', required=False),
    OpenApiParameter('operateur',   description='Filtrer par opérateur (OTA)', required=False),
    OpenApiParameter('statut',      description=f'Filtrer par statut : {", ".join(f"`{s}`" for s in DTV_STATUTS)}', required=False),
    OpenApiParameter('superficie',     description='Superficie exacte (ha)', required=False, type=float),
    OpenApiParameter('superficie_min', description='Superficie minimale (ha)', required=False, type=float),
    OpenApiParameter('superficie_max', description='Superficie maximale (ha)', required=False, type=float),
    OpenApiParameter('search', description='Recherche libre sur toutes les colonnes attributaires', required=False),
    OpenApiParameter('ordering', description='Tri, ex. `NOM_VILLAGE` ou `-SUPERF`', required=False),
]


@extend_schema(
    tags=['Géoportail'],
    summary='Table attributaire DTV — module DTV (sans géométrie)',
    description=(
        'Retourne les enregistrements de la couche **DTV – Villages (Polygones)**, directement '
        'depuis la table attributaire (aucune donnée saisie manuellement). Statuts : `LEVE`, '
        '`PROV`, `EXISTANT` (anciennement « Délimité »).\n\n'
        'La réponse inclut `columns` (colonnes réellement disponibles) et `totals_by_statut`. '
        'Colonnes attendues si présentes dans la couche : code/nom du village, région, '
        'département, sous-préfecture, superficie, périmètre, projet, opérateur, statut — '
        'toute colonne absente de la couche réelle est simplement omise de la réponse.'
    ),
    parameters=DTV_ATTR_PARAMETERS + [
        OpenApiParameter('page',      description='Numéro de page (défaut 1)', required=False, type=int),
        OpenApiParameter('page_size', description='Taille de page (défaut 100, max 500)', required=False, type=int),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'total':            {'type': 'integer'},
                'page':             {'type': 'integer'},
                'page_size':        {'type': 'integer'},
                'columns':          {'type': 'array', 'items': {'type': 'string'}},
                'totals_by_statut': {'type': 'object'},
                'results':          {'type': 'array', 'items': {'type': 'object'}},
            },
        },
        400: {'description': 'Zone inconnue'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_dtv_villages(request, zone: str):
    """Table attributaire DTV (module DTV) — filtrable, triable, paginée, sans géométrie."""
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_DTV)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search   = (request.GET.get('search') or '').strip()
    ordering = (request.GET.get('ordering') or '').strip()
    page, page_size = _parse_pagination(request)

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_dtv_schema_tables(cursor), q_statut)
            results, totals_by_statut, columns = fetch_attribute_rows(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response(
            {'detail': f'Connexion impossible ({zone}) : {exc}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    results = sort_results(results, ordering, columns)

    total = len(results)
    start = (page - 1) * page_size
    page_data = results[start: start + page_size]

    return Response({
        'total':            total,
        'page':             page,
        'page_size':        page_size,
        'columns':          columns,
        'totals_by_statut': totals_by_statut,
        'results':          page_data,
    })


@extend_schema(
    tags=['Géoportail'],
    summary='Export DTV (CSV / XLSX)',
    description='Exporte les villages DTV (mêmes filtres que `dtv/villages/`, sans pagination).',
    parameters=DTV_ATTR_PARAMETERS + [
        OpenApiParameter('format', description='`csv` (défaut) ou `xlsx`', required=False),
    ],
    responses=EXPORT_RESPONSE,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_dtv_export(request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)
    fmt = (request.GET.get('format') or 'csv').strip().lower()
    if fmt not in ('csv', 'xlsx'):
        return Response({'detail': f'Format inconnu : {fmt}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_DTV)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search = (request.GET.get('search') or '').strip()

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_dtv_schema_tables(cursor), q_statut)
            results, _, columns = fetch_attribute_rows(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return _export_response(results, columns, fmt, f'dtv_{zone}')


@extend_schema(
    tags=['Géoportail'],
    summary='Statistiques DTV par statut (nombre + superficie)',
    description=(
        'Retourne, pour chaque statut DTV (`LEVE`, `PROV`, `EXISTANT`), le nombre de villages '
        'et la superficie totale (ha) des territoires concernés.'
    ),
    parameters=DTV_ATTR_PARAMETERS,
    responses=DTV_STATS_RESPONSE,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_dtv_stats(request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    exact_filters = parse_exact_filters(request, EXACT_FILTERS_DTV)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search = (request.GET.get('search') or '').strip()

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            schema_tables = filter_schema_tables_by_statut(discover_dtv_schema_tables(cursor), q_statut)
            stats = compute_stats(
                cursor, schema_tables,
                exact_filters=exact_filters,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response({
        'zone':  zone,
        'stats': [
            {
                'statut':               s,
                'nb_villages':          stats.get(s, {}).get('nb', 0),
                'superficie_totale_ha': round(stats.get(s, {}).get('superficie_ha', 0.0), 2),
            }
            for s in DTV_STATUTS
        ],
    })


@extend_schema(
    tags=['Géoportail'],
    summary='Résumé global (sous-préfectures, CF, DTV)',
    description=(
        'Retourne les compteurs et superficies globales pour la carte « Résumé » du géoportail : '
        'nombre de sous-préfectures, nombre + superficie totale des parcelles CF, nombre + '
        'superficie totale des villages DTV. Accepte les mêmes filtres que `cf/parcelles/` / '
        '`dtv/villages/` pour rester cohérent avec les filtres actifs côté frontend.'
    ),
    parameters=[OpenApiParameter('zone', location='path', description='`cavally` ou `worodougou`')] + CF_ATTR_PARAMETERS[1:],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'zone':             {'type': 'string'},
                'sous_prefectures': {'type': 'object', 'properties': {'nb': {'type': 'integer'}}},
                'cf':  {'type': 'object', 'properties': {'nb': {'type': 'integer'}, 'superficie_totale_ha': {'type': 'number'}}},
                'dtv': {'type': 'object', 'properties': {'nb': {'type': 'integer'}, 'superficie_totale_ha': {'type': 'number'}}},
            },
        },
        400: {'description': 'Zone inconnue'},
        503: {'description': 'Connexion PostGIS impossible'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geo_resume(request, zone: str):
    zone = zone.lower()
    if zone not in VALID_ZONES:
        return Response({'detail': f'Zone inconnue : {zone}'}, status=400)

    exact_filters_cf  = parse_exact_filters(request, EXACT_FILTERS_CF)
    exact_filters_dtv = parse_exact_filters(request, EXACT_FILTERS_DTV)
    q_statut = (request.GET.get('statut') or '').strip().upper()
    superficie_eq, superficie_min, superficie_max = _parse_superficie_params(request)
    search = (request.GET.get('search') or '').strip()

    try:
        with connections[_db_alias(zone)].cursor() as cursor:
            sp_schema_tables = []
            for t in SOUS_PREFECTURE_TABLES:
                if _table_exists(cursor, 'public', t):
                    sp_schema_tables.append(('public', t))
            nb_sous_prefectures = 0
            for sch, tbl in sp_schema_tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{sch}"."{tbl}"')
                    nb_sous_prefectures += cursor.fetchone()[0]
                except Exception:
                    pass

            cf_schema_tables  = filter_schema_tables_by_statut(discover_cf_schema_tables(cursor), q_statut)
            dtv_schema_tables = filter_schema_tables_by_statut(discover_dtv_schema_tables(cursor), q_statut)

            cf_stats = compute_stats(
                cursor, cf_schema_tables,
                exact_filters=exact_filters_cf,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
            dtv_stats = compute_stats(
                cursor, dtv_schema_tables,
                exact_filters=exact_filters_dtv,
                superficie_eq=superficie_eq, superficie_min=superficie_min, superficie_max=superficie_max,
                search=search or None,
            )
    except OperationalError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    cf_nb    = sum(v['nb'] for v in cf_stats.values())
    cf_ha    = sum(v['superficie_ha'] for v in cf_stats.values())
    dtv_nb   = sum(v['nb'] for v in dtv_stats.values())
    dtv_ha   = sum(v['superficie_ha'] for v in dtv_stats.values())

    return Response({
        'zone': zone,
        'sous_prefectures': {'nb': nb_sous_prefectures},
        'cf':  {'nb': cf_nb, 'superficie_totale_ha': round(cf_ha, 2)},
        'dtv': {'nb': dtv_nb, 'superficie_totale_ha': round(dtv_ha, 2)},
    })


# ---------------------------------------------------------------------------
# Introspection des tables (debug)
# ---------------------------------------------------------------------------

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
