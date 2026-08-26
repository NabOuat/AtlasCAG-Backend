from rest_framework import serializers
from .models import RapportBureau


class RapportBureauSerializer(serializers.ModelSerializer):
    agent_nom       = serializers.SerializerMethodField()
    zone_nom        = serializers.CharField(source='zone.nom', read_only=True)
    region_nom      = serializers.CharField(source='region.nom', read_only=True)
    departement_nom = serializers.CharField(source='departement.nom', read_only=True)
    vague_nom       = serializers.CharField(source='vague.nom', read_only=True, default=None)

    class Meta:
        model  = RapportBureau
        fields = [
            'id', 'date', 'zone', 'zone_nom', 'region', 'region_nom',
            'departement', 'departement_nom', 'vague', 'vague_nom',
            'type_traitement', 'agent', 'agent_nom', 'fichier',
            'nb_parcelles', 'superficie_totale', 'repartition_village',
            'observations', 'cree_le',
        ]
        read_only_fields = ['agent', 'fichier', 'nb_parcelles', 'superficie_totale', 'repartition_village']

    def get_agent_nom(self, obj) -> str:
        u = obj.agent
        if not u:
            return '—'
        return f'{u.first_name} {u.last_name}'.strip() or u.username


class NouveauRapportBureauSerializer(serializers.ModelSerializer):
    """Entrée du formulaire de dépôt. `agent` (l'utilisateur connecté), `nb_parcelles`,
    `superficie_totale` et `repartition_village` sont renseignés côté vue à partir du parsing
    du fichier (apps.bureau.services.importer_rapport_bureau), jamais par le client."""

    class Meta:
        model  = RapportBureau
        fields = ['date', 'zone', 'region', 'departement', 'vague', 'type_traitement', 'fichier', 'observations']
