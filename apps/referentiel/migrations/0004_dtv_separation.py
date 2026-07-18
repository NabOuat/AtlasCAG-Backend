# Séparation Village / DTV
# Exécuter le SQL manuellement, puis : python manage.py migrate referentiel 0004 --fake

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("referentiel", "0003_village_boucle_village_cd_sp_vil_village_clas_preci_and_more"),
    ]

    operations = [
        # ── 1. Nouvelle table DTV ────────────────────────────────────────────
        migrations.CreateModel(
            name="DTV",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "village",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dtv",
                        to="referentiel.village",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("NON_DEMARRE", "Non démarré"),
                            ("EN_COURS",    "En cours"),
                            ("PROVISOIRE",  "Provisoire"),
                            ("APPROUVE",    "Approuvé"),
                            ("VALIDE",      "Validé"),
                        ],
                        default="NON_DEMARRE",
                        max_length=20,
                    ),
                ),
                ("recueil_historique_fait", models.BooleanField(default=False)),
                ("layons_identifies",       models.IntegerField(default=0)),
                ("pv_constat_signes",       models.IntegerField(default=0)),
                ("delimite",                models.BooleanField(default=False)),
                ("publicite_ouverte",       models.BooleanField(default=False)),
                ("publicite_cloturee",      models.BooleanField(default=False)),
                ("approuve",                models.BooleanField(default=False)),
                ("valide",                  models.BooleanField(default=False)),
                ("superficie",  models.FloatField(blank=True, null=True)),
                ("perimetre",   models.FloatField(blank=True, null=True)),
                ("nom_ota",     models.CharField(blank=True, max_length=100)),
                ("clas_preci",  models.CharField(blank=True, max_length=10)),
                ("prec_gnss",   models.FloatField(blank=True, null=True)),
                ("boucle",      models.CharField(blank=True, max_length=50)),
                ("cd_sp_vil",   models.CharField(blank=True, max_length=50)),
                ("point_ratt",  models.CharField(blank=True, max_length=100)),
                ("date_debut",      models.DateField(blank=True, null=True)),
                ("date_validation", models.DateField(blank=True, null=True)),
                ("cree_le",    models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "dtv"},
        ),

        # ── 2. SommetVillage : village → dtv ────────────────────────────────
        # Ajout nullable (la migration SQL peuple les données avant NOT NULL)
        migrations.AddField(
            model_name="sommetvillage",
            name="dtv",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sommets",
                to="referentiel.dtv",
            ),
        ),
        migrations.RemoveField(
            model_name="sommetvillage",
            name="village",
        ),
        # Passage NOT NULL (après migration des données en SQL)
        migrations.AlterField(
            model_name="sommetvillage",
            name="dtv",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sommets",
                to="referentiel.dtv",
            ),
        ),
        migrations.AlterModelOptions(
            name="sommetvillage",
            options={"db_table": "sommet_village", "ordering": ["dtv", "num_sommet"]},
        ),
        # Simplification de typ_sommet (suppression des choices)
        migrations.AlterField(
            model_name="sommetvillage",
            name="typ_sommet",
            field=models.CharField(blank=True, max_length=30),
        ),

        # ── 3. Village : suppression de toutes les colonnes DTV ─────────────
        # Colonnes spatiales (ajoutées par migration 0003)
        migrations.RemoveField(model_name="village", name="superficie"),
        migrations.RemoveField(model_name="village", name="perimetre"),
        migrations.RemoveField(model_name="village", name="nom_ota"),
        migrations.RemoveField(model_name="village", name="clas_preci"),
        migrations.RemoveField(model_name="village", name="prec_gnss"),
        migrations.RemoveField(model_name="village", name="boucle"),
        migrations.RemoveField(model_name="village", name="cd_sp_vil"),
        migrations.RemoveField(model_name="village", name="point_ratt"),
        # Colonnes de progression (ajoutées au modèle Python, jamais migrées → IF EXISTS en SQL)
        migrations.RemoveField(model_name="village", name="approuve"),
        migrations.RemoveField(model_name="village", name="delimite"),
        migrations.RemoveField(model_name="village", name="layons_identifies"),
        migrations.RemoveField(model_name="village", name="publicite_cloturee"),
        migrations.RemoveField(model_name="village", name="publicite_ouverte"),
        migrations.RemoveField(model_name="village", name="pv_constat_signes"),
        migrations.RemoveField(model_name="village", name="recueil_historique_fait"),
        migrations.RemoveField(model_name="village", name="valide"),
    ]
