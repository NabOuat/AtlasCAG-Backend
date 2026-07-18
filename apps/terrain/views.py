from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import PlanningASFJournalier, Layon
from .serializers import PlanningSerializer, PlanningCreateSerializer, LayonSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Terrain'],
        summary='Liste du planning des missions ASF',
        description=(
            'Retourne le planning journalier des agents de sécurisation foncière (ASF). '
            'Filtrable par agent, zone, période et type d\'activité.'
        ),
        parameters=[
            OpenApiParameter('asf',           description='ID de l\'agent ASF', required=False),
            OpenApiParameter('zone',          description='ID de la zone', required=False),
            OpenApiParameter('date_debut',    description='Date de début au format YYYY-MM-DD', required=False),
            OpenApiParameter('date_fin',      description='Date de fin au format YYYY-MM-DD', required=False),
            OpenApiParameter('type_activite', description='Type d\'activité terrain', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Terrain'], summary='Détail d\'une mission'),
    create=extend_schema(
        tags=['Terrain'],
        summary='Créer une mission terrain',
        description='Planifie une nouvelle mission journalière pour un ASF sur un village.',
        request=PlanningCreateSerializer,
    ),
    update=extend_schema(
        tags=['Terrain'],
        summary='Modifier une mission (remplacement complet)',
        request=PlanningCreateSerializer,
    ),
    partial_update=extend_schema(
        tags=['Terrain'],
        summary='Modifier une mission (partiel)',
        request=PlanningCreateSerializer,
    ),
    destroy=extend_schema(tags=['Terrain'], summary='Supprimer une mission'),
)
class PlanningViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = PlanningASFJournalier.objects.select_related('asf', 'village__zone').order_by('date_activite', 'heure_debut')
        asf           = self.request.query_params.get('asf')
        zone          = self.request.query_params.get('zone')
        date_debut    = self.request.query_params.get('date_debut')
        date_fin      = self.request.query_params.get('date_fin')
        type_activite = self.request.query_params.get('type_activite')
        if asf:           qs = qs.filter(asf__id=asf)
        if zone:          qs = qs.filter(village__zone__id=zone)
        if date_debut:    qs = qs.filter(date_activite__gte=date_debut)
        if date_fin:      qs = qs.filter(date_activite__lte=date_fin)
        if type_activite: qs = qs.filter(type_activite=type_activite)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return PlanningCreateSerializer
        return PlanningSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Terrain'],
        summary='Liste des layons identifiés',
        description=(
            'Retourne les layons identifiés lors des missions terrain. '
            'Un layon est un tracé à débroussailler pour délimiter un village DTV. '
            'Filtrable par village.'
        ),
        parameters=[
            OpenApiParameter('village', description='ID du village', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Terrain'], summary='Détail d\'un layon'),
    create=extend_schema(
        tags=['Terrain'],
        summary='Enregistrer un layon',
        description='Crée un layon identifié lors d\'une mission de délimitation DTV.',
    ),
    update=extend_schema(tags=['Terrain'], summary='Modifier un layon'),
    partial_update=extend_schema(tags=['Terrain'], summary='Modifier partiellement un layon'),
    destroy=extend_schema(tags=['Terrain'], summary='Supprimer un layon'),
)
class LayonViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = LayonSerializer

    def get_queryset(self):
        qs      = Layon.objects.select_related('village__zone').order_by('village__nom', 'identifiant')
        village = self.request.query_params.get('village')
        if village: qs = qs.filter(village__id=village)
        return qs
