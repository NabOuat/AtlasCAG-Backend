from rest_framework import serializers
from .models import Dossier, EnqueteFonciere, Contrat, CertificationFonciere, HistoriqueStatutDossier


class DossierListSerializer(serializers.ModelSerializer):
    village_nom   = serializers.CharField(source='village.nom',  read_only=True)
    zone_nom      = serializers.CharField(source='zone.nom',     read_only=True)
    cree_par_nom  = serializers.SerializerMethodField()

    class Meta:
        model  = Dossier
        fields = [
            'id', 'numero_dossier', 'village', 'village_nom',
            'zone', 'zone_nom', 'type_dossier', 'statut',
            'cree_le', 'modifie_le', 'cree_par', 'cree_par_nom',
        ]

    def get_cree_par_nom(self, obj):
        if obj.cree_par:
            return f'{obj.cree_par.first_name} {obj.cree_par.last_name}'.strip() or obj.cree_par.username
        return None


class HistoriqueStatutSerializer(serializers.ModelSerializer):
    modifie_par_nom = serializers.SerializerMethodField()

    class Meta:
        model  = HistoriqueStatutDossier
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'modifie_par_nom', 'modifie_le', 'commentaire']

    def get_modifie_par_nom(self, obj):
        if obj.modifie_par:
            return f'{obj.modifie_par.first_name} {obj.modifie_par.last_name}'.strip()
        return None


class DossierDetailSerializer(DossierListSerializer):
    historique = HistoriqueStatutSerializer(source='historique_statuts', many=True, read_only=True)

    class Meta(DossierListSerializer.Meta):
        fields = DossierListSerializer.Meta.fields + ['historique']


class DossierCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Dossier
        fields = ['numero_dossier', 'village', 'zone', 'type_dossier', 'statut']
