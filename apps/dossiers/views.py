from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from apps.referentiel.models import Zone
from .models import Dossier, VagueEnvoi
from .serializers import (
    DossierListSerializer, DossierDetailSerializer, DossierCreateSerializer,
    VagueEnvoiSerializer, SuiviCFSerializer, SuiviCFCreateSerializer,
)
from .services import importer_fichier_ads, ImportADSError


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


@extend_schema_view(
    list=extend_schema(
        tags=['Dossiers'],
        summary='Liste des vagues d\'envoi',
        description='Retourne les lots de dossiers envoyés ensemble à l\'administration. Filtrable par zone et type de dossier.',
        parameters=[
            OpenApiParameter('zone',         description='ID de la zone', required=False),
            OpenApiParameter('type_dossier', description='`CF` ou `DTV`', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Dossiers'], summary='Détail d\'une vague d\'envoi'),
    create=extend_schema(tags=['Dossiers'], summary='Créer une vague d\'envoi'),
    update=extend_schema(tags=['Dossiers'], summary='Modifier une vague d\'envoi'),
    partial_update=extend_schema(tags=['Dossiers'], summary='Modifier une vague d\'envoi (partiel)'),
    destroy=extend_schema(tags=['Dossiers'], summary='Supprimer une vague d\'envoi'),
)
class VagueEnvoiViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = VagueEnvoiSerializer

    def get_queryset(self):
        qs           = VagueEnvoi.objects.select_related('zone').order_by('-date')
        zone         = self.request.query_params.get('zone')
        type_dossier = self.request.query_params.get('type_dossier')
        if zone:         qs = qs.filter(zone__id=zone)
        if type_dossier: qs = qs.filter(type_dossier=type_dossier)
        return qs


@extend_schema_view(
    list=extend_schema(
        tags=['Dossiers'],
        summary='Suivi CF — liste des dossiers CF',
        description=(
            'Vue de suivi administratif des dossiers CF (statut, statut_cf, vague d\'envoi). '
            'Distincte de la table attributaire SIG (`/api/geo/{zone}/cf/parcelles/`), qui reste '
            'la source d\'affichage cartographique — cet endpoint sert le pilotage du workflow.'
        ),
        parameters=[
            OpenApiParameter('zone',        description='ID de la zone', required=False),
            OpenApiParameter('statut',      description='`EN_COURS`, `VALIDE`, `REJETE`, `ARCHIVE`, `ANNULE`', required=False),
            OpenApiParameter('statut_cf',   description='`LEVE`, `PROV`, `EN_PUBLICITE`, `DEF`, `APPROUVE`, `VALIDE`, `REJETE`', required=False),
            OpenApiParameter('vague_envoi', description='ID de la vague d\'envoi', required=False),
            OpenApiParameter('search',      description='Recherche par numéro de dossier, village, demandeur ou num_demand', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Dossiers'], summary='Détail d\'un dossier CF (suivi)'),
    create=extend_schema(tags=['Dossiers'], summary='Créer un dossier CF', request=SuiviCFCreateSerializer),
    update=extend_schema(tags=['Dossiers'], summary='Modifier un dossier CF', request=SuiviCFCreateSerializer),
    partial_update=extend_schema(tags=['Dossiers'], summary='Modifier un dossier CF (partiel)', request=SuiviCFCreateSerializer),
    destroy=extend_schema(tags=['Dossiers'], summary='Supprimer un dossier CF'),
)
class SuiviCFViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q
        qs = (
            Dossier.objects.filter(type_dossier='CF')
            .select_related('village', 'zone', 'vague_envoi', 'cree_par')
            .order_by('-cree_le')
        )
        zone        = self.request.query_params.get('zone')
        statut      = self.request.query_params.get('statut')
        statut_cf   = self.request.query_params.get('statut_cf')
        vague_envoi = self.request.query_params.get('vague_envoi')
        search      = self.request.query_params.get('search')
        if zone:        qs = qs.filter(zone__id=zone)
        if statut:      qs = qs.filter(statut=statut)
        if statut_cf:   qs = qs.filter(statut_cf=statut_cf)
        if vague_envoi: qs = qs.filter(vague_envoi__id=vague_envoi)
        if search:
            qs = qs.filter(
                Q(numero_dossier__icontains=search) | Q(village__nom__icontains=search)
                | Q(nom_demandeur__icontains=search) | Q(num_demand__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return SuiviCFCreateSerializer
        return SuiviCFSerializer

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, type_dossier='CF')

    @extend_schema(
        tags=['Dossiers'],
        summary='Import en masse — fichier ADS',
        description=(
            'Importe un fichier Excel (`.xlsx`) ou CSV (`.csv`) listant des dossiers CF à créer '
            'ou mettre à jour (upsert sur `numero_dossier`). Colonnes reconnues : `numero_dossier` '
            '(obligatoire), `village` (obligatoire à la création), `sous_prefecture` (optionnel, '
            'désambiguïse un village), `num_demand`, `nom_demandeur`, `superficie_parcelle`, '
            '`perimetre_parcelle`, `nom_ota`, `n_demcge`, `statut_cf`. Le fichier n\'est pas '
            'conservé côté serveur — traitement en mémoire uniquement. Chaque ligne est traitée '
            'indépendamment : une ligne en erreur n\'empêche pas l\'import des autres.'
        ),
        request={'multipart/form-data': {
            'type': 'object',
            'properties': {
                'fichier': {'type': 'string', 'format': 'binary'},
                'zone':    {'type': 'integer'},
            },
            'required': ['fichier', 'zone'],
        }},
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total_rows': {'type': 'integer'},
                    'created':    {'type': 'integer'},
                    'updated':    {'type': 'integer'},
                    'errors': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'row':            {'type': 'integer'},
                                'numero_dossier': {'type': 'string', 'nullable': True},
                                'message':        {'type': 'string'},
                            },
                        },
                    },
                },
            },
            400: {'description': 'Fichier manquant, zone manquante/inconnue, ou fichier illisible'},
        },
    )
    @action(detail=False, methods=['post'], url_path='import-ads')
    def import_ads(self, request):
        fichier = request.FILES.get('fichier')
        zone_id = request.data.get('zone')
        if not fichier:
            return Response({'detail': 'Fichier requis.'}, status=status.HTTP_400_BAD_REQUEST)
        if not zone_id:
            return Response({'detail': 'zone requise.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            zone = Zone.objects.get(pk=zone_id)
        except Zone.DoesNotExist:
            return Response({'detail': f'Zone inconnue : {zone_id}'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = importer_fichier_ads(fichier, zone, request.user)
        except ImportADSError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)
