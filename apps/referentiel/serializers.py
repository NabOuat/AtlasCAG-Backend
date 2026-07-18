from rest_framework import serializers
from .models import Zone, Region, SousPrefecture, Village


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
    zone_nom            = serializers.CharField(source='zone.nom', read_only=True)
    sous_prefecture_nom = serializers.SerializerMethodField()

    # Champs DTV — lus via la relation OneToOne Village.dtv
    recueil_historique_fait = serializers.SerializerMethodField()
    layons_identifies       = serializers.SerializerMethodField()
    pv_constat_signes       = serializers.SerializerMethodField()
    delimite                = serializers.SerializerMethodField()
    publicite_ouverte       = serializers.SerializerMethodField()
    publicite_cloturee      = serializers.SerializerMethodField()
    approuve                = serializers.SerializerMethodField()
    valide                  = serializers.SerializerMethodField()

    # DTV progress: étapes complétées / 8
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

    def _dtv(self, obj):
        try:
            return obj.dtv
        except Exception:
            return None

    def get_sous_prefecture_nom(self, obj) -> str | None:
        if obj.sous_prefecture_fk:
            return obj.sous_prefecture_fk.nom
        return obj.sous_prefecture

    def get_recueil_historique_fait(self, obj) -> bool:
        d = self._dtv(obj); return d.recueil_historique_fait if d else False

    def get_layons_identifies(self, obj) -> int:
        d = self._dtv(obj); return d.layons_identifies if d else 0

    def get_pv_constat_signes(self, obj) -> int:
        d = self._dtv(obj); return d.pv_constat_signes if d else 0

    def get_delimite(self, obj) -> bool:
        d = self._dtv(obj); return d.delimite if d else False

    def get_publicite_ouverte(self, obj) -> bool:
        d = self._dtv(obj); return d.publicite_ouverte if d else False

    def get_publicite_cloturee(self, obj) -> bool:
        d = self._dtv(obj); return d.publicite_cloturee if d else False

    def get_approuve(self, obj) -> bool:
        d = self._dtv(obj); return d.approuve if d else False

    def get_valide(self, obj) -> bool:
        d = self._dtv(obj); return d.valide if d else False

    def get_dtv_progress(self, obj) -> int:
        d = self._dtv(obj)
        if not d:
            return 0
        return sum([
            d.recueil_historique_fait,
            bool(d.layons_identifies),
            bool(d.pv_constat_signes),
            d.delimite,
            d.publicite_ouverte,
            d.publicite_cloturee,
            d.approuve,
            d.valide,
        ])

    def get_dtv_etape(self, obj) -> str:
        d = self._dtv(obj)
        if not d:
            return 'NON_DEMARRE'
        if d.valide:              return 'VALIDE'
        if d.approuve:            return 'APPROUVE'
        if d.publicite_cloturee:  return 'PUB_CLOTUREE'
        if d.publicite_ouverte:   return 'PUB_OUVERTE'
        if d.delimite:            return 'DELIMITE'
        if d.pv_constat_signes:   return 'PV_SIGNES'
        if d.layons_identifies:   return 'LAYONS'
        if d.recueil_historique_fait: return 'RECUEIL'
        return 'NON_DEMARRE'
