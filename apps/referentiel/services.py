"""Import en masse de la hiérarchie administrative Région → Département → Sous-préfecture →
Village depuis un fichier Excel/CSV (ex. `village.xlsx`), pour peupler le référentiel une fois
la base vide, ou le compléter/corriger via des ré-imports successifs.

Même philosophie que les autres imports du projet (apps.dossiers.services,
apps.publicite... non, apps.dossiers uniquement) : lecture en mémoire, traitement ligne par
ligne dans sa propre transaction (une ligne en erreur n'annule pas les précédentes), résultat
qui liste les erreurs plutôt que de tout bloquer.

Support d'un mode « dry_run » : exécute exactement la même logique dans une transaction qui est
toujours annulée à la fin, pour permettre un aperçu fiable côté frontend avant confirmation.
"""

import csv
import io

from django.db import transaction

from .models import Zone, Region, Departement, SousPrefecture, Village

COL_REGION      = 'region'
COL_CD_REG      = 'cd_reg'
COL_DEPARTEMENT = 'departement'
COL_CD_DPT      = 'cd_dpt'
COL_SOUS_PREF   = 'sous_prefecture'
COL_CD_SP       = 'cd_sp'
COL_VILLAGE     = 'village'
COL_CD_VIL      = 'cd_vil'

REQUIRED_COLS = [COL_REGION, COL_DEPARTEMENT, COL_SOUS_PREF, COL_VILLAGE]
CODE_COLS     = [COL_CD_REG, COL_CD_DPT, COL_CD_SP, COL_CD_VIL]


class ImportHierarchieError(Exception):
    """Levée pour un problème global empêchant toute lecture du fichier (format non supporté,
    fichier vide, colonne obligatoire absente de l'en-tête)."""


def _normalize_header(h) -> str:
    return (h or '').strip().lower().replace(' ', '_').replace('-', '_')


