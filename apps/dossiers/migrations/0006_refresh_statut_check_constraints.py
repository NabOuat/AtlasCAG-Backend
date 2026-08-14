"""Remplace deux contraintes CHECK obsolètes sur `dossier`, héritées d'un ancien schéma et
désynchronisées des choix Django actuels :
- `ck_statut_dossier` n'autorisait que d'anciens statuts (LEVE, EN_CONTROLE, CONTROLE_OK, ...),
  aucun ne correspondant à `Dossier.STATUT_CHOICES` actuel — bloquait toute création de dossier.
- `dossier_statut_cf_check` n'autorisait pas APPROUVE/VALIDE — aurait bloqué le workflow de
  publicité (apps.publicite) dès qu'un dossier réel existerait.

Les nouvelles contraintes reflètent exactement `Dossier.STATUT_CHOICES` et
`Dossier.STATUT_CF_CHOICES`. Aucune perte de données : la table était vide au moment de cette
migration.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dossiers", "0005_fix_legacy_notnull_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "dossier" DROP CONSTRAINT IF EXISTS "ck_statut_dossier";',
                (
                    'ALTER TABLE "dossier" ADD CONSTRAINT "ck_statut_dossier" '
                    "CHECK (statut IN ('EN_COURS', 'VALIDE', 'REJETE', 'ARCHIVE', 'ANNULE'));"
                ),
                'ALTER TABLE "dossier" DROP CONSTRAINT IF EXISTS "dossier_statut_cf_check";',
                (
                    'ALTER TABLE "dossier" ADD CONSTRAINT "dossier_statut_cf_check" '
                    "CHECK (statut_cf IS NULL OR statut_cf IN "
                    "('LEVE', 'PROV', 'EN_PUBLICITE', 'APRES_PUBLICITE', 'DEF', 'APPROUVE', 'VALIDE', 'REJETE'));"
                ),
            ],
            reverse_sql=[
                'ALTER TABLE "dossier" DROP CONSTRAINT IF EXISTS "dossier_statut_cf_check";',
                (
                    'ALTER TABLE "dossier" ADD CONSTRAINT "dossier_statut_cf_check" '
                    "CHECK (statut_cf IS NULL OR statut_cf IN "
                    "('LEVE', 'PROV', 'EN_PUBLICITE', 'APRES_PUBLICITE', 'DEF', 'REJETE'));"
                ),
                'ALTER TABLE "dossier" DROP CONSTRAINT IF EXISTS "ck_statut_dossier";',
                (
                    'ALTER TABLE "dossier" ADD CONSTRAINT "ck_statut_dossier" '
                    "CHECK (statut IN ('LEVE', 'EN_CONTROLE', 'CONTROLE_OK', 'CONTROLE_REJETE', "
                    "'EN_ENQUETE', 'ENQUETE_OK', 'EN_CONTRAT', 'CONTRACTUALISE', "
                    "'EN_CERTIFICATION', 'PUBLIE', 'CERTIFIE'));"
                ),
            ],
            state_operations=[],
        ),
    ]
