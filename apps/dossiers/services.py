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


def _read_rows(fichier, required=(COL_NUMERO,)):
    """Retourne une liste de dicts {colonne_normalisée: valeur} à partir d'un fichier .csv ou .xlsx.
    Lève `ImportADSError` si l'une des colonnes de `required` (déjà normalisées) est absente
    de l'en-tête."""
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
    missing = [c for c in required if c not in headers]
    if missing:
        raise ImportADSError(
            f"Colonne(s) obligatoire(s) absente(s) de l'en-tête du fichier : {', '.join(missing)}."
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


# ─────────────────────────────────────────────────────────────────────────────
# Import du fichier Excel « parcelles envoyées en publicité » (module Publicité)
# ─────────────────────────────────────────────────────────────────────────────
# Une ligne = une parcelle. En-têtes réelles observées (fichiers DigiFor/SCCarto) :
# N°, NOM_REGION, NOM_DEPART, NOM_SSPREF, NOM_VILLAG, NOM_DEMAND, NUM_DEMAND, SUPERF,
# N° PARCELLE, NOM DE CE, OBSERVATION — plus une ligne récapitulative 'TOTAL' à ignorer.

PUB_COL_VILLAGE    = 'nom_villag'
PUB_COL_NOM_DEMAND = 'nom_demand'
PUB_COL_NUM_DEMAND = 'num_demand'
PUB_COL_SUPERF     = 'superf'
PUB_COL_NOM_CE     = 'nom_de_ce'
PUB_COL_OBSERVATION = 'observation'
# Alias de la colonne 'N° PARCELLE' — le caractère '°' varie selon l'outil d'export.
PUB_COL_PARCELLE_ALIASES = ['n°_parcelle', 'n_parcelle', 'num_parcelle', 'numero_parcelle', 'code_parcelle']


def _first_value(row: dict, keys: list[str]):
    for k in keys:
        if k in row:
            return row[k]
    return None


def importer_excel_publicite(fichier, zone, village, vague, user) -> dict:
    """Importe le fichier Excel des parcelles envoyées en publicité pour `village` (une ligne =
    une parcelle), rattache chaque parcelle à `vague`, et crée/complète les `Dossier`
    correspondants sans dupliquer : upsert par `num_demand`, en construisant un `numero_dossier`
    unique à partir de NUM_DEMAND (+ N° PARCELLE quand une même demande couvre plusieurs
    parcelles). Les lignes 'TOTAL' (récapitulatif) sont ignorées.

    Ne modifie JAMAIS `statut_cf` (la COUCHE, reflet exact de la table PostGIS où vit
    physiquement la géométrie de la parcelle) : cette transition reste exclusivement réservée
    au workflow dédié (apps.publicite.services.migrer_parcelle, déclenché par l'action
    explicite « Mettre en publicité »), qui migre la géométrie PostGIS en conséquence — un
    import Excel qui basculerait `statut_cf` directement mentirait sur l'emplacement réel de la
    parcelle (elle resterait dans la couche Définitif alors que la COUCHE affichée dirait
    « En publicité »). Tout dossier importé démarre donc `statut_cf` vide, c'est-à-dire
    Définitif (`resolveStatut` côté frontend traite vide comme `DEF`, et `MettreEnPubliciteView`
    accepte explicitement `None`/`''`/`'DEF'` comme état de départ).

    En revanche `statut_publicite` (état métier/administratif du dossier dans le circuit
    publicité, indépendant de la COUCHE) démarre bien à `EN_PUBLICITE` dès qu'un dossier
    nouvellement créé ou un dossier CF préexistant (import ADS) est rattaché à une vague pour
    la première fois — mais jamais si un `statut_publicite` est déjà renseigné, pour ne pas
    rembobiner une progression déjà faite (Approuvée/Rejetée/Validée).

    Retourne {total_rows, created, updated, nb_parcelles, superficie_totale, errors}."""
    if vague.zone_id != zone.id:
        raise ImportADSError("La vague sélectionnée n'appartient pas à la même zone que le village.")

    rows = _read_rows(fichier, required=[PUB_COL_NUM_DEMAND, PUB_COL_SUPERF])

    created = 0
    updated = 0
    errors: list[dict] = []
    superficie_totale = 0.0

    for idx, row in enumerate(rows, start=2):  # ligne 1 = en-tête
        if any(_clean(v).upper() == 'TOTAL' for v in row.values()):
            continue  # ligne récapitulative

        num_demand = _clean(row.get(PUB_COL_NUM_DEMAND))
        if not num_demand:
            continue  # ligne vide / non exploitable, pas une erreur en soi

        n_parcelle     = _clean(_first_value(row, PUB_COL_PARCELLE_ALIASES))
        numero_dossier = f"{num_demand}-{n_parcelle}" if n_parcelle else num_demand

        try:
            with transaction.atomic():
                row_village = _clean(row.get(PUB_COL_VILLAGE))
                if row_village and row_village.lower() != village.nom.lower():
                    raise ValueError(
                        f"Le village de la ligne ({row_village!r}) ne correspond pas au village "
                        f"sélectionné ({village.nom!r})."
                    )

                defaults = {'vague_envoi': vague}
                if n_parcelle:
                    defaults['numero_parcelle'] = n_parcelle

                nom_demandeur = _clean(row.get(PUB_COL_NOM_DEMAND))
                if nom_demandeur:
                    defaults['nom_demandeur'] = nom_demandeur

                nom_ce = _clean(row.get(PUB_COL_NOM_CE))
                if nom_ce:
                    defaults['nom_ce'] = nom_ce

                observation = _clean(row.get(PUB_COL_OBSERVATION))
                if observation:
                    defaults['observation'] = observation

                superficie = None
                raw_superf = row.get(PUB_COL_SUPERF)
                if raw_superf not in (None, ''):
                    try:
                        superficie = float(raw_superf)
                    except (TypeError, ValueError):
                        raise ValueError(f"Superficie invalide : {raw_superf!r}.")
                    defaults['superficie_parcelle'] = superficie

                dossier = Dossier.objects.filter(num_demand=num_demand).first()
                if not dossier and numero_dossier != num_demand:
                    dossier = Dossier.objects.filter(numero_dossier=numero_dossier).first()

                if dossier:
                    for k, v in defaults.items():
                        setattr(dossier, k, v)
                    if not dossier.statut_publicite:
                        # Dossier CF préexistant (import ADS) qui entre pour la première fois
                        # dans le circuit publicité via cet import — même bascule que pour un
                        # dossier nouvellement créé ci-dessous, jamais appliquée s'il a déjà un
                        # statut_publicite (on ne rembobine jamais une progression déjà faite).
                        # `statut_cf` (COUCHE) n'est volontairement jamais touché ici.
                        dossier.statut_publicite = 'EN_PUBLICITE'
                    dossier.save()
                    updated += 1
                else:
                    Dossier.objects.create(
                        numero_dossier=numero_dossier, num_demand=num_demand,
                        village=village, zone=zone, type_dossier='CF',
                        statut_publicite='EN_PUBLICITE',
                        cree_par=user, **defaults,
                    )
                    created += 1

                if superficie is not None:
                    superficie_totale += superficie
        except Exception as exc:
            errors.append({'row': idx, 'num_demand': num_demand, 'message': str(exc)})

    return {
        'total_rows':        len(rows),
        'created':           created,
        'updated':           updated,
        'nb_parcelles':      created + updated,
        'superficie_totale': round(superficie_totale, 4),
        'errors':            errors,
    }
