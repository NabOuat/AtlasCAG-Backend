from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import FaitAgrege, ObjectifPeriode
from .serializers import FaitAgregeSerializer, ObjectifPeriodeSerializer
from apps.dossiers.models import Dossier, Contrat
from apps.controle.models import ControleQualite, AnomalieControle
from apps.referentiel.models import Village, Zone


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ── KPIs principaux ────────────────────────────────
        total_dossiers     = Dossier.objects.count()
        dossiers_en_cours  = Dossier.objects.filter(statut='EN_COURS').count()
        dossiers_valides   = Dossier.objects.filter(statut='VALIDE').count()
        dossiers_rejetes   = Dossier.objects.filter(statut='REJETE').count()

        total_contrats     = Contrat.objects.count()
        contrats_signes    = Contrat.objects.filter(statut='SIGNE').count()

        total_anomalies    = AnomalieControle.objects.count()
        anom_non_corr      = AnomalieControle.objects.filter(corrigee=False).count()
        anom_bloquantes    = AnomalieControle.objects.filter(gravite='BLOQUANTE', corrigee=False).count()

        controles_rejetes  = ControleQualite.objects.filter(statut='REJETE').count()
        controles_valides  = ControleQualite.objects.filter(statut='VALIDE').count()

        # ── Villages DTV ───────────────────────────────────
        villages_total     = Village.objects.count()
        villages_valides   = Village.objects.filter(valide=True).count()
        villages_approuves = Village.objects.filter(approuve=True).count()
        villages_delimites = Village.objects.filter(delimite=True).count()

        # ── Dossiers récents ───────────────────────────────
        recents = Dossier.objects.select_related('village', 'zone').order_by('-cree_le')[:8]
        recents_data = [
            {
                'id':           d.id,
                'numero':       d.numero_dossier,
                'village':      d.village.nom,
                'zone':         d.zone.nom,
                'type_dossier': d.type_dossier,
                'statut':       d.statut,
                'cree_le':      d.cree_le.isoformat(),
            }
            for d in recents
        ]

        # ── Anomalies récentes non corrigées ───────────────
        anom_recentes = (
            AnomalieControle.objects
            .filter(corrigee=False)
            .select_related('controle__dossier__village', 'controle__dossier__zone')
            .order_by('-controle__cree_le')[:6]
        )
        anom_data = [
            {
                'id':          a.id,
                'description': a.description,
                'gravite':     a.gravite,
                'dossier':     a.controle.dossier.numero_dossier,
                'village':     a.controle.dossier.village.nom,
                'zone':        a.controle.dossier.zone.nom,
            }
            for a in anom_recentes
        ]

        # ── Par zone ───────────────────────────────────────
        par_zone = []
        for z in Zone.objects.all():
            par_zone.append({
                'zone':     z.nom,
                'dossiers': Dossier.objects.filter(zone=z).count(),
                'en_cours': Dossier.objects.filter(zone=z, statut='EN_COURS').count(),
                'valides':  Dossier.objects.filter(zone=z, statut='VALIDE').count(),
                'contrats': Contrat.objects.filter(dossier__zone=z).count(),
                'villages': Village.objects.filter(zone=z).count(),
            })

        return Response({
            'kpis': {
                'dossiers':  {'total': total_dossiers, 'en_cours': dossiers_en_cours,
                              'valides': dossiers_valides, 'rejetes': dossiers_rejetes},
                'contrats':  {'total': total_contrats, 'signes': contrats_signes},
                'anomalies': {'total': total_anomalies, 'non_corr': anom_non_corr,
                              'bloquantes': anom_bloquantes},
                'controles': {'valides': controles_valides, 'rejetes': controles_rejetes},
                'villages':  {'total': villages_total, 'valides': villages_valides,
                              'approuves': villages_approuves, 'delimites': villages_delimites},
            },
            'recents':   recents_data,
            'anomalies': anom_data,
            'par_zone':  par_zone,
        })


class FaitAgregeViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = FaitAgregeSerializer

    def get_queryset(self):
        qs      = FaitAgrege.objects.select_related('village', 'zone').order_by('-periode')
        zone    = self.request.query_params.get('zone')
        periode = self.request.query_params.get('periode')
        source  = self.request.query_params.get('source')
        if zone:    qs = qs.filter(zone__id=zone)
        if periode: qs = qs.filter(periode=periode)
        if source:  qs = qs.filter(source=source)
        return qs
