"""Connexion et introspection bas niveau des bases PostGIS spatiales externes (une par zone).

Les données géographiques (CF, DTV, sous-préfectures) vivent dans des bases Postgres OVH
séparées de la base métier `default` (déclarées dans `settings.DATABASES` sous les alias
`<zone>_spatial`). Ce module ne connaît que la structure physique (schémas/tables/colonnes) ;
la logique métier (quelles tables interroger pour quelle couche, quels filtres) vit dans
`apps/geo/queries.py`.
"""

VALID_ZONES = {'cavally', 'worodougou'}

# Schémas système à ignorer lors de la découverte de tables
SKIP_SCHEMAS = frozenset({
    'information_schema', 'pg_catalog', 'topology',
    'admin', 'test', 'test_29n', 'test_30n',
})


def db_alias(zone: str) -> str:
    return f'{zone}_spatial'


def discover_schema_tables(cursor, table_names: list[str]) -> list[tuple[str, str]]:
    """Retourne (schema, table_name) pour toutes les tables matchant les noms donnés
    dans tous les schémas non-système, triées par schema puis table."""
    placeholders = ','.join(['%s'] * len(table_names))
    skip = list(SKIP_SCHEMAS)
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


def table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s",
        [schema, table],
    )
    return cursor.fetchone() is not None


def non_geom_columns(cursor, schema: str, table: str) -> list[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s "
        "AND udt_name NOT IN ('geometry','geography') "
        "ORDER BY ordinal_position",
        [schema, table],
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_srid(cursor, schema: str, table: str) -> int:
    try:
        cursor.execute(
            f'SELECT ST_SRID(geom) FROM "{schema}"."{table}" WHERE geom IS NOT NULL LIMIT 1'
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def has_data_multi(cursor, schema_tables: list[tuple[str, str]]) -> bool:
    for sch, tbl in schema_tables:
        try:
            cursor.execute(f'SELECT 1 FROM "{sch}"."{tbl}" WHERE geom IS NOT NULL LIMIT 1')
            if cursor.fetchone():
                return True
        except Exception:
            pass
    return False
