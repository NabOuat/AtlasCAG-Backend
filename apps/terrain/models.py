from django.db import models
from apps.referentiel.models import Village
from apps.dossiers.models import Dossier


class PlanningASFJournalier(models.Model):
    TYPE_ACTIVITE_CHOICES = [
        ('LEVE',     'Levé GNSS'),
        ('ENQUETE',  'Enquête foncière'),
        ('CONTRAT',  'Rédaction contrat'),
        ('REUNION',  'Réunion'),
        ('AUTRE',    'Autre'),
    ]
    asf           = models.ForeignKey(
        'accounts.Utilisateur', on_delete=models.CASCADE, related_name='plannings',
    )
    village       = models.ForeignKey(Village, on_delete=models.RESTRICT, related_name='plannings')
    date_activite = models.DateField()
    heure_debut   = models.TimeField(null=True, blank=True)
    heure_fin     = models.TimeField(null=True, blank=True)
    type_activite = models.CharField(max_length=20, choices=TYPE_ACTIVITE_CHOICES)
    lieu          = models.CharField(max_length=255, blank=True)
    observations  = models.TextField(blank=True)

    class Meta:
        db_table = 'planning_asf_journalier'
        ordering = ['date_activite', 'heure_debut']


class FormulairesTerrain(models.Model):
    TYPE_CHOICES = [
        ('LEVE',    'Levé'),
        ('ENQUETE', 'Enquête'),
        ('CONTRAT', 'Contrat'),
        ('AUTRE',   'Autre'),
    ]
    dossier        = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='formulaires')
    type_formulaire = models.CharField(max_length=20, choices=TYPE_CHOICES)
    data           = models.JSONField(default=dict)
    soumis_par     = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='formulaires_soumis',
    )
    soumis_le      = models.DateTimeField(auto_now_add=True)
    synchro        = models.BooleanField(default=False)

    class Meta:
        db_table = 'formulaire_terrain'
        ordering = ['-soumis_le']


class Layon(models.Model):
    village      = models.ForeignKey(Village, on_delete=models.CASCADE, related_name='layons')
    identifiant  = models.CharField(max_length=30)
    description  = models.TextField(blank=True)
    cree_le      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'layon'
        unique_together = ('village', 'identifiant')

    def __str__(self):
        return f'{self.village} – {self.identifiant}'


class ActiviteISF(models.Model):
    TYPE_CHOICES = [
        ('ISF',   'ISF'),
        ('AUTRE', 'Autre'),
    ]
    dossier       = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='activites_isf')
    type_activite = models.CharField(max_length=20, choices=TYPE_CHOICES, default='ISF')
    date_activite = models.DateField()
    realise_par   = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='activites_isf_realisees',
    )
    observations  = models.TextField(blank=True)
    valide        = models.BooleanField(default=False)

    class Meta:
        db_table = 'activite_isf'
        ordering = ['-date_activite']
