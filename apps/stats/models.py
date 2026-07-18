from django.db import models
from apps.referentiel.models import Village, Zone


class FaitAgrege(models.Model):
    SOURCE_CHOICES = [
        ('TERRAIN', 'Terrain'),
        ('SIFOR',   'SIFOR'),
        ('DIGIFOR', 'DIGIFOR'),
    ]
    village         = models.ForeignKey(Village, on_delete=models.CASCADE, related_name='faits')
    zone            = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='faits')
    periode         = models.CharField(max_length=7, help_text='Format YYYY-MM')
    source          = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='TERRAIN')
    nb_dossiers     = models.IntegerField(default=0)
    nb_contrats     = models.IntegerField(default=0)
    nb_cf           = models.IntegerField(default=0)
    nb_anomalies    = models.IntegerField(default=0)
    cree_le         = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fait_agrege'
        constraints = [
            models.UniqueConstraint(
                fields=['village', 'zone', 'periode', 'source'],
                name='uix_fait_agrege',
            )
        ]


class ObjectifPeriode(models.Model):
    zone          = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='objectifs')
    periode       = models.CharField(max_length=7, help_text='Format YYYY-MM')
    nb_dossiers   = models.IntegerField(default=0)
    nb_contrats   = models.IntegerField(default=0)
    nb_cf         = models.IntegerField(default=0)

    class Meta:
        db_table = 'objectif_periode'
        unique_together = ('zone', 'periode')


class SyncApi(models.Model):
    SOURCE_CHOICES = [
        ('SIFOR',   'SIFOR'),
        ('DIGIFOR', 'DIGIFOR'),
    ]
    STATUT_CHOICES = [
        ('SUCCES',  'Succès'),
        ('ECHEC',   'Échec'),
        ('EN_COURS', 'En cours'),
    ]
    source          = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    statut          = models.CharField(max_length=10, choices=STATUT_CHOICES)
    lance_le        = models.DateTimeField(auto_now_add=True)
    termine_le      = models.DateTimeField(null=True, blank=True)
    nb_records      = models.IntegerField(default=0)
    message_erreur  = models.TextField(blank=True)

    class Meta:
        db_table = 'sync_api'
        ordering = ['-lance_le']
