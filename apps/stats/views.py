from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import connections, OperationalError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import FaitAgrege
from .serializers import FaitAgregeSerializer
from apps.dossiers.models import Dossier, Contrat
from apps.controle.models import ControleQualite, AnomalieControle
from apps.referentiel.models import Village, Zone
from apps.geo.db import db_alias, VALID_ZONES
from apps.geo.queries import discover_cf_schema_tables, filter_schema_tables_by_statut, compute_stats


def _parcelles_levees(zone_nom: str) -> dict:
    """Nombre de parcelles levées et leur superficie totale (ha), lus directement dans la couche
    PostGIS `cf_poly_parcelle_leve` (une ligne = une parcelle levée sur le terrain, une par
    sous-préfecture) de la base spatiale de la zone — jamais depuis `Dossier` (table métier, qui
    ne reflète que les dossiers administratifs créés dans AtlasCAG, pas l'état réel du relevé
    terrain : une parcelle peut être levée dans DIGIFOR sans qu'aucun dossier n'ait encore été
    créé côté métier, ce qui est notamment tout le cas de la zone Cavally aujourd'hui).

    Tolérant aux pannes : la base spatiale distante (OVH) peut être temporairement indisponible,
    auquel cas on retombe sur {0, 0} plutôt que de faire échouer tout le tableau de bord."""
    alias = db_alias((zone_nom or '').strip().lower())
    if (zone_nom or '').strip().lower() not in VALID_ZONES or alias not in connections.databases:
        return {'nb': 0, 'superficie_ha': 0.0}
    try:
        with connections[alias].cursor() as cursor:
            leve_tables = filter_schema_tables_by_statut(discover_cf_schema_tables(cursor), 'LEVE')
            stats = compute_stats(cursor, leve_tables, exact_filters={})
    except OperationalError:
        return {'nb': 0, 'superficie_ha': 0.0}
    return stats.get('LEVE', {'nb': 0, 'superficie_ha': 0.0})


def _cf_breakdown(qs, *, parcelles_levees):
    """Répartition des dossiers CF selon `statut_publicite` (workflow métier du circuit
    Publicité — cf. apps.dossiers.models.Dossier.STATUT_PUBLICITE_CHOICES), jamais `statut_cf`
    (COUCHE, l'emplacement physique PostGIS de la parcelle) ni `statut` (générique). « Traité »
    correspond à `EN_PUBLICITE` : un dossier déjà engagé dans le circuit, en attente de décision.

    `total`/`superficie_totale` viennent de `parcelles_levees` (cf. `_parcelles_levees`), PAS
    d'un comptage sur `Dossier` : le nombre de parcelles réellement levées sur le terrain et
    leur superficie doivent refléter la couche PostGIS `cf_poly_parcelle_leve`, source de vérité
    du relevé terrain, indépendamment du nombre de dossiers administratifs déjà créés."""
    return {
        'total':             parcelles_levees['nb'],
        'superficie_totale': round(parcelles_levees['superficie_ha'], 2),
        'traite':            qs.filter(statut_publicite='EN_PUBLICITE').count(),
        'approuve':          qs.filter(statut_publicite='APPROUVE').count(),
        'rejete':            qs.filter(statut_publicite='REJETE').count(),
        'valide':            qs.filter(statut_publicite='VALIDE').count(),
    }


def _dtv_breakdown(qs):
    """Répartition des villages selon la progression DTV réelle (apps.referentiel.models.DTV) —
    un village sans DTV créé n'est compté dans aucune des 4 étapes, seulement dans `total`."""
    return {
        'total':       qs.count(),
        'valides':     qs.filter(dtv__valide=True).count(),
        'approuves':   qs.filter(dtv__approuve=True).count(),
        'delimites':   qs.filter(dtv__delimite=True).count(),
        'pub_ouverte': qs.filter(dtv__publicite_ouverte=True).count(),
    }


