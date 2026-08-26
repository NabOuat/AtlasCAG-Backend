# Backfille les dossiers CF déjà rattachés à une vague d'envoi (donc réellement passés par un
# import Excel-publicité) mais dont statut_cf/statut_publicite sont restés vides — cas des
# dossiers préexistants (import ADS) que l'import Excel a mis à jour avant la correction du
# service `importer_excel_publicite` (qui ne bascule désormais plus uniquement les dossiers
# nouvellement créés vers EN_PUBLICITE).
from django.db import migrations
from django.db.models import Q


def backfill(apps, schema_editor):
    Dossier = apps.get_model('dossiers', 'Dossier')
    Dossier.objects.filter(vague_envoi__isnull=False).filter(
        Q(statut_cf__isnull=True) | Q(statut_cf='')
    ).update(statut_cf='EN_PUBLICITE', statut_publicite='EN_PUBLICITE')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dossiers', '0009_dossier_statut_publicite'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
