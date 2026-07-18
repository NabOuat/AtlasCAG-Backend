from rest_framework import serializers
from .models import Zone, Region, Departement, SousPrefecture, Village


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Zone
        fields = ['id', 'nom', 'code', 'type']


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Region
        fields = ['id', 'nom', 'code']


class SousPrefectureSerializer(serializers.ModelSerializer):
    departement_nom = serializers.CharField(source='departement.nom', read_only=True)

    class Meta:
        model  = SousPrefecture
        fields = ['id', 'nom', 'departement', 'departement_nom']


class VillageListSerializer(serializers.ModelSerializer):
    zone_nom           = serializers.CharField(source='zone.nom',  read_only=True)
    sous_prefecture_nom = serializers.SerializerMethodField()

    # DTV progress: étapes complétées / 7
    dtv_progress = serializers.SerializerMethodField()
    dtv_etape    = serializers.SerializerMethodField()

    class Meta:
        model  = Village
        fields = [
            'id', 'nom', 'zone', 'zone_nom', 'sous_prefecture', 'sous_prefecture_nom',
            'latitude', 'longitude',
            'recueil_historique_fait', 'layons_identifies', 'pv_constat_signes',
            'delimite', 'publicite_ouverte', 'publicite_cloturee', 'approuve', 'valide',
            'dtv_progress', 'dtv_etape',
        ]

    def get_sous_prefecture_nom(self, obj):
        if obj.sous_prefecture_fk:
            return obj.sous_prefecture_fk.nom
        return obj.sous_prefecture

    def get_dtv_progress(self, obj):
        bools = [
            obj.recueil_historique_fait,
            bool(obj.layons_identifies),
            bool(obj.pv_constat_signes),
            obj.delimite,
            obj.publicite_ouverte,
            obj.publicite_cloturee,
            obj.approuve,
            obj.valide,
        ]
        return sum(bools)

    def get_dtv_etape(self, obj):
        if obj.valide:            return 'VALIDE'
        if obj.approuve:          return 'APPROUVE'
        if obj.publicite_cloturee: return 'PUB_CLOTUREE'
        if obj.publicite_ouverte:  return 'PUB_OUVERTE'
        if obj.delimite:           return 'DELIMITE'
        if obj.pv_constat_signes:  return 'PV_SIGNES'
        if obj.layons_identifies:  return 'LAYONS'
        if obj.recueil_historique_fait: return 'RECUEIL'
        return 'NON_DEMARRE'