@extend_schema(
    tags=['Statistiques'],
    summary='Tableau de bord principal',
    description=(
        'Retourne tous les KPIs pour l\'écran d\'accueil du tableau de bord :\n\n'
        '- **kpis.dossiers** : total, en cours, validés, rejetés (tous types de dossiers)\n'
        '- **kpis.cf** : total (parcelles levées) et superficie totale (ha) lus directement '
        'dans la couche PostGIS `cf_poly_parcelle_leve`, + répartition des dossiers CF par '
        '`statut_publicite` — traité (en publicité), approuvé, rejeté, validé\n'
        '- **kpis.contrats** : total, signés\n'
        '- **kpis.anomalies** : total, non corrigées, bloquantes\n'
        '- **kpis.controles** : validés, rejetés\n'
        '- **kpis.villages** : total, validés, approuvés, délimités, publication ouverte\n'
        '- **recents** : 8 derniers dossiers créés\n'
        '- **anomalies** : 6 dernières anomalies non corrigées\n'
        '- **par_zone** : dossiers/contrats(+signés)/villages/anomalies(+bloquantes)/CF/DTV, '
        'chacun calculé exclusivement sur la zone concernée — permet de reproduire les 4 KPI '
        'principaux (CF, contrats, anomalies, villages DTV) séparément pour chaque zone'
    ),
    responses={
        200: {
            'type': 'object',
            'properties': {
                'kpis': {
                    'type': 'object',
                    'properties': {
                        'dossiers':  {'type': 'object'},
                        'cf':        {'type': 'object'},
                        'contrats':  {'type': 'object'},
                        'anomalies': {'type': 'object'},
                        'controles': {'type': 'object'},
                        'villages':  {'type': 'object'},
                    },
                },
                'recents':   {'type': 'array', 'items': {'type': 'object'}},
                'anomalies': {'type': 'array', 'items': {'type': 'object'}},
                'par_zone':  {'type': 'array', 'items': {'type': 'object'}},
            },
        }
    },
)
class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ── KPIs principaux ────────────────────────────────
        total_dossiers     = Dossier.objects.count()
        dossiers_en_cours  = Dossier.objects.filter(statut='EN_COURS').count()
        dossiers_valides   = Dossier.objects.filter(statut='VALIDE').count()
        dossiers_rejetes   = Dossier.objects.filter(statut='REJETE').count()

        # Une seule lecture de la couche PostGIS `cf_poly_parcelle_leve` par zone (2 requêtes
        # au total), réutilisée à la fois pour le cumul global et pour chaque zone ci-dessous —
        # jamais recalculée depuis `Dossier`.
        zones = list(Zone.objects.all())
        levees_par_zone = {z.id: _parcelles_levees(z.nom) for z in zones}
        levees_globales = {
            'nb':            sum(s['nb'] for s in levees_par_zone.values()),
            'superficie_ha': sum(s['superficie_ha'] for s in levees_par_zone.values()),
        }
        cf_global = _cf_breakdown(Dossier.objects.filter(type_dossier='CF'), parcelles_levees=levees_globales)

        total_contrats     = Contrat.objects.count()
        contrats_signes    = Contrat.objects.filter(statut='SIGNE').count()

        total_anomalies    = AnomalieControle.objects.count()
        anom_non_corr      = AnomalieControle.objects.filter(corrigee=False).count()
        anom_bloquantes    = AnomalieControle.objects.filter(gravite='BLOQUANTE', corrigee=False).count()

        controles_rejetes  = ControleQualite.objects.filter(statut='REJETE').count()
        controles_valides  = ControleQualite.objects.filter(statut='VALIDE').count()

        # ── Villages DTV (les étapes de progression vivent sur DTV, pas sur Village) ──
        villages_global = _dtv_breakdown(Village.objects.all())

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

        # ── Par zone — CF et DTV calculés séparément et exclusivement sur les dossiers/villages
        # de la zone concernée (aucun mélange entre Cavally et Worodougou). Inclut les mêmes
        # compteurs que les KPI globaux (contrats signés, anomalies) pour permettre de reproduire
        # à l'identique, par zone, les 4 cartes de la ligne d'indicateurs principaux. ──────────
        par_zone = []
        for z in zones:
            par_zone.append({
                'zone':     z.nom,
                'zone_id':  z.id,
                'dossiers': Dossier.objects.filter(zone=z).count(),
                'en_cours': Dossier.objects.filter(zone=z, statut='EN_COURS').count(),
                'valides':  Dossier.objects.filter(zone=z, statut='VALIDE').count(),
                'contrats':        Contrat.objects.filter(dossier__zone=z).count(),
                'contrats_signes': Contrat.objects.filter(dossier__zone=z, statut='SIGNE').count(),
                'villages': Village.objects.filter(zone=z).count(),
                'anomalies_non_corr':   AnomalieControle.objects.filter(
                    corrigee=False, controle__dossier__zone=z).count(),
                'anomalies_bloquantes': AnomalieControle.objects.filter(
                    corrigee=False, gravite='BLOQUANTE', controle__dossier__zone=z).count(),
                'cf':       _cf_breakdown(
                    Dossier.objects.filter(zone=z, type_dossier='CF'),
                    parcelles_levees=levees_par_zone[z.id],
                ),
                'dtv':      _dtv_breakdown(Village.objects.filter(zone=z)),
            })

        return Response({
            'kpis': {
                'dossiers':  {'total': total_dossiers, 'en_cours': dossiers_en_cours,
                              'valides': dossiers_valides, 'rejetes': dossiers_rejetes},
                'cf':        cf_global,
                'contrats':  {'total': total_contrats, 'signes': contrats_signes},
                'anomalies': {'total': total_anomalies, 'non_corr': anom_non_corr,
                              'bloquantes': anom_bloquantes},
                'controles': {'valides': controles_valides, 'rejetes': controles_rejetes},
                'villages':  villages_global,
            },
            'recents':   recents_data,
            'anomalies': anom_data,
            'par_zone':  par_zone,
        })


@extend_schema_view(
    list=extend_schema(
        tags=['Statistiques'],
        summary='Faits agrégés par période',
        description=(
            'Retourne les faits agrégés (snapshots périodiques) calculés par le système. '
            'Filtrable par zone, période et source.'
        ),
        parameters=[
            OpenApiParameter('zone',    description='ID de la zone', required=False),
            OpenApiParameter('periode', description='Période au format YYYY-MM (ex: 2026-07)', required=False),
            OpenApiParameter('source',  description='Source du fait agrégé', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Statistiques'],
        summary='Détail d\'un fait agrégé',
    ),
)
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
