import datetime

import openpyxl
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import RapportBureau
from .permissions import PeutSaisirRapportBureau
from .serializers import RapportBureauSerializer, NouveauRapportBureauSerializer
from .services import importer_rapport_bureau, ImportRapportBureauError

FILTER_PARAMETERS = [
    OpenApiParameter('zone',            description='ID de la zone', required=False),
    OpenApiParameter('region',          description='ID de la région', required=False),
    OpenApiParameter('departement',     description='ID du département', required=False),
    OpenApiParameter('vague',           description='ID de la vague d\'envoi', required=False),
    OpenApiParameter('type_traitement', description='Type de traitement', required=False),
    OpenApiParameter('date_debut',      description='Date de début au format YYYY-MM-DD', required=False),
    OpenApiParameter('date_fin',        description='Date de fin au format YYYY-MM-DD', required=False),
]


@extend_schema_view(
    list=extend_schema(
        tags=['Planning Bureau'],
        summary='Liste des rapports bureau (un agent, un jour, un type)',
        description=(
            'Retourne les rapports bureau déposés, issus des imports Excel journaliers. '
            'Filtrable par zone/région/département/vague/type/période, triable via `ordering` '
            '(`date`, `nb_parcelles`, `superficie_totale`, préfixer de `-` pour l\'ordre décroissant).'
        ),
        parameters=FILTER_PARAMETERS,
    ),
    retrieve=extend_schema(tags=['Planning Bureau'], summary='Détail d\'un rapport'),
    create=extend_schema(
        tags=['Planning Bureau'],
        summary='Déposer un rapport journalier (fichier Excel)',
        description=(
            'Importe le fichier Excel du jour pour le contexte donné (date/zone/région/'
            'département/type de traitement) : une ligne du fichier = un village travaillé. '
            '`nb_parcelles`, `superficie_totale` et la répartition par village sont calculés '
            'automatiquement. L\'agent est l\'utilisateur connecté.\n\n'
            'Colonnes attendues : une colonne Village, une colonne nombre de parcelles/PDF, '
            'une colonne superficie (ha) — libellés tolérants, voir apps.bureau.services.'
        ),
        request={'multipart/form-data': NouveauRapportBureauSerializer},
        responses={201: RapportBureauSerializer},
    ),
    update=extend_schema(tags=['Planning Bureau'], summary='Modifier un rapport (remplacement complet)'),
    partial_update=extend_schema(tags=['Planning Bureau'], summary='Modifier un rapport (partiel)'),
    destroy=extend_schema(tags=['Planning Bureau'], summary='Supprimer un rapport'),
)
class RapportBureauViewSet(viewsets.ModelViewSet):
    permission_classes = [PeutSaisirRapportBureau]
    serializer_class    = RapportBureauSerializer
    ordering_fields      = ['date', 'nb_parcelles', 'superficie_totale']
    ordering              = ['-date', '-cree_le']

    def get_queryset(self):
        qs = RapportBureau.objects.select_related('zone', 'region', 'departement', 'vague', 'agent')
        p = self.request.query_params
        zone            = p.get('zone')
        region          = p.get('region')
        departement     = p.get('departement')
        vague           = p.get('vague')
        type_traitement = p.get('type_traitement')
        date_debut      = p.get('date_debut')
        date_fin        = p.get('date_fin')
        if zone:            qs = qs.filter(zone__id=zone)
        if region:          qs = qs.filter(region__id=region)
        if departement:     qs = qs.filter(departement__id=departement)
        if vague:           qs = qs.filter(vague__id=vague)
        if type_traitement: qs = qs.filter(type_traitement=type_traitement)
        if date_debut:      qs = qs.filter(date__gte=date_debut)
        if date_fin:        qs = qs.filter(date__lte=date_fin)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return NouveauRapportBureauSerializer
        return RapportBureauSerializer

    def create(self, request, *args, **kwargs):
        entree = NouveauRapportBureauSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        instance = entree.save(agent=request.user)

        try:
            with instance.fichier.open('rb') as f:
                resultat = importer_rapport_bureau(f)
        except ImportRapportBureauError as exc:
            instance.delete()
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        instance.nb_parcelles        = resultat['nb_parcelles']
        instance.superficie_totale   = resultat['superficie_totale']
        instance.repartition_village = resultat['repartition_village']
        instance.save(update_fields=['nb_parcelles', 'superficie_totale', 'repartition_village'])

        out = RapportBureauSerializer(instance, context={'request': request})
        payload = {**out.data, 'errors': resultat['errors']}
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Planning Bureau'],
        summary='Tableau de bord — aujourd\'hui / cette semaine / ce mois',
        description=(
            'Retourne, pour chaque période (aujourd\'hui, semaine en cours, mois en cours) et '
            'chaque type de traitement, le nombre d\'agents distincts, le nombre de parcelles/PDF '
            'et la superficie totale (ha). Accepte les mêmes filtres que la liste.'
        ),
        parameters=FILTER_PARAMETERS,
        responses={200: {
            'type': 'object',
            'properties': {
                p: {
                    'type': 'object',
                    'additionalProperties': {
                        'type': 'object',
                        'properties': {
                            'nb_agents':          {'type': 'integer'},
                            'nb_parcelles':        {'type': 'integer'},
                            'superficie_totale':   {'type': 'number'},
                        },
                    },
                } for p in ('aujourd_hui', 'cette_semaine', 'ce_mois')
            },
        }},
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        qs = self.get_queryset()
        today         = timezone.localdate()
        debut_semaine = today - datetime.timedelta(days=today.weekday())
        debut_mois    = today.replace(day=1)
        return Response({
            'aujourd_hui':   self._bucket(qs.filter(date=today)),
            'cette_semaine': self._bucket(qs.filter(date__gte=debut_semaine, date__lte=today)),
            'ce_mois':       self._bucket(qs.filter(date__gte=debut_mois, date__lte=today)),
        })

    @staticmethod
    def _bucket(qs):
        result = {}
        for key, _label in RapportBureau.TYPE_CHOICES:
            sub = qs.filter(type_traitement=key)
            agg = sub.aggregate(nb_parcelles=Sum('nb_parcelles'), superficie_totale=Sum('superficie_totale'))
            result[key] = {
                'nb_agents':          sub.exclude(agent__isnull=True).values('agent').distinct().count(),
                'nb_parcelles':       agg['nb_parcelles'] or 0,
                'superficie_totale':  round(agg['superficie_totale'] or 0.0, 2),
            }
        return result

    @extend_schema(
        tags=['Planning Bureau'],
        summary='Export Excel des rapports bureau',
        description='Exporte les rapports filtrés (mêmes filtres que la liste) au format XLSX.',
        parameters=FILTER_PARAMETERS,
        responses={200: {'description': 'Fichier XLSX'}},
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        qs = self.get_queryset()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Rapports Bureau'
        headers = [
            'Date', 'Agent', 'Type', 'Vague', 'Nb parcelles', 'Superficie (ha)',
            'Région', 'Département', 'Zone', 'Observations',
        ]
        ws.append(headers)
        for r in qs:
            agent_nom = (f'{r.agent.first_name} {r.agent.last_name}'.strip() or r.agent.username) if r.agent else '—'
            ws.append([
                r.date.isoformat(), agent_nom, r.get_type_traitement_display(),
                r.vague.nom if r.vague_id else '', r.nb_parcelles, r.superficie_totale,
                r.region.nom, r.departement.nom, r.zone.nom, r.observations,
            ])
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="rapports_bureau.xlsx"'
        wb.save(response)
        return response
