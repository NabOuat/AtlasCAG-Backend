from rest_framework import serializers
from .models import ControleQualite, AnomalieControle, EnvoiEntreprise


class AnomalieSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AnomalieControle
        fields = ['id', 'description', 'gravite', 'corrigee', 'date_correction']


class ControleListSerializer(serializers.ModelSerializer):
    dossier_numero  = serializers.CharField(source='dossier.numero_dossier', read_only=True)
    village_nom     = serializers.CharField(source='dossier.village.nom',    read_only=True)
    zone_nom        = serializers.CharField(source='dossier.zone.nom',       read_only=True)
    controleur_nom  = serializers.SerializerMethodField()
    nb_anomalies    = serializers.SerializerMethodField()

    class Meta:
        model  = ControleQualite
        fields = [
            'id', 'dossier', 'dossier_numero', 'village_nom', 'zone_nom',
            'controleur', 'controleur_nom', 'date_controle', 'statut',
            'observations', 'cree_le', 'nb_anomalies',
        ]

    def get_controleur_nom(self, obj):
        if obj.controleur:
            return f'{obj.controleur.first_name} {obj.controleur.last_name}'.strip()
        return None

    def get_nb_anomalies(self, obj):
        return obj.anomalies.count()


class ControleDetailSerializer(ControleListSerializer):
    anomalies = AnomalieSerializer(many=True, read_only=True)

    class Meta(ControleListSerializer.Meta):
        fields = ControleListSerializer.Meta.fields + ['anomalies']


class EnvoiSerializer(serializers.ModelSerializer):
    dossier_numero = serializers.CharField(source='dossier.numero_dossier', read_only=True)
    envoye_par_nom = serializers.SerializerMethodField()

    class Meta:
        model  = EnvoiEntreprise
        fields = [
            'id', 'dossier', 'dossier_numero', 'plateforme', 'statut',
            'envoye_par', 'envoye_par_nom', 'envoye_le', 'reference', 'observations',
        ]

    def get_envoye_par_nom(self, obj):
        if obj.envoye_par:
            return f'{obj.envoye_par.first_name} {obj.envoye_par.last_name}'.strip()
        return None
