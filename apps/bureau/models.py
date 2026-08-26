from django.db import models
from apps.referentiel.models import Zone, Region, Departement


def upload_rapport_bureau_to(instance, filename):
    return f'bureau/{instance.date:%Y/%m}/{filename}'


class RapportBureau(models.Model):
    """Rapport journalier d'un agent bureau (traitement ZIP/Shape, édition PDF, reprise, A0…) :
    une ligne = un agent, un jour, un type de traitement, déposé via l'import de son fichier
    Excel. `nb_parcelles`/`superficie_totale`/`repartition_village` sont calculés automatiquement
    à partir du contenu du fichier (une ligne du fichier = un village) — jamais saisis à la main,
    voir apps.bureau.services.importer_rapport_bureau."""

    TYPE_CHOICES = [
        ('ZIP_SHAPE',   'Traitement ZIP / Shape'),
        ('PDF_CF',      'Édition PDF CF'),
        ('PDF_DTV',     'Édition PDF DTV'),
        ('REPRISE_CF',  'Reprise CF'),
        ('REPRISE_DTV', 'Reprise DTV'),
        ('A0_CF',       'A0 CF'),
    ]

    date        = models.DateField()
    zone        = models.ForeignKey(Zone, on_delete=models.RESTRICT, related_name='rapports_bureau')
    region      = models.ForeignKey(Region, on_delete=models.RESTRICT, related_name='rapports_bureau')
    departement = models.ForeignKey(Departement, on_delete=models.RESTRICT, related_name='rapports_bureau')
    vague       = models.ForeignKey(
        'dossiers.VagueEnvoi', null=True, blank=True,
        on_delete=models.RESTRICT, related_name='rapports_bureau',
    )
    type_traitement = models.CharField(max_length=20, choices=TYPE_CHOICES)

    agent = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.RESTRICT, related_name='rapports_bureau',
    )
    fichier = models.FileField(upload_to=upload_rapport_bureau_to, null=True, blank=True)

    nb_parcelles         = models.IntegerField(default=0)
    superficie_totale    = models.FloatField(default=0)
    repartition_village  = models.JSONField(null=True, blank=True)
    observations         = models.TextField(blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rapport_bureau'
        ordering = ['-date', '-cree_le']

    def __str__(self):
        return f'{self.get_type_traitement_display()} — {self.date}'
