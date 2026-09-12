"""Import Excel/CSV de parcelles rattachées à un village + une vague d'envoi, entrée
principale du workflow de publicité (cf. LOGIQUE_METIER_PUBLICITE.pdf §3).

Contrairement à l'import ADS (`apps.dossiers.services.importer_fichier_ads`, clé
`numero_dossier`), ce format utilise `NUM_DEMAND` comme identifiant de ligne et construit
`numero_dossier = NUM_DEMAND[-N°PARCELLE]`. Toutes les lignes doivent appartenir au village
sélectionné (vérifié via NOM_VILLAG si la colonne est présente) — une ligne divergente est
rejetée comme erreur de ligne, jamais comme échec global.

Ce que cet import ne fait jamais :
- il ne touche jamais `statut_cf` (la COUCHE PostGIS n'est déplacée que par le workflow de
  publicité, apps.publicite) ;
- il ne fait passer `statut_publicite` à EN_PUBLICITE que pour un dossier qui n'en a encore
  aucun — jamais pour rembobiner une progression déjà entamée.
"""

import io
import re

STATUT_PUBLICITE_INITIAL = 'EN_PUBLICITE'

# Alias de colonnes tolérés (en-têtes comparés en majuscules/strippés, espaces->underscore)
ALIAS_NUM_DEMAND     = {'NUM_DEMAND'}
ALIAS_SUPERF         = {'SUPERF', 'SUPERFICIE'}
ALIAS_NUMERO_PARCELLE = {'N°_PARCELLE', 'N_PARCELLE', 'NUM_PARCELLE', 'NUMERO_PARCELLE', 'CODE_PARCELLE'}
ALIAS_NOM_VILLAGE    = {'NOM_VILLAG', 'NOM_VILLAGE'}
ALIAS_NOM_DEMANDEUR  = {'NOM_DEMAND', 'NOM_DEMANDEUR'}
ALIAS_NOM_CE         = {'NOM_DE_CE', 'NOM_CE'}
ALIAS_OBSERVATION    = {'OBSERVATION', 'OBSERVATIONS'}

_IGNORABLE_IDENTIFIERS = {'', 'TOTAL', 'TOTAUX', 'TOTAL GENERAL', 'TOTAL GÉNÉRAL'}


class ImportExcelPubliciteError(Exception):
    """Levée pour un problème global empêchant toute lecture du fichier (format non supporté,
    fichier vide, colonne NUM_DEMAND absente de l'en-tête)."""


def _normalize_header(h) -> str:
    h = (h or '').strip().upper()
    h = re.sub(r'\s+', '_', h)
    return h


def _read_rows(fichier):
    """Retourne (colonnes_normalisées, liste_de_dicts) à partir d'un fichier .csv/.xls/.xlsx."""
    name = (fichier.name or '').lower()

    if name.endswith('.csv'):
        import csv
        content = fichier.read().decode('utf-8-sig', errors='replace')
        rows = list(csv.reader(io.StringIO(content)))
    elif name.endswith(('.xlsx', '.xls')):
        try:
            import openpyxl
        except ImportError:
            raise ImportExcelPubliciteError("Dépendance 'openpyxl' non installée côté serveur.")
        wb = openpyxl.load_workbook(fichier, read_only=True, data_only=True)
        ws = wb.active
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
    else:
        raise ImportExcelPubliciteError("Format de fichier non supporté — utiliser .csv, .xls ou .xlsx.")

    if not rows:
        raise ImportExcelPubliciteError("Fichier vide.")

    headers = [_normalize_header(h) for h in rows[0]]
    if not (set(headers) & ALIAS_NUM_DEMAND):
        raise ImportExcelPubliciteError("Colonne obligatoire 'NUM_DEMAND' absente de l'en-tête du fichier.")

    data_rows = []
    for raw_row in rows[1:]:
        if raw_row is None or all(c in (None, '') for c in raw_row):
            continue
        rec = {headers[i]: (raw_row[i] if i < len(raw_row) else None) for i in range(len(headers))}
        data_rows.append(rec)
    return data_rows


