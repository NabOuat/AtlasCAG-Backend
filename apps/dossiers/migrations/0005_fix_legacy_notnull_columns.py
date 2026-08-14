"""Retire la contrainte NOT NULL sur des colonnes orphelines de la table `dossier`
(numero_parcelle, superficie_declaree, agent_leveur_id, date_levee) héritées d'une ancienne
version du schéma et absentes du modèle Django actuel. Sans cette correction, aucune création
de Dossier ne peut aboutir (violation NOT NULL sur des colonnes que l'ORM ne connaît pas et ne
peuple donc jamais). Migration purement additive côté état Django (RunSQL sans opération
correspondante sur le state, ces colonnes n'étant pas modélisées) — aucune perte de données,
la table étant vide au moment de cette migration.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dossiers", "0004_alter_dossier_statut_cf"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "dossier" ALTER COLUMN "numero_parcelle" DROP NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "superficie_declaree" DROP NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "agent_leveur_id" DROP NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "date_levee" DROP NOT NULL;',
            ],
            reverse_sql=[
                'ALTER TABLE "dossier" ALTER COLUMN "date_levee" SET NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "agent_leveur_id" SET NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "superficie_declaree" SET NOT NULL;',
                'ALTER TABLE "dossier" ALTER COLUMN "numero_parcelle" SET NOT NULL;',
            ],
            state_operations=[],
        ),
    ]
