from rest_framework import serializers
from apps.dossiers.models import Dossier, VagueEnvoi
from .models import FichierDossier, FichierExcelPublicite


class DossierPKOuCodeField(serializers.PrimaryKeyRelatedField):
    """Accepte en écriture soit l'ID numérique (clé primaire) du dossier, soit un code texte —
    `numero_dossier` (code interne, ex. `505-005-051053-051053`, construit par l'import Excel
    publicité comme NUM_DEMAND + N° PARCELLE) ou directement `num_demand` (ex. `505-005-051053`,
    la valeur affichée dans la colonne NUM_DEMAND du Canevas et celle que l'outil de détection du
    nom de fichier PDF extrait — les deux ne coïncident donc pas dès qu'une demande couvre
    plusieurs parcelles). Les utilisateurs sur le terrain ne connaissent que NUM_DEMAND, pas le
    code interne, donc le frontend envoie le code tel quel plutôt que de faire une recherche
    préalable pour résoudre l'ID."""

    default_error_messages = {
        'does_not_exist': (
            "Aucun dossier correspondant à ce PDF n'a été trouvé (code recherché : "
            "{pk_value!r}). Vérifiez le NUM_DEMAND ou le nom du fichier."
        ),
        'multiple_matches': (
            "Plusieurs dossiers partagent ce NUM_DEMAND ({pk_value!r}) — précisez le N° PARCELLE "
            "en renseignant le code complet du dossier (ex : {pk_value}-051053)."
        ),
        'incorrect_type': 'Code de dossier invalide : {data_type}.',
    }

    def to_internal_value(self, data):
        if isinstance(data, str) and not data.strip().isdigit():
            code = data.strip()
            try:
                return self.get_queryset().get(numero_dossier=code)
            except Dossier.DoesNotExist:
                pass
            matches = list(self.get_queryset().filter(num_demand=code)[:2])
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                self.fail('multiple_matches', pk_value=code)
            self.fail('does_not_exist', pk_value=f'numero_dossier ou num_demand={code}')
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
    vague           = serializers.PrimaryKeyRelatedField(queryset=VagueEnvoi.objects.all())
    vague_nom       = serializers.CharField(source='vague.nom', read_only=True, default=None)
    televerse_par_nom = serializers.SerializerMethodField()
    fichier_url     = serializers.SerializerMethodField()

    class Meta:
        model  = FichierExcelPublicite
        fields = [
            'id', 'village', 'village_nom', 'sous_prefecture', 'zone_id',
            'vague', 'vague_nom',
            'nom', 'fichier', 'fichier_url', 'taille', 'description',
            'nb_parcelles', 'nb_crees', 'nb_maj', 'superficie_totale', 'erreurs',
            'televerse_par', 'televerse_par_nom', 'televerse_le',
        ]
        read_only_fields = [
            'taille', 'televerse_le', 'televerse_par',
            'nb_parcelles', 'nb_crees', 'nb_maj', 'superficie_totale', 'erreurs',
        ]

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
