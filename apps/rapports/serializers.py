from rest_framework import serializers
from .models import RapportPeriodique


class RapportSerializer(serializers.ModelSerializer):
    zone_nom      = serializers.CharField(source='zone.nom', read_only=True)
    redige_par_nom = serializers.SerializerMethodField()
    fichier_url   = serializers.SerializerMethodField()

    class Meta:
        model  = RapportPeriodique
        fields = [
            'id', 'zone', 'zone_nom', 'periode', 'type_rapport', 'statut',
            'redige_par', 'redige_par_nom', 'fichier', 'fichier_url',
            'cree_le', 'modifie_le',
        ]

    def get_redige_par_nom(self, obj):
        if obj.redige_par:
            return f'{obj.redige_par.first_name} {obj.redige_par.last_name}'.strip()
        return None

    def get_fichier_url(self, obj):
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
        return None
