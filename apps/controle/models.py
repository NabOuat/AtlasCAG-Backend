from django.db import models
from apps.dossiers.models import Dossier


class ControleQualite(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE',  'En attente'),
        ('EN_COURS',    'En cours'),
        ('VALIDE',      'Validé'),
        ('REJETE',      'Rejeté'),
    ]
    dossier         = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='controles')
    controleur      = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='controles_effectues',
    )
    date_controle   = models.DateTimeField(null=True, blank=True)
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    observations    = models.TextField(blank=True)
    cree_le         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'controle_qualite'
        ordering = ['-cree_le']


class AnomalieControle(models.Model):
    GRAVITE_CHOICES = [
        ('BLOQUANTE', 'Bloquante'),
        ('MAJEURE',   'Majeure'),
        ('MINEURE',   'Mineure'),
    ]
    controle        = models.ForeignKey(ControleQualite, on_delete=models.CASCADE, related_name='anomalies')
    description     = models.TextField()
    gravite         = models.CharField(max_length=20, choices=GRAVITE_CHOICES)
    corrigee        = models.BooleanField(default=False)
    date_correction = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'anomalie_controle'


class EnvoiEntreprise(models.Model):
    PLATEFORME_CHOICES = [
        ('SCCARTO',  'SCCARTO'),
        ('DIGIFOR',  'DIGIFOR'),
        ('SIFOR',    'SIFOR'),
    ]
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('ENVOYE',     'Envoyé'),
        ('CONFIRME',   'Confirmé'),
        ('REJETE',     'Rejeté'),
    ]
    dossier    = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='envois')
    plateforme = models.CharField(max_length=10, choices=PLATEFORME_CHOICES)
    statut     = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    envoye_par = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='envois_effectues',
    )
    envoye_le  = models.DateTimeField(null=True, blank=True)
    reference  = models.CharField(max_length=100, blank=True)
    observations = models.TextField(blank=True)

    class Meta:
        db_table = 'envoi_entreprise'
