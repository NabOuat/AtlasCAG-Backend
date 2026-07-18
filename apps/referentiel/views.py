from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Zone, Region, Village
from .serializers import ZoneSerializer, RegionSerializer, VillageListSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des zones',
        description='Retourne les deux zones opérationnelles : **Cavally** et **Worodougou**.',
    ),
    retrieve=extend_schema(
        tags=['Référentiel'],
        summary='Détail d\'une zone',
    ),
)
class ZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Zone.objects.all().order_by('nom')
    serializer_class   = ZoneSerializer
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des régions',
        description='Retourne toutes les régions administratives couvertes par l\'AFOR.',
    ),
    retrieve=extend_schema(
        tags=['Référentiel'],
        summary='Détail d\'une région',
    ),
)
class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Region.objects.all().order_by('nom')
    serializer_class   = RegionSerializer
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des villages',
        description=(
            'Retourne tous les villages avec leur avancement DTV (via la relation `dtv`). '
            'Filtrable par zone, sous-préfecture et étape de validation.'
        ),
        parameters=[
            OpenApiParameter('zone',            description='ID de la zone (ex: 1)', required=False),
            OpenApiParameter('sous_prefecture', description='Nom partiel de la sous-préfecture', required=False),
            OpenApiParameter(
                'etape',
                description='Étape DTV : `VALIDE`, `APPROUVE`, `DELIMITE`, `NON_DEMARRE`',
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=['Référentiel'],
        summary='Détail d\'un village',
    ),
)
class VillageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = VillageListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs    = Village.objects.select_related('zone', 'sous_prefecture_fk', 'dtv').order_by('nom')
        zone  = self.request.query_params.get('zone')
        sp    = self.request.query_params.get('sous_prefecture')
        etape = self.request.query_params.get('etape')
        if zone:  qs = qs.filter(zone__id=zone)
        if sp:    qs = qs.filter(sous_prefecture__icontains=sp)
        if etape == 'VALIDE':        qs = qs.filter(dtv__valide=True)
        elif etape == 'APPROUVE':    qs = qs.filter(dtv__approuve=True, dtv__valide=False)
        elif etape == 'DELIMITE':    qs = qs.filter(dtv__delimite=True, dtv__approuve=False)
        elif etape == 'NON_DEMARRE': qs = qs.filter(dtv__recueil_historique_fait=False)
        return qs

    @extend_schema(
        tags=['Référentiel'],
        summary='Statistiques DTV par zone',
        description=(
            'Retourne les compteurs d\'avancement DTV pour une zone donnée : '
            'total, validés, approuvés, délimités, publicité ouverte/clôturée, non démarrés.'
        ),
        parameters=[
            OpenApiParameter('zone', description='ID de la zone', required=False),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total':        {'type': 'integer'},
                    'valide':       {'type': 'integer'},
                    'approuve':     {'type': 'integer'},
                    'delimite':     {'type': 'integer'},
                    'pub_ouverte':  {'type': 'integer'},
                    'pub_cloturee': {'type': 'integer'},
                    'non_demarre':  {'type': 'integer'},
                },
            }
        },
    )
    @action(detail=False, methods=['get'])
    def stats_dtv(self, request):
        qs = Village.objects.all()
        zone = request.query_params.get('zone')
        if zone: qs = qs.filter(zone__id=zone)
        return Response({
            'total':          qs.count(),
            'valide':         qs.filter(dtv__valide=True).count(),
            'approuve':       qs.filter(dtv__approuve=True).count(),
            'delimite':       qs.filter(dtv__delimite=True).count(),
            'pub_ouverte':    qs.filter(dtv__publicite_ouverte=True).count(),
            'pub_cloturee':   qs.filter(dtv__publicite_cloturee=True).count(),
            'non_demarre':    qs.filter(dtv__recueil_historique_fait=False).count(),
        })
