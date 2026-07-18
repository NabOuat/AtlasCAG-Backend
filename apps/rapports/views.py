from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import RapportPeriodique
from .serializers import RapportSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Rapports'],
        summary='Liste des rapports périodiques',
        description=(
            'Retourne tous les rapports périodiques triés par date décroissante. '
            'Filtrable par zone, type de rapport, statut et période.'
        ),
        parameters=[
            OpenApiParameter('zone',         description='ID de la zone', required=False),
            OpenApiParameter('type_rapport', description='`HEBDOMADAIRE`, `MENSUEL`, `TRIMESTRIEL`, `ANNUEL`', required=False),
            OpenApiParameter('statut',       description='`BROUILLON`, `VALIDE`, `PUBLIE`', required=False),
            OpenApiParameter('periode',      description='Période au format YYYY-MM (ex: 2026-07)', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Rapports'], summary='Détail d\'un rapport'),
    create=extend_schema(
        tags=['Rapports'],
        summary='Créer un rapport',
        description='Crée un nouveau rapport. L\'auteur est automatiquement l\'utilisateur connecté.',
    ),
    update=extend_schema(tags=['Rapports'], summary='Modifier un rapport (remplacement complet)'),
    partial_update=extend_schema(
        tags=['Rapports'],
        summary='Modifier un rapport (partiel)',
        description='Met à jour le statut, le contenu ou tout autre champ du rapport.',
    ),
    destroy=extend_schema(tags=['Rapports'], summary='Supprimer un rapport'),
)
class RapportViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = RapportSerializer

    def get_queryset(self):
        qs = RapportPeriodique.objects.select_related('zone', 'redige_par').order_by('-cree_le')
        zone         = self.request.query_params.get('zone')
        type_rapport = self.request.query_params.get('type_rapport')
        statut       = self.request.query_params.get('statut')
        periode      = self.request.query_params.get('periode')
        if zone:         qs = qs.filter(zone__id=zone)
        if type_rapport: qs = qs.filter(type_rapport=type_rapport)
        if statut:       qs = qs.filter(statut=statut)
        if periode:      qs = qs.filter(periode=periode)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        serializer.save(redige_par=self.request.user)