def _clean(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _read_rows(fichier):
    """Retourne une liste de dicts {colonne_normalisée: valeur brute} à partir d'un .csv ou .xlsx.
    Les colonnes dérivées éventuelles du fichier (ex. SP_VIL, CD_SP_VIL) sont lues comme les
    autres mais ignorées par `importer_hierarchie` — elles sont recalculables et non stockées."""
    name = (fichier.name or '').lower()

    if name.endswith('.csv'):
        content = fichier.read().decode('utf-8-sig', errors='replace')
        rows = list(csv.reader(io.StringIO(content)))
    elif name.endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            raise ImportHierarchieError("Dépendance 'openpyxl' non installée côté serveur.")
        wb = openpyxl.load_workbook(fichier, read_only=True, data_only=True)
        ws = wb.active
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
    else:
        raise ImportHierarchieError("Format de fichier non supporté — utiliser .csv ou .xlsx.")

    if not rows:
        raise ImportHierarchieError("Fichier vide.")

    headers = [_normalize_header(h) for h in rows[0]]
    missing = [c for c in REQUIRED_COLS if c not in headers]
    if missing:
        raise ImportHierarchieError(
            f"Colonne(s) obligatoire(s) absente(s) de l'en-tête du fichier : {', '.join(missing)}. "
            f"Colonnes attendues (au minimum) : REGION, DEPARTEMENT, SOUS-PREFECTURE, VILLAGE "
            f"(CD_REG, CD_DPT, CD_SP, CD_VIL optionnelles mais recommandées)."
        )

    data_rows = []
    for raw_row in rows[1:]:
        if raw_row is None or all(c in (None, '') for c in raw_row):
            continue
        rec = {h: (raw_row[i] if i < len(raw_row) else None) for i, h in enumerate(headers)}
        data_rows.append(rec)
    return data_rows


def _code_widths(rows):
    """Calcule, pour chaque colonne de code présente, la largeur maximale observée (en
    caractères) — sert à re-zéro-padder les codes que openpyxl a lus comme des nombres (perdant
    ainsi leurs zéros non significatifs, ex. 1 au lieu de '001') sans supposer une largeur fixe
    a priori : elle est déduite des autres valeurs du même fichier."""
    widths = {}
    for col in CODE_COLS:
        lengths = [len(_clean(r.get(col))) for r in rows if r.get(col) not in (None, '')]
        if lengths:
            widths[col] = max(lengths)
    return widths


def _code(row, col, widths) -> str:
    value = _clean(row.get(col))
    if not value:
        return ''
    width = widths.get(col)
    return value.zfill(width) if width else value


def importer_hierarchie(fichier, user, dry_run=False) -> dict:
    """Importe la hiérarchie Région → Département → Sous-préfecture → Village.

    Résolution/duplication :
    - Région : upsert par `code` s'il est fourni, sinon par `nom`.
    - Département : upsert par (`code`, région) si code fourni, sinon (`nom`, région).
    - Sous-préfecture : upsert par (`code`, département) si code fourni, sinon (`nom`, département).
    - Village : la zone opérationnelle est résolue à partir du nom de la région (`Zone.nom`) —
      si la zone n'existe pas encore, la ligne est journalisée en erreur (le village n'est PAS
      créé), les niveaux Région/Département/Sous-préfecture eux restent importés car ils n'en
      dépendent pas. On ne crée jamais de Zone automatiquement : la création d'une zone implique
      une configuration de base spatiale distincte (voir apps.geo), qui reste un acte manuel
      délibéré (Administration > Référentiel).
      Un village déjà existant (créé avant que ce référentiel ne soit peuplé, donc sans lien
      vers une SousPrefecture) est retrouvé par (zone, nom, sous_prefecture texte) et complété
      (rattachement + code) plutôt que dupliqué ; sinon il est créé.

    Retourne un résumé : {total_rows, regions, departements, sous_prefectures,
    villages_created, villages_updated, errors}."""
    rows = _read_rows(fichier)
    widths = _code_widths(rows)

    compteurs = {
        'regions_crees': 0, 'regions_maj': 0,
        'departements_crees': 0, 'departements_maj': 0,
        'sous_prefectures_creees': 0, 'sous_prefectures_maj': 0,
        'villages_crees': 0, 'villages_maj': 0,
    }
    errors: list[dict] = []

    def _run():
        for idx, row in enumerate(rows, start=2):  # ligne 1 = en-tête
            region_nom = _clean(row.get(COL_REGION))
            dept_nom   = _clean(row.get(COL_DEPARTEMENT))
            sp_nom     = _clean(row.get(COL_SOUS_PREF))
            vil_nom    = _clean(row.get(COL_VILLAGE))

            if not (region_nom and dept_nom and sp_nom and vil_nom):
                errors.append({
                    'row': idx, 'village': vil_nom or None,
                    'message': 'Région, département, sous-préfecture et village sont tous obligatoires.',
                })
                continue

            cd_reg = _code(row, COL_CD_REG, widths)
            cd_dpt = _code(row, COL_CD_DPT, widths)
            cd_sp  = _code(row, COL_CD_SP, widths)
            cd_vil = _code(row, COL_CD_VIL, widths)

            # Deux transactions distinctes et indépendantes : un échec au niveau Village (ex.
            # Zone introuvable) ne doit jamais annuler la Région/le Département/la Sous-préfecture
            # déjà résolus pour cette même ligne — ce sont des entités indépendantes de la Zone.
            try:
                with transaction.atomic():
                    # ── Région ──────────────────────────────────────
                    region = (Region.objects.filter(code=cd_reg).first() if cd_reg
                              else Region.objects.filter(nom__iexact=region_nom).first())
                    if region:
                        if region.nom != region_nom or (cd_reg and region.code != cd_reg):
                            region.nom = region_nom
                            if cd_reg:
                                region.code = cd_reg
                            region.save(update_fields=['nom', 'code'])
                            compteurs['regions_maj'] += 1
                    else:
                        region = Region.objects.create(nom=region_nom, code=cd_reg or region_nom[:20])
                        compteurs['regions_crees'] += 1

                    # ── Département ─────────────────────────────────
                    dept_qs = Departement.objects.filter(region=region)
                    dept = (dept_qs.filter(code=cd_dpt).first() if cd_dpt
                            else dept_qs.filter(nom__iexact=dept_nom).first())
                    if dept:
                        if dept.nom != dept_nom or (cd_dpt and dept.code != cd_dpt):
                            dept.nom = dept_nom
                            if cd_dpt:
                                dept.code = cd_dpt
                            dept.save(update_fields=['nom', 'code'])
                            compteurs['departements_maj'] += 1
                    else:
                        dept = Departement.objects.create(nom=dept_nom, code=cd_dpt, region=region)
                        compteurs['departements_crees'] += 1

                    # ── Sous-préfecture ──────────────────────────────
                    sp_qs = SousPrefecture.objects.filter(departement=dept)
                    sp = (sp_qs.filter(code=cd_sp).first() if cd_sp
                          else sp_qs.filter(nom__iexact=sp_nom).first())
                    if sp:
                        if sp.nom != sp_nom or (cd_sp and sp.code != cd_sp):
                            sp.nom = sp_nom
                            if cd_sp:
                                sp.code = cd_sp
                            sp.save(update_fields=['nom', 'code'])
                            compteurs['sous_prefectures_maj'] += 1
                    else:
                        sp = SousPrefecture.objects.create(nom=sp_nom, code=cd_sp, departement=dept)
                        compteurs['sous_prefectures_creees'] += 1
            except Exception as exc:
                errors.append({'row': idx, 'village': vil_nom, 'message': str(exc)})
                continue  # pas de sous-préfecture résolue -> le village ne peut pas être traité

            try:
                with transaction.atomic():
                    # ── Village (nécessite une Zone déjà existante) ──
                    zone = Zone.objects.filter(nom__iexact=region_nom).first()
                    if not zone:
                        raise ValueError(
                            f"Zone {region_nom!r} introuvable — créez-la d'abord dans "
                            f"Administration > Référentiel avant d'importer ses villages."
                        )

                    village = Village.objects.filter(
                        zone=zone, nom__iexact=vil_nom, sous_prefecture__iexact=sp_nom,
                    ).first()
                    if village:
                        changed = []
                        if village.sous_prefecture_fk_id != sp.id:
                            village.sous_prefecture_fk = sp
                            changed.append('sous_prefecture_fk')
                        if cd_vil and village.code != cd_vil:
                            village.code = cd_vil
                            changed.append('code')
                        if changed:
                            village.save(update_fields=changed)
                            compteurs['villages_maj'] += 1
                    else:
                        Village.objects.create(
                            nom=vil_nom, code=cd_vil, sous_prefecture=sp_nom,
                            sous_prefecture_fk=sp, zone=zone,
                        )
                        compteurs['villages_crees'] += 1
            except Exception as exc:
                errors.append({'row': idx, 'village': vil_nom, 'message': str(exc)})

        if dry_run:
            transaction.set_rollback(True)

    with transaction.atomic():
        _run()

    return {
        'total_rows': len(rows),
        'dry_run': dry_run,
        **compteurs,
        'errors': errors,
    }
