from django.db import models
from apps.dossiers.models import Dossier


class HistoriqueMigrationCouche(models.Model):
    """Trace chaque tentative de migration d'une parcelle CF entre couches PostGIS,
    déclenchée par une transition du workflow de publicité (mettre en publicité, approuver,
    rejeter, valider). Enregistrée même en cas d'échec (`succes=False`) : la base spatiale
    (`<zone>_spatial`) et la base métier (`default`) sont deux bases Postgres physiquement
    séparées, donc aucune transaction atomique unique n'est possible entre les deux — cet
    historique est la trace nécessaire à la stratégie de cohérence « best-effort + compensation »
    retenue pour ce projet.
    """

    dossier        = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='migrations_couche')
    num_demand     = models.CharField(max_length=50, db_index=True)  # dénormalisé : clé d'identification unique côté couches PostGIS
    ancien_statut  = models.CharField(max_length=20)
    nouveau_statut = models.CharField(max_length=20)
    couche_source  = models.CharField(max_length=150, blank=True)  # "schema.table"
    couche_cible   = models.CharField(max_length=150, blank=True)  # "schema.table"
    effectue_par   = models.ForeignKey(
        'accounts.Utilisateur', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='migrations_couche_effectuees',
    )
    date_migration = models.DateTimeField(auto_now_add=True)
    succes         = models.BooleanField(default=False)
    message_erreur = models.TextField(blank=True)

    class Meta:
        db_table = 'historique_migration_couche'
        ordering = ['-date_migration']

    def __str__(self):
        etat = 'OK' if self.succes else 'ÉCHEC'
        return f"{self.num_demand} — {self.ancien_statut} → {self.nouveau_statut} [{etat}]"
