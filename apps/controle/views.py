from rest_framework import viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import ControleQualite, AnomalieControle, EnvoiEntreprise
from .serializers import ControleListSerializer, ControleDetailSerializer, EnvoiSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Liste des contrôles qualité',
        description='Retourne tous les contrôles qualité réalisés, triés par date décroissante. Filtrable par zone, statut et gravité d\'anomalie.',
        parameters=[
            OpenApiParameter('zone',    description='ID de la zone', required=False),
            OpenApiParameter('statut',  description='`EN_ATTENTE`, `EN_COURS`, `VALIDE`, `REJETE`', required=False),
            OpenApiParameter('gravite', description='Filtrer les contrôles ayant au moins une anomalie de cette gravité : `BLOQUANTE`, `MAJEURE`, `MINEURE`', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Détail d\'un contrôle',
        description='Retourne le contrôle avec la liste complète de ses anomalies.',
    ),
    create=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Créer un contrôle',
        description=(
            'Crée un contrôle qualité pour un dossier. Le contrôleur est l\'utilisateur connecté.\n\n'
            '**Corps de la requête** :\n'
            '```json\n'
            '{\n'
            '  "dossier": 42,\n'
            '  "date_controle": "2026-07-18",\n'
            '  "statut": "EN_COURS",\n'
            '  "observations": "...",\n'
            '  "anomalies_input": [\n'
            '    { "description": "Superficie incohérente", "gravite": "MAJEURE" },\n'
            '    { "description": "Voisin manquant", "gravite": "MINEURE" }\n'
            '  ]\n'
            '}\n'
            '```\n'
            'Les anomalies sont créées automatiquement en cascade.'
        ),
        request=ControleListSerializer,
    ),
    update=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Modifier un contrôle (remplacement complet)',
        request=ControleListSerializer,
    ),
    partial_update=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Modifier un contrôle (partiel)',
        description='Utilisé pour changer le statut (`VALIDE` / `REJETE`) ou ajouter des observations.',
        request=ControleListSerializer,
    ),
    destroy=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Supprimer un contrôle',
    ),
)
class ControleViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ControleQualite.objects.select_related(
            'dossier__village', 'dossier__zone', 'controleur'
        ).prefetch_related('anomalies').order_by('-cree_le')
        zone    = self.request.query_params.get('zone')
        statut  = self.request.query_params.get('statut')
        gravite = self.request.query_params.get('gravite')
        if zone:    qs = qs.filter(dossier__zone__id=zone)
        if statut:  qs = qs.filter(statut=statut)
        if gravite: qs = qs.filter(anomalies__gravite=gravite).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ControleDetailSerializer
        return ControleListSerializer

    def perform_create(self, serializer):
        serializer.save(controleur=self.request.user)

    @extend_schema(
        tags=['Contrôle Qualité'],
        summary='Statistiques des contrôles',
        description='Retourne les compteurs par statut et les statistiques d\'anomalies.',
        parameters=[
            OpenApiParameter('zone',    description='ID de la zone', required=False),
            OpenApiParameter('statut',  description='Filtrer par statut', required=False),
            OpenApiParameter('gravite', description='Filtrer par gravité d\'anomalie', required=False),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total':      {'type': 'integer'},
                    'en_attente': {'type': 'integer'},
                    'en_cours':   {'type': 'integer'},
                    'valide':     {'type': 'integer'},
                    'rejete':     {'type': 'integer'},
                    'anomalies': {
                        'type': 'object',
                        'properties': {
                            'total':     {'type': 'integer'},
                            'bloquante': {'type': 'integer'},
                            'majeure':   {'type': 'integer'},
                            'mineure':   {'type': 'integer'},
                            'non_corr':  {'type': 'integer', 'description': 'Non corrigées'},
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
            'total':      qs.count(),
            'en_attente': qs.filter(statut='EN_ATTENTE').count(),
            'en_cours':   qs.filter(statut='EN_COURS').count(),
            'valide':     qs.filter(statut='VALIDE').count(),
            'rejete':     qs.filter(statut='REJETE').count(),
            'anomalies': {
                'total':       AnomalieControle.objects.count(),
                'bloquante':   AnomalieControle.objects.filter(gravite='BLOQUANTE').count(),
                'majeure':     AnomalieControle.objects.filter(gravite='MAJEURE').count(),
                'mineure':     AnomalieControle.objects.filter(gravite='MINEURE').count(),
                'non_corr':    AnomalieControle.objects.filter(corrigee=False).count(),
            },
        })


@extend_schema_view(
    list=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Liste des envois entreprises',
        description='Retourne les envois de dossiers vers les entreprises de levé. Filtrable par plateforme.',
        parameters=[
            OpenApiParameter('plateforme', description='Nom de la plateforme / entreprise', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Détail d\'un envoi',
    ),
    create=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Créer un envoi',
        description='Enregistre l\'envoi d\'un dossier vers une entreprise. L\'expéditeur est l\'utilisateur connecté.',
    ),
    update=extend_schema(tags=['Contrôle Qualité'], summary='Modifier un envoi'),
    partial_update=extend_schema(
        tags=['Contrôle Qualité'],
        summary='Modifier partiellement un envoi',
        description='Utilisé pour mettre à jour le statut ou la référence de l\'envoi.',
    ),
    destroy=extend_schema(tags=['Contrôle Qualité'], summary='Supprimer un envoi'),
)
class EnvoiViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = EnvoiSerializer

    def get_queryset(self):
        qs = EnvoiEntreprise.objects.select_related('dossier__village', 'envoye_par').order_by('-envoye_le')
        plateforme = self.request.query_params.get('plateforme')
        if plateforme: qs = qs.filter(plateforme=plateforme)
        return qs

    def perform_create(self, serializer):
        serializer.save(envoye_par=self.request.user)


# ── Contrôle Qualité — endpoints QC ────────────────────────────────────────

@extend_schema(
    tags=['Contrôle Qualité'],
    summary='Villages avec plans PDF (Contrôle QC)',
    description=(
        'Retourne la liste des villages qui ont au moins un dossier CF avec un fichier de type `PLAN`. '
        'Groupés par sous-préfecture, chaque village inclut le nombre de dossiers CF et de plans.\n\n'
        '**Usage** : première étape du workflow QC — sélection du village à contrôler.'
    ),
    parameters=[
        OpenApiParameter('zone', description='ID de la zone pour filtrer', required=False),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id':              {'type': 'integer'},
                            'nom':             {'type': 'string'},
                            'sous_prefecture': {'type': 'string'},
                            'zone_id':         {'type': 'integer'},
                            'zone_nom':        {'type': 'string'},
                            'nb_dossiers':     {'type': 'integer', 'description': 'Dossiers CF avec plans'},
                            'nb_plans':        {'type': 'integer', 'description': 'Total fichiers PLAN'},
                        },
                    },
                },
            },
        }
    },
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def qc_villages(request):
    """Villages ayant des dossiers CF avec au moins un fichier PLAN."""
    from apps.referentiel.models import Village

    zone_id = request.GET.get('zone')

    qs = Village.objects.filter(
        dossiers__type_dossier='CF',
        dossiers__fichiers__type_fichier='PLAN',
    ).distinct().select_related('zone')

    if zone_id:
        qs = qs.filter(zone_id=zone_id)

    qs = qs.annotate(
        nb_dossiers=Count(
            'dossiers',
            filter=Q(dossiers__type_dossier='CF'),
            distinct=True,
        ),
        nb_plans=Count(
            'dossiers__fichiers',
            filter=Q(
                dossiers__type_dossier='CF',
                dossiers__fichiers__type_fichier='PLAN',
            ),
            distinct=True,
        ),
    ).order_by('sous_prefecture', 'nom')

    results = [
        {
            'id':              v.id,
            'nom':             v.nom,
            'sous_prefecture': v.sous_prefecture,
            'zone_id':         v.zone_id,
            'zone_nom':        v.zone.nom,
            'nb_dossiers':     v.nb_dossiers,
            'nb_plans':        v.nb_plans,
        }
        for v in qs
    ]
    return Response({'count': len(results), 'results': results})


