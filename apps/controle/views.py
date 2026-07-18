from rest_framework import viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count, Q
from .models import ControleQualite, AnomalieControle, EnvoiEntreprise
from .serializers import ControleListSerializer, ControleDetailSerializer, AnomalieSerializer, EnvoiSerializer


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
        # Récupérer le dernier contrôle pour ce dossier
        dernier = ControleQualite.objects.filter(dossier=d).order_by('-cree_le').first()
        results.append({
            'id':                  d.id,
            'numero_dossier':      d.numero_dossier,
            'village_id':          d.village_id,
            'village_nom':         d.village.nom,
            'zone_nom':            d.zone.nom,
            'statut':              d.statut,
            'statut_cf':           d.statut_cf,
            # DIGIFOR
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
            # Fichiers
            'plans':               plans,
            'nb_plans':            len(plans),
            # Dernier contrôle
            'controle_statut':     dernier.statut if dernier else None,
            'controle_id':         dernier.id     if dernier else None,
        })

    return Response({'count': len(results), 'results': results})