def _clean(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _get_alias(row, aliases):
    for key in aliases:
        if key in row:
            return row[key]
    return None


def importer_excel_publicite(*, fichier, village, vague_envoi, user) -> dict:
    """Importe un fichier Excel/CSV de parcelles pour `village`, les rattache à `vague_envoi`.
    Retourne un résumé : {nb_parcelles, superficie_totale, nb_crees, nb_maj, erreurs: [...]}."""
    from apps.dossiers.models import Dossier

    rows = _read_rows(fichier)

    nb_parcelles      = 0
    superficie_totale = 0.0
    nb_crees          = 0
    nb_maj            = 0
    erreurs: list[dict] = []

    for idx, row in enumerate(rows, start=2):  # ligne 1 = en-tête
        num_demand = _clean(_get_alias(row, ALIAS_NUM_DEMAND))

        if num_demand.upper() in _IGNORABLE_IDENTIFIERS:
            erreurs.append({'row': idx, 'message': 'Ligne ignorée (récapitulatif ou identifiant manquant).'})
            continue

        nom_villag = _clean(_get_alias(row, ALIAS_NOM_VILLAGE))
        if nom_villag and nom_villag.upper() != village.nom.strip().upper():
            erreurs.append({
                'row': idx,
                'message': f"Village incohérent : {nom_villag!r} ne correspond pas au village sélectionné ({village.nom!r}).",
            })
            continue

        superf_raw = _get_alias(row, ALIAS_SUPERF)
        try:
            superficie = float(str(superf_raw).replace(',', '.')) if superf_raw not in (None, '') else None
        except (TypeError, ValueError):
            erreurs.append({'row': idx, 'message': f"Superficie illisible : {superf_raw!r}."})
            continue
        if superficie is None:
            erreurs.append({'row': idx, 'message': "SUPERF manquant."})
            continue

        numero_parcelle = _clean(_get_alias(row, ALIAS_NUMERO_PARCELLE))
        numero_dossier  = f'{num_demand}-{numero_parcelle}' if numero_parcelle else num_demand

        defaults = {'superficie_parcelle': superficie}
        nom_demandeur = _clean(_get_alias(row, ALIAS_NOM_DEMANDEUR))
        if nom_demandeur: defaults['nom_demandeur'] = nom_demandeur
        nom_ce = _clean(_get_alias(row, ALIAS_NOM_CE))
        if nom_ce: defaults['nom_ce'] = nom_ce
        observation = _clean(_get_alias(row, ALIAS_OBSERVATION))
        if observation: defaults['observation'] = observation
        if numero_parcelle: defaults['numero_parcelle'] = numero_parcelle

        try:
            dossier = Dossier.objects.filter(numero_dossier=numero_dossier).first()
            if dossier:
                for k, v in defaults.items():
                    setattr(dossier, k, v)
                dossier.vague_envoi = vague_envoi
                # Ne jamais rembobiner une progression déjà entamée (Approuvée/Rejetée/Validée).
                if not dossier.statut_publicite:
                    dossier.statut_publicite = STATUT_PUBLICITE_INITIAL
                dossier.save()
                nb_maj += 1
            else:
                Dossier.objects.create(
                    numero_dossier=numero_dossier, num_demand=num_demand,
                    village=village, zone=village.zone, type_dossier='CF',
                    vague_envoi=vague_envoi, statut_publicite=STATUT_PUBLICITE_INITIAL,
                    cree_par=user, **defaults,
                )
                nb_crees += 1
        except Exception as exc:
            erreurs.append({'row': idx, 'message': str(exc)})
            continue

        nb_parcelles += 1
        superficie_totale += superficie

    return {
        'nb_parcelles':      nb_parcelles,
        'superficie_totale': round(superficie_totale, 2),
        'nb_crees':          nb_crees,
        'nb_maj':            nb_maj,
        'erreurs':           erreurs,
    }
