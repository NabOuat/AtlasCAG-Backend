from rest_framework import serializers
from .models import HistoriqueMigrationCouche


class HistoriqueMigrationCoucheSerializer(serializers.ModelSerializer):
    effectue_par_nom = serializers.CharField(source='effectue_par.nom_complet', read_only=True, default=None)

    class Meta:
        model  = HistoriqueMigrationCouche
        fields = [
            'id', 'dossier', 'num_demand', 'ancien_statut', 'nouveau_statut',
            'couche_source', 'couche_cible', 'effectue_par', 'effectue_par_nom',
            'date_migration', 'succes', 'message_erreur',
        ]
        read_only_fields = fields
