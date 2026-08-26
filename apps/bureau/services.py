"""Import du fichier Excel journalier « Planning Bureau ». Le fichier déposé par l'agent
contient une ligne par village travaillé ce jour-là ; l'import calcule `nb_parcelles` et
`superficie_totale` (sommes) ainsi que `repartition_village` (détail par village) — jamais
saisis à la main. Même philosophie que `apps.dossiers.services` (import ADS) : une ligne en
erreur n'empêche pas les autres d'être comptabilisées."""

# Colonnes reconnues dans le fichier (en-têtes comparés en minuscules/strippés/espaces->_).
# Plusieurs libellés possibles par colonne car le fichier est produit par différents agents.
COL_VILLAGE_ALIASES = ['village', 'nom_village', 'village_nom']
COL_NB_ALIASES       = ['nb_parcelles', 'nombre_de_parcelles', 'nb_pdf', 'nombre_de_pdf', 'nombre', 'quantite', 'nb']
COL_SUPERF_ALIASES   = ['superficie', 'superficie_ha', 'superficie_(ha)', 'superficie_totale', 'ha']


class ImportRapportBureauError(Exception):
    """Levée pour un problème global empêchant toute lecture du fichier (format non supporté,
    fichier vide, colonne village introuvable dans l'en-tête)."""


def _normalize_header(h) -> str:
    return (h or '').strip().lower().replace(' ', '_')


def _read_rows(fichier):
    name = (fichier.name or '').lower()
    if not name.endswith('.xlsx'):
        raise ImportRapportBureauError("Format de fichier non supporté — utiliser un classeur .xlsx.")

    try:
        import openpyxl
    except ImportError:
        raise ImportRapportBureauError("Dépendance 'openpyxl' non installée côté serveur.")

    wb = openpyxl.load_workbook(fichier, read_only=True, data_only=True)
    ws = wb.active
    rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
    if not rows:
        raise ImportRapportBureauError("Fichier vide.")

    headers = [_normalize_header(h) for h in rows[0]]
    if not any(a in headers for a in COL_VILLAGE_ALIASES):
        raise ImportRapportBureauError(
            "Colonne « Village » introuvable dans l'en-tête du fichier "
            f"(attendu l'un de : {', '.join(COL_VILLAGE_ALIASES)})."
        )

    data_rows = []
    for raw_row in rows[1:]:
        if raw_row is None or all(c in (None, '') for c in raw_row):
            continue
        rec = {}
        for i, h in enumerate(headers):
            rec[h] = raw_row[i] if i < len(raw_row) else None
        data_rows.append(rec)
    return data_rows


def _clean(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _first_value(row: dict, aliases: list[str]):
    for a in aliases:
        if a in row and row[a] not in (None, ''):
            return row[a]
    return None


def _parse_number(value, *, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} invalide : {value!r}.")


def importer_rapport_bureau(fichier) -> dict:
    """Parse `fichier` (une ligne = un village) et retourne
    {nb_parcelles, superficie_totale, repartition_village, errors} — ne touche pas la base,
    la vue est responsable de reporter ce résultat sur l'instance `RapportBureau`."""
    rows = _read_rows(fichier)

    par_village: dict[str, dict] = {}
    errors: list[dict] = []

    for idx, row in enumerate(rows, start=2):  # ligne 1 = en-tête
        village = _clean(_first_value(row, COL_VILLAGE_ALIASES))
        if not village:
            continue  # ligne vide/non exploitable, pas une erreur en soi

        try:
            nb_raw = _first_value(row, COL_NB_ALIASES)
            nb = int(_parse_number(nb_raw, label='Nombre de parcelles/PDF')) if nb_raw not in (None, '') else 0

            superf_raw = _first_value(row, COL_SUPERF_ALIASES)
            superficie = _parse_number(superf_raw, label='Superficie') if superf_raw not in (None, '') else 0.0
        except ValueError as exc:
            errors.append({'row': idx, 'village': village, 'message': str(exc)})
            continue

        acc = par_village.setdefault(village, {'nb_parcelles': 0, 'superficie_totale': 0.0})
        acc['nb_parcelles']      += nb
        acc['superficie_totale'] += superficie

    for acc in par_village.values():
        acc['superficie_totale'] = round(acc['superficie_totale'], 4)

    return {
        'nb_parcelles':         sum(v['nb_parcelles'] for v in par_village.values()),
        'superficie_totale':    round(sum(v['superficie_totale'] for v in par_village.values()), 4),
        'repartition_village':  par_village,
        'errors':               errors,
    }
