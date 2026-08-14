from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from apps.accounts.permissions import IsAdminOuChefProjet
from .models import Zone, Region, Departement, SousPrefecture, Village
from .serializers import (
    ZoneSerializer, RegionSerializer, DepartementSerializer,
    SousPrefectureSerializer, VillageListSerializer, VillageWriteSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des zones',
        description='Retourne les zones opérationnelles (ex. Cavally, Worodougou).',
    ),
    retrieve=extend_schema(tags=['Référentiel'], summary='Détail d\'une zone'),
    create=extend_schema(
        tags=['Référentiel'],
        summary='Créer une zone',
        description='Réservé aux profils Administrateur et Chef de Projet.',
    ),
    update=extend_schema(tags=['Référentiel'], summary='Modifier une zone (réservé Admin/Chef de Projet)'),
    partial_update=extend_schema(tags=['Référentiel'], summary='Modifier une zone (partiel, réservé Admin/Chef de Projet)'),
    destroy=extend_schema(tags=['Référentiel'], summary='Supprimer une zone (réservé Admin/Chef de Projet)'),
)
class ZoneViewSet(viewsets.ModelViewSet):
    queryset           = Zone.objects.all().order_by('nom')
    serializer_class   = ZoneSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOuChefProjet]


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des régions',
        description='Retourne toutes les régions administratives couvertes par l\'AFOR.',
    ),
    retrieve=extend_schema(tags=['Référentiel'], summary='Détail d\'une région'),
    create=extend_schema(
        tags=['Référentiel'],
        summary='Créer une région',
        description='Réservé aux profils Administrateur et Chef de Projet.',
    ),
    update=extend_schema(tags=['Référentiel'], summary='Modifier une région (réservé Admin/Chef de Projet)'),
    partial_update=extend_schema(tags=['Référentiel'], summary='Modifier une région (partiel, réservé Admin/Chef de Projet)'),
    destroy=extend_schema(tags=['Référentiel'], summary='Supprimer une région (réservé Admin/Chef de Projet)'),
)
class RegionViewSet(viewsets.ModelViewSet):
    queryset           = Region.objects.all().order_by('nom')
    serializer_class   = RegionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOuChefProjet]


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des départements',
        description='Filtrable par région.',
        parameters=[OpenApiParameter('region', description='ID de la région', required=False)],
    ),
    retrieve=extend_schema(tags=['Référentiel'], summary='Détail d\'un département'),
    create=extend_schema(
        tags=['Référentiel'],
        summary='Créer un département',
        description='Réservé aux profils Administrateur et Chef de Projet.',
    ),
    update=extend_schema(tags=['Référentiel'], summary='Modifier un département (réservé Admin/Chef de Projet)'),
    partial_update=extend_schema(tags=['Référentiel'], summary='Modifier un département (partiel, réservé Admin/Chef de Projet)'),
    destroy=extend_schema(tags=['Référentiel'], summary='Supprimer un département (réservé Admin/Chef de Projet)'),
)
class DepartementViewSet(viewsets.ModelViewSet):
    serializer_class   = DepartementSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOuChefProjet]

    def get_queryset(self):
        qs     = Departement.objects.select_related('region').order_by('nom')
        region = self.request.query_params.get('region')
        if region: qs = qs.filter(region__id=region)
        return qs


@extend_schema_view(
    list=extend_schema(
        tags=['Référentiel'],
        summary='Liste des sous-préfectures',
        description='Filtrable par département.',
        parameters=[OpenApiParameter('departement', description='ID du département', required=False)],
    ),
    retrieve=extend_schema(tags=['Référentiel'], summary='Détail d\'une sous-préfecture'),
    create=extend_schema(
        tags=['Référentiel'],
        summary='Créer une sous-préfecture',
        description='Réservé aux profils Administrateur et Chef de Projet.',
    ),
    update=extend_schema(tags=['Référentiel'], summary='Modifier une sous-préfecture (réservé Admin/Chef de Projet)'),
    partial_update=extend_schema(tags=['Référentiel'], summary='Modifier une sous-préfecture (partiel, réservé Admin/Chef de Projet)'),
    destroy=extend_schema(tags=['Référentiel'], summary='Supprimer une sous-préfecture (réservé Admin/Chef de Projet)'),
)
class SousPrefectureViewSet(viewsets.ModelViewSet):
    serializer_class   = SousPrefectureSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOuChefProjet]

    def get_queryset(self):
        qs          = SousPrefecture.objects.select_related('departement').order_by('nom')
        departement = self.request.query_params.get('departement')
        if departement: qs = qs.filter(departement__id=departement)
        return qs


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
                description='Étape DTV : `VALIDE`, `APPROUVE`, `EXISTANT`, `NON_DEMARRE`',
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=['Référentiel'],
        summary='Détail d\'un village',
    ),
    create=extend_schema(
        tags=['Référentiel'],
        summary='Créer un village',
        description='Réservé aux profils Administrateur et Chef de Projet. Champs réels uniquement (pas d\'avancement DTV — géré séparément).',
        request=VillageWriteSerializer,
    ),
    update=extend_schema(tags=['Référentiel'], summary='Modifier un village (réservé Admin/Chef de Projet)', request=VillageWriteSerializer),
    partial_update=extend_schema(tags=['Référentiel'], summary='Modifier un village (partiel, réservé Admin/Chef de Projet)', request=VillageWriteSerializer),
    destroy=extend_schema(tags=['Référentiel'], summary='Supprimer un village (réservé Admin/Chef de Projet)'),
)
class VillageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOuChefProjet]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return VillageWriteSerializer
        return VillageListSerializer

    def get_queryset(self):
        qs    = Village.objects.select_related('zone', 'sous_prefecture_fk', 'dtv').order_by('nom')
        zone  = self.request.query_params.get('zone')
        sp    = self.request.query_params.get('sous_prefecture')
        etape = self.request.query_params.get('etape')
        if zone:  qs = qs.filter(zone__id=zone)
        if sp:    qs = qs.filter(sous_prefecture__icontains=sp)
        # 'DELIMITE' toléré en entrée pour compatibilité ascendante, non documenté (cf. cahier des charges : le
        # terme « Délimité » est remplacé par « Existant » dans toute la nomenclature exposée).
        if etape in ('EXISTANT', 'DELIMITE'):
            qs = qs.filter(dtv__delimite=True, dtv__approuve=False)
        elif etape == 'VALIDE':      qs = qs.filter(dtv__valide=True)
        elif etape == 'APPROUVE':    qs = qs.filter(dtv__approuve=True, dtv__valide=False)
        elif etape == 'NON_DEMARRE': qs = qs.filter(dtv__recueil_historique_fait=False)
        return qs

    @extend_schema(
        tags=['Référentiel'],
        summary='Statistiques DTV par zone',
        description=(
            'Retourne les compteurs d\'avancement DTV pour une zone donnée : '
            'total, validés, approuvés, existants, publicité ouverte/clôturée, non démarrés.'
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
                    'existant':     {'type': 'integer'},
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
            'existant':       qs.filter(dtv__delimite=True).count(),
            'pub_ouverte':    qs.filter(dtv__publicite_ouverte=True).count(),
            'pub_cloturee':   qs.filter(dtv__publicite_cloturee=True).count(),
            'non_demarre':    qs.filter(dtv__recueil_historique_fait=False).count(),
        })
