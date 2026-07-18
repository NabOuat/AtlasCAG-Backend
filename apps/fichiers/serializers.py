from rest_framework import serializers
from .models import FichierDossier


class FichierDossierSerializer(serializers.ModelSerializer):
    dossier_numero    = serializers.CharField(source='dossier.numero_dossier', read_only=True)
    televerse_par_nom = serializers.SerializerMethodField()
    fichier_url       = serializers.SerializerMethodField()

    class Meta:
        model  = FichierDossier
        fields = [
            'id', 'dossier', 'dossier_numero', 'nom', 'type_fichier',
            'fichier', 'fichier_url', 'taille',
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
