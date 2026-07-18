from django.db import models
from apps.referentiel.models import Zone


class RapportPeriodique(models.Model):
    TYPE_CHOICES = [
        ('MENSUEL',    'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('ANNUEL',     'Annuel'),
    ]
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('FINALISE',  'Finalisé'),
        ('ENVOYE',    'Envoyé'),
    ]
    zone         = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='rapports')
    periode      = models.CharField(max_length=7, help_text='Format YYYY-MM')
    type_rapport = models.CharField(max_length=15, choices=TYPE_CHOICES)
    statut       = models.CharField(max_length=15, choices=STATUT_CHOICES, default='BROUILLON')
    redige_par   = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='rapports_rediges',
    )
    fichier      = models.FileField(upload_to='rapports/', null=True, blank=True)
    cree_le      = models.DateTimeField(auto_now_add=True)
    modifie_le   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rapport_periodique'
        unique_together = ('zone', 'periode', 'type_rapport')
        ordering = ['-cree_le']

    def __str__(self):
        return f'{self.type_rapport} {self.periode} – {self.zone}'
