from rest_framework import serializers
from .models import FaitAgrege, ObjectifPeriode


class FaitAgregeSerializer(serializers.ModelSerializer):
    village_nom = serializers.CharField(source='village.nom', read_only=True)
    zone_nom    = serializers.CharField(source='zone.nom',    read_only=True)

    class Meta:
        model  = FaitAgrege
        fields = [
            'id', 'village', 'village_nom', 'zone', 'zone_nom',
            'periode', 'source', 'nb_dossiers', 'nb_contrats', 'nb_cf', 'nb_anomalies',
        ]


class ObjectifPeriodeSerializer(serializers.ModelSerializer):
    zone_nom = serializers.CharField(source='zone.nom', read_only=True)

    class Meta:
        model  = ObjectifPeriode
        fields = ['id', 'zone', 'zone_nom', 'periode', 'nb_dossiers', 'nb_contrats', 'nb_cf']
