"""Import en masse de dossiers CF depuis un fichier Excel/CSV (« fichier ADS »).

Le fichier n'est pas persisté : il est lu en mémoire, ligne par ligne, chaque ligne étant traitée
dans sa propre transaction pour qu'une ligne en erreur n'annule pas les précédentes (même
philosophie que `apps/publicite/services.py` : best-effort, erreurs journalisées plutôt que tout
bloquant).
"""

import csv
import io

from django.db import transaction

from apps.referentiel.models import Village
from .models import Dossier

STATUT_CF_VALIDES = {c for c, _ in Dossier.STATUT_CF_CHOICES}

# Colonnes reconnues dans le fichier (en-têtes comparés en minuscules/strippés)
COL_NUMERO          = 'numero_dossier'
COL_VILLAGE         = 'village'
COL_SOUS_PREFECTURE = 'sous_prefecture'
COL_NUM_DEMAND      = 'num_demand'
COL_NOM_DEMANDEUR   = 'nom_demandeur'
COL_SUPERFICIE      = 'superficie_parcelle'
COL_PERIMETRE       = 'perimetre_parcelle'
COL_NOM_OTA         = 'nom_ota'
COL_N_DEMCGE        = 'n_demcge'
COL_STATUT_CF       = 'statut_cf'

FLOAT_COLS = {COL_SUPERFICIE, COL_PERIMETRE}


class ImportADSError(Exception):
    """Levée pour un problème global empêchant toute lecture du fichier (format non supporté,
    fichier vide, colonne obligatoire absente de l'en-tête)."""


def _normalize_header(h) -> str:
    return (h or '').strip().lower().replace(' ', '_')


def _read_rows(fichier):
    """Retourne une liste de dicts {colonne_normalisée: valeur} à partir d'un fichier .csv ou .xlsx."""
    name = (fichier.name or '').lower()

    if name.endswith('.csv'):
        content = fichier.read().decode('utf-8-sig', errors='replace')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
    elif name.endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            raise ImportADSError("Dépendance 'openpyxl' non installée côté serveur.")
        wb = openpyxl.load_workbook(fichier, read_only=True, data_only=True)
        ws = wb.active
        rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
    else:
        raise ImportADSError("Format de fichier non supporté — utiliser .csv ou .xlsx.")

    if not rows:
        raise ImportADSError("Fichier vide.")

    headers = [_normalize_header(h) for h in rows[0]]
    if COL_NUMERO not in headers:
        raise ImportADSError(f"Colonne obligatoire '{COL_NUMERO}' absente de l'en-tête du fichier.")

    data_rows = []
    for raw_row in rows[1:]:
        if raw_row is None or all(c in (None, '') for c in raw_row):
            continue
        rec = {}
        for i, h in enumerate(headers):
            rec[h] = raw_row[i] if i < len(raw_row) else None
        data_rows.append(rec)
    return data_rows


def _clean(value):
    if value is None:
        return ''
    return str(value).strip()


def _resolve_village(zone, village_nom, sous_prefecture=None):
    qs = Village.objects.filter(zone_id=zone.id, nom__iexact=village_nom)
    if sous_prefecture:
        qs = qs.filter(sous_prefecture__icontains=sous_prefecture)
    matches = list(qs[:2])
    if not matches:
        raise ValueError(f"Village {village_nom!r} introuvable dans la zone {zone.nom}.")
    if len(matches) > 1:
        raise ValueError(
            f"Plusieurs villages nommés {village_nom!r} dans la zone {zone.nom} — "
            f"préciser la colonne 'sous_prefecture' pour désambiguïser."
        )
    return matches[0]


def importer_fichier_ads(fichier, zone, user) -> dict:
    """Importe un fichier ADS (Excel/CSV) de dossiers CF pour une zone donnée.
    Retourne {total_rows, created, updated, errors: [{row, numero_dossier, message}]}."""
    rows = _read_rows(fichier)

    created = 0
    updated = 0
    errors: list[dict] = []

    for idx, row in enumerate(rows, start=2):  # ligne 1 = en-tête
        numero_dossier = _clean(row.get(COL_NUMERO))
        if not numero_dossier:
            errors.append({'row': idx, 'numero_dossier': None, 'message': 'numero_dossier manquant.'})
            continue

        try:
            with transaction.atomic():
                defaults = {}

                statut_cf = _clean(row.get(COL_STATUT_CF)).upper()
                if statut_cf:
                    if statut_cf not in STATUT_CF_VALIDES:
                        raise ValueError(f"statut_cf invalide : {statut_cf!r}.")
                    defaults['statut_cf'] = statut_cf

                for col, key in [
                    (COL_NUM_DEMAND, 'num_demand'), (COL_NOM_DEMANDEUR, 'nom_demandeur'),
                    (COL_NOM_OTA, 'nom_ota'), (COL_N_DEMCGE, 'n_demcge'),
                ]:
                    value = _clean(row.get(col))
                    if value:
                        defaults[key] = value

                for col, key in [(COL_SUPERFICIE, 'superficie_parcelle'), (COL_PERIMETRE, 'perimetre_parcelle')]:
                    raw = row.get(col)
                    if raw not in (None, ''):
                        try:
                            defaults[key] = float(raw)
                        except (TypeError, ValueError):
                            raise ValueError(f"Valeur numérique invalide pour {col} : {raw!r}.")

                dossier = Dossier.objects.filter(numero_dossier=numero_dossier).first()
                if dossier:
                    for k, v in defaults.items():
                        setattr(dossier, k, v)
                    dossier.save()
                    updated += 1
                else:
                    village_nom = _clean(row.get(COL_VILLAGE))
                    if not village_nom:
                        raise ValueError("village requis pour créer un nouveau dossier.")
                    village = _resolve_village(zone, village_nom, _clean(row.get(COL_SOUS_PREFECTURE)) or None)
                    Dossier.objects.create(
                        numero_dossier=numero_dossier, village=village, zone=zone,
                        type_dossier='CF', cree_par=user, **defaults,
                    )
                    created += 1
        except Exception as exc:
            errors.append({'row': idx, 'numero_dossier': numero_dossier, 'message': str(exc)})

    return {'total_rows': len(rows), 'created': created, 'updated': updated, 'errors': errors}
