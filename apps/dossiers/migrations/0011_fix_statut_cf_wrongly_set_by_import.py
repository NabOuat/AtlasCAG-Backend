# Corrige la COUCHE (`statut_cf`) des dossiers dont le seul « historique » est un import
# Excel-publicité : les migrations 0009/0010 et `importer_excel_publicite` (avant correctif)
# faisaient passer `statut_cf` à `EN_PUBLICITE` dès l'import, alors que la géométrie de la
# parcelle n'a jamais été migrée dans PostGIS (aucune trace dans HistoriqueMigrationCouche).
# La COUCHE affichée mentait donc sur l'emplacement physique réel de la parcelle (toujours
# dans la table Définitif) et empêchait l'action « Mettre en publicité » de s'afficher.
#
# Remet `statut_cf` à vide (= Définitif) pour tout dossier actuellement `EN_PUBLICITE` qui n'a
# aucune migration réussie historisée vers ce statut — ne touche jamais un dossier dont la
# transition a réellement eu lieu (traçable dans HistoriqueMigrationCouche), ni `statut_publicite`
# (état métier du circuit publicité, volontairement distinct et non concerné par ce correctif).
from django.db import migrations


def fix_statut_cf(apps, schema_editor):
    Dossier = apps.get_model('dossiers', 'Dossier')
    HistoriqueMigrationCouche = apps.get_model('publicite', 'HistoriqueMigrationCouche')

    candidats = Dossier.objects.filter(statut_cf='EN_PUBLICITE')
    migres_reellement = set(
        HistoriqueMigrationCouche.objects.filter(
            dossier__in=candidats, succes=True, nouveau_statut='EN_PUBLICITE',
        ).values_list('dossier_id', flat=True)
    )
    candidats.exclude(id__in=migres_reellement).update(statut_cf=None)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dossiers', '0010_backfill_statut_publicite_vague'),
        ('publicite', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_statut_cf, noop_reverse),
    ]
