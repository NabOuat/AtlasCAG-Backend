from rest_framework import serializers
from .models import PlanningASFJournalier, Layon


class PlanningSerializer(serializers.ModelSerializer):
    asf_nom      = serializers.SerializerMethodField()
    village_nom  = serializers.CharField(source='village.nom', read_only=True)
    zone_nom     = serializers.CharField(source='village.zone.nom', read_only=True)

    class Meta:
        model  = PlanningASFJournalier
        fields = [
            'id', 'asf', 'asf_nom', 'village', 'village_nom', 'zone_nom',
            'date_activite', 'heure_debut', 'heure_fin',
            'type_activite', 'lieu', 'observations',
        ]

    def get_asf_nom(self, obj) -> str:
        u = obj.asf
        return f'{u.first_name} {u.last_name}'.strip() or u.username


class PlanningCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlanningASFJournalier
        fields = ['asf', 'village', 'date_activite', 'heure_debut', 'heure_fin',
                  'type_activite', 'lieu', 'observations']


class LayonSerializer(serializers.ModelSerializer):
    village_nom = serializers.CharField(source='village.nom', read_only=True)

    class Meta:
        model  = Layon
        fields = ['id', 'village', 'village_nom', 'identifiant', 'description', 'cree_le']
