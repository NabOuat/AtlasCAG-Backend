from rest_framework import serializers
from apps.dossiers.models import Dossier
from .models import FichierDossier, FichierExcelPublicite


class DossierPKOuCodeField(serializers.PrimaryKeyRelatedField):
    """Accepte en écriture soit l'ID numérique (clé primaire) du dossier, soit son
    `numero_dossier` (code métier, ex. `088-001-000011`) — c'est ce code que connaissent les
    utilisateurs sur le terrain, pas l'ID technique interne, donc le frontend l'envoie tel quel
    plutôt que de faire une recherche préalable pour résoudre l'ID."""

    def to_internal_value(self, data):
        if isinstance(data, str) and not data.strip().isdigit():
            code = data.strip()
            try:
                return self.get_queryset().get(numero_dossier=code)
            except Dossier.DoesNotExist:
                self.fail('does_not_exist', pk_value=f'numero_dossier={code}')
        return super().to_internal_value(data)


class FichierDossierSerializer(serializers.ModelSerializer):
    dossier           = DossierPKOuCodeField(queryset=Dossier.objects.all())
    dossier_numero    = serializers.CharField(source='dossier.numero_dossier', read_only=True)
    village_id        = serializers.IntegerField(source='dossier.village_id', read_only=True)
    village_nom       = serializers.CharField(source='dossier.village.nom', read_only=True)
    sous_prefecture   = serializers.CharField(source='dossier.village.sous_prefecture', read_only=True)
    zone_id           = serializers.IntegerField(source='dossier.zone_id', read_only=True)
    televerse_par_nom = serializers.SerializerMethodField()
    fichier_url       = serializers.SerializerMethodField()

    class Meta:
        model  = FichierDossier
        fields = [
            'id', 'dossier', 'dossier_numero',
            'village_id', 'village_nom', 'sous_prefecture', 'zone_id',
            'nom', 'type_fichier', 'fichier', 'fichier_url', 'taille',
            'televerse_par', 'televerse_par_nom', 'televerse_le',
        ]
        read_only_fields = ['taille', 'televerse_le', 'televerse_par']

    def get_televerse_par_nom(self, obj) -> str | None:
        if obj.televerse_par:
            return f'{obj.televerse_par.first_name} {obj.televerse_par.last_name}'.strip()
        return None

    def get_fichier_url(self, obj) -> str | None:
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
        return None


class FichierExcelPubliciteSerializer(serializers.ModelSerializer):
    village_nom     = serializers.CharField(source='village.nom', read_only=True)
    sous_prefecture = serializers.CharField(source='village.sous_prefecture', read_only=True)
    zone_id         = serializers.IntegerField(source='village.zone_id', read_only=True)
    televerse_par_nom = serializers.SerializerMethodField()
    fichier_url     = serializers.SerializerMethodField()

    class Meta:
        model  = FichierExcelPublicite
        fields = [
            'id', 'village', 'village_nom', 'sous_prefecture', 'zone_id',
            'nom', 'fichier', 'fichier_url', 'taille', 'description',
            'televerse_par', 'televerse_par_nom', 'televerse_le',
        ]
        read_only_fields = ['taille', 'televerse_le', 'televerse_par']

    def get_televerse_par_nom(self, obj) -> str | None:
        if obj.televerse_par:
            return f'{obj.televerse_par.first_name} {obj.televerse_par.last_name}'.strip()
        return None

    def get_fichier_url(self, obj) -> str | None:
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
        return None
