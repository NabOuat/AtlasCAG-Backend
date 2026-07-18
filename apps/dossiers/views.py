from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Dossier
from .serializers import DossierListSerializer, DossierDetailSerializer, DossierCreateSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Dossiers'],
        summary='Liste des dossiers',
        description=(
            'Retourne tous les dossiers (CF et DTV) triés par date de création décroissante. '
            'Filtrable par zone, statut, type de dossier et recherche textuelle.'
        ),
        parameters=[
            OpenApiParameter('zone',         description='ID de la zone', required=False),
            OpenApiParameter('statut',       description='`EN_COURS`, `VALIDE`, `REJETE`, `ARCHIVE`', required=False),
            OpenApiParameter('type_dossier', description='`CF` (Certificat Foncier) ou `DTV` (Délimitation Territoriale Villageoise) ou `CONTRACTUALISATION`', required=False),
            OpenApiParameter('search',       description='Recherche par numéro de dossier ou nom du village', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Dossiers'],
        summary='Détail d\'un dossier',
        description=(
            'Retourne toutes les informations d\'un dossier : données DIGIFOR, '
            'sommets de parcelle (voisins), fichiers attachés, contrats et contrôles liés.'
        ),
    ),
    create=extend_schema(
        tags=['Dossiers'],
        summary='Créer un dossier',
        description='Crée un nouveau dossier CF ou DTV. L\'utilisateur connecté est enregistré comme créateur.',
        request=DossierCreateSerializer,
    ),
    update=extend_schema(
        tags=['Dossiers'],
        summary='Modifier un dossier (remplacement complet)',
        request=DossierCreateSerializer,
    ),
    partial_update=extend_schema(
        tags=['Dossiers'],
        summary='Modifier un dossier (partiel)',
        description='Met à jour un ou plusieurs champs du dossier (ex : changer le statut).',
        request=DossierCreateSerializer,
    ),
    destroy=extend_schema(
        tags=['Dossiers'],
        summary='Supprimer un dossier',
    ),
)
class DossierViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Dossier.objects.select_related('village', 'zone', 'cree_par').order_by('-cree_le')
        zone         = self.request.query_params.get('zone')
        statut       = self.request.query_params.get('statut')
        type_dossier = self.request.query_params.get('type_dossier')
        search       = self.request.query_params.get('search')
        if zone:         qs = qs.filter(zone__id=zone)
        if statut:       qs = qs.filter(statut=statut)
        if type_dossier: qs = qs.filter(type_dossier=type_dossier)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(numero_dossier__icontains=search) | Q(village__nom__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return DossierCreateSerializer
        if self.action == 'retrieve':
            return DossierDetailSerializer
        return DossierListSerializer

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user)

    @extend_schema(
        tags=['Dossiers'],
        summary='Statistiques des dossiers',
        description=(
            'Retourne les compteurs agrégés des dossiers. '
            'Les mêmes filtres que la liste (`zone`, `statut`, `type_dossier`) s\'appliquent.'
        ),
        parameters=[
            OpenApiParameter('zone',         description='ID de la zone', required=False),
            OpenApiParameter('statut',       description='Filtrer le total par statut', required=False),
            OpenApiParameter('type_dossier', description='`CF` ou `DTV`', required=False),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total':    {'type': 'integer'},
                    'en_cours': {'type': 'integer'},
                    'valide':   {'type': 'integer'},
                    'rejete':   {'type': 'integer'},
                    'archive':  {'type': 'integer'},
                    'par_type': {
                        'type': 'object',
                        'properties': {
                            'DTV':                {'type': 'integer'},
                            'CF':                 {'type': 'integer'},
                            'CONTRACTUALISATION': {'type': 'integer'},
                        },
                    },
                },
            }
        },
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total':    qs.count(),
            'en_cours': qs.filter(statut='EN_COURS').count(),
            'valide':   qs.filter(statut='VALIDE').count(),
            'rejete':   qs.filter(statut='REJETE').count(),
            'archive':  qs.filter(statut='ARCHIVE').count(),
            'par_type': {
                'DTV':                qs.filter(type_dossier='DTV').count(),
                'CF':                 qs.filter(type_dossier='CF').count(),
                'CONTRACTUALISATION': qs.filter(type_dossier='CONTRACTUALISATION').count(),
            },
        })