@extend_schema(
    tags=['Contrôle Qualité'],
    summary='Dossiers CF avec données DIGIFOR + voisins (Contrôle QC)',
    description=(
        'Retourne les dossiers CF d\'un village avec toutes les données nécessaires au contrôle qualité :\n\n'
        '- **Données DIGIFOR** : numéro de demande, demandeur, superficie, périmètre, OCS, OTA, etc.\n'
        '- **Voisins** (sommets de parcelle) : liste des voisins identifiés lors du levé DIGIFOR, '
        'avec numéro de sommet, nom du voisin, type voisinage, type nature, numéro de tronçon\n'
        '- **Fichiers PLAN** : liste des PDFs (id, nom, URL, taille, date)\n'
        '- **Dernier contrôle** : statut et ID du contrôle qualité le plus récent\n\n'
        '**Usage** : deuxième étape du workflow QC — affichage de la liste des PDFs à contrôler '
        'et chargement du panneau DIGIFOR dans la fenêtre de contrôle.'
    ),
    parameters=[
        OpenApiParameter('village', description='ID du village', required=False),
        OpenApiParameter('zone',    description='ID de la zone (retourne tous les villages de la zone)', required=False),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id':                  {'type': 'integer'},
                            'numero_dossier':      {'type': 'string'},
                            'village_id':          {'type': 'integer'},
                            'village_nom':         {'type': 'string'},
                            'zone_nom':            {'type': 'string'},
                            'statut':              {'type': 'string'},
                            'statut_cf':           {'type': 'string'},
                            'num_demand':          {'type': 'string', 'description': 'Numéro DIGIFOR'},
                            'nom_demandeur':       {'type': 'string'},
                            'superficie_parcelle': {'type': 'number', 'description': 'Superficie en hectares (DIGIFOR)'},
                            'perimetre_parcelle':  {'type': 'number'},
                            'ocs':                 {'type': 'string', 'description': 'Occupation du sol'},
                            'nom_ota':             {'type': 'string', 'description': 'Opérateur technique agrée'},
                            'voisins': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'num_sommet': {'type': 'integer'},
                                        'nom_vois':   {'type': 'string'},
                                        'typ_vois':   {'type': 'string'},
                                        'typ_nat':    {'type': 'string'},
                                        'num_tronc':  {'type': 'string'},
                                    },
                                },
                            },
                            'plans': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id':           {'type': 'integer'},
                                        'nom':          {'type': 'string'},
                                        'fichier_url':  {'type': 'string', 'format': 'uri'},
                                        'taille':       {'type': 'integer', 'description': 'Taille en octets'},
                                        'televerse_le': {'type': 'string', 'format': 'date-time'},
                                    },
                                },
                            },
                            'nb_plans':        {'type': 'integer'},
                            'controle_statut': {'type': 'string', 'nullable': True},
                            'controle_id':     {'type': 'integer', 'nullable': True},
                        },
                    },
                },
            },
        }
    },
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def qc_dossiers(request):
    """Dossiers CF d'un village avec leurs fichiers PLAN et données DIGIFOR."""
    from apps.dossiers.models import Dossier

    village_id = request.GET.get('village')
    zone_id    = request.GET.get('zone')

    qs = Dossier.objects.filter(type_dossier='CF')
    if village_id:
        qs = qs.filter(village_id=village_id)
    elif zone_id:
        qs = qs.filter(zone_id=zone_id)

    results = []
    for d in qs.select_related('village', 'zone').prefetch_related('fichiers').order_by('numero_dossier'):
        plans = [
            {
                'id':           f.id,
                'nom':          f.nom,
                'fichier_url':  request.build_absolute_uri(f.fichier.url) if f.fichier else None,
                'taille':       f.taille,
                'televerse_le': f.televerse_le,
            }
            for f in d.fichiers.filter(type_fichier='PLAN')
        ]
        # Voisins depuis SommetParcelle (DIGIFOR)
        from apps.dossiers.models import SommetParcelle
        sommets = SommetParcelle.objects.filter(dossier=d).exclude(nom_vois='').values(
            'num_sommet', 'nom_vois', 'typ_vois', 'typ_nat', 'num_tronc', 'coord_x', 'coord_y'
        ).order_by('num_sommet')
        voisins = [
            {
                'num_sommet': s['num_sommet'],
                'nom_vois':   s['nom_vois'],
                'typ_vois':   s['typ_vois'],
                'typ_nat':    s['typ_nat'],
                'num_tronc':  s['num_tronc'],
            }
            for s in sommets if s['nom_vois']
        ]

        # Dernier contrôle pour ce dossier
        dernier = ControleQualite.objects.filter(dossier=d).order_by('-cree_le').first()
        results.append({
            'id':                  d.id,
            'numero_dossier':      d.numero_dossier,
            'village_id':          d.village_id,
            'village_nom':         d.village.nom,
            'zone_nom':            d.zone.nom,
            'statut':              d.statut,
            'statut_cf':           d.statut_cf,
            # DIGIFOR — données dossier
            'num_demand':          d.num_demand,
            'nom_demandeur':       d.nom_demandeur,
            'superficie_parcelle': d.superficie_parcelle,
            'perimetre_parcelle':  d.perimetre_parcelle,
            'ocs':                 d.ocs,
            'nom_ota':             d.nom_ota,
            'n_demcge':            d.n_demcge,
            'boucle':              d.boucle,
            'cd_sp_vil':           d.cd_sp_vil,
            'clas_preci':          d.clas_preci,
            'point_ratt':          d.point_ratt,
            # DIGIFOR — voisins (SommetParcelle)
            'voisins':             voisins,
            # Fichiers
            'plans':               plans,
            'nb_plans':            len(plans),
            # Dernier contrôle
            'controle_statut':     dernier.statut if dernier else None,
            'controle_id':         dernier.id     if dernier else None,
        })

    return Response({'count': len(results), 'results': results})
