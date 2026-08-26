from django.db import models
from apps.dossiers.models import Dossier


def upload_to(instance, filename):
    return f'dossiers/{instance.dossier_id}/{filename}'


def upload_excel_to(instance, filename):
    return f'publicite/excel/{instance.village_id}/{filename}'


class FichierDossier(models.Model):
    TYPE_CHOICES = [
        ('PLAN',          'Plan'),
        ('PV',            'Procès-verbal'),
        ('PHOTO',         'Photo'),
        ('DOCUMENT',      'Document'),
        ('RAPPORT',       'Rapport'),
        ('AUTRE',         'Autre'),
    ]
    dossier      = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='fichiers')
    nom          = models.CharField(max_length=255)
    type_fichier = models.CharField(max_length=20, choices=TYPE_CHOICES, default='AUTRE')
    fichier      = models.FileField(upload_to=upload_to)
    taille       = models.PositiveIntegerField(null=True, blank=True)
    televerse_par = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fichiers_televerses',
    )
    televerse_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fichier_dossier'
        ordering = ['-televerse_le']

    def __str__(self):
        return self.nom


class FichierExcelPublicite(models.Model):
    """Fichier Excel de la liste des parcelles envoyées en publicité pour un village, rattaché
    à une vague d'envoi. L'import remplit `nb_parcelles`/`nb_crees`/`nb_maj`/`superficie_totale`/
    `erreurs` automatiquement à partir du contenu du fichier (voir
    apps.dossiers.services.importer_excel_publicite) — ces champs ne sont jamais saisis à la main."""
    village     = models.ForeignKey(
        'referentiel.Village', on_delete=models.CASCADE, related_name='excels_publicite',
    )
    vague       = models.ForeignKey(
        'dossiers.VagueEnvoi', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fichiers_excel',
    )
    nom         = models.CharField(max_length=255)
    fichier     = models.FileField(upload_to=upload_excel_to)
    taille      = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    # ── Résultat de l'import, calculé automatiquement ─────────
    nb_parcelles      = models.IntegerField(default=0)
    nb_crees          = models.IntegerField(default=0)
    nb_maj            = models.IntegerField(default=0)
    superficie_totale = models.FloatField(default=0)
    erreurs           = models.JSONField(default=list, blank=True)

    televerse_par = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='excels_televerses',
    )
    televerse_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fichier_excel_publicite'
        ordering = ['-televerse_le']

    def __str__(self):
        return self.nom
