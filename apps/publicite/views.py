from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dossiers.models import Dossier
from .models import HistoriqueMigrationCouche
from .serializers import HistoriqueMigrationCoucheSerializer
from .services import MigrationError, migrer_parcelle

# Noms des tables PostGIS pilotées par le workflow de publicité (une par statut CF).
# 'cf_poly_parcelle_Def' est centralisée (schéma public, toutes sous-préfectures) ; les
# quatre autres sont scopées par sous-préfecture (cf. apps/publicite/management/commands/
# create_publicite_layers.py pour la création de cf_parcelle_approuvee/validee).
CF_DEF_TABLE          = 'cf_poly_parcelle_Def'
CF_EN_PUBLICITE_TABLE = 'cf_parcelle_en_publicite'
CF_APPROUVEE_TABLE    = 'cf_parcelle_approuvee'
CF_REJETEE_TABLE      = 'cf_parcelle_rejete'
CF_VALIDEE_TABLE      = 'cf_parcelle_validee'


def _zone_str(dossier: Dossier) -> str:
    return (dossier.zone.nom or '').strip().lower()


TRANSITION_RESPONSE = {
    200: {
        'type': 'object',
        'properties': {
            'id':             {'type': 'integer'},
            'numero_dossier': {'type': 'string'},
            'statut_cf':      {'type': 'string'},
        },
    },
    400: {'description': 'Précondition de statut non respectée, num_demand manquant ou zone non reconnue'},
    404: {'description': 'Dossier introuvable'},
    502: {'description': 'Migration spatiale impossible (parcelle introuvable, couche cible absente…)'},
}


class _TransitionView(APIView):
    """Vue de base pour une transition du workflow de publicité : vérifie la précondition
    de statut, résout la zone géographique du dossier, puis délègue la migration
    spatiale + mise à jour métier au service `migrer_parcelle`."""

    permission_classes = [IsAuthenticated]
    statut_attendu: str
    table_source: str
    table_cible: str
    nouveau_statut: str

    def post(self, request, dossier_id):
        try:
            dossier = Dossier.objects.select_related('zone').get(pk=dossier_id)
        except Dossier.DoesNotExist:
            return Response({'detail': 'Dossier introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if dossier.statut_cf != self.statut_attendu:
            return Response(
                {'detail': (
                    f"Transition impossible : statut_cf actuel = {dossier.statut_cf!r}, "
                    f"attendu {self.statut_attendu!r}."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not dossier.num_demand:
            return Response(
                {'detail': 'Le dossier ne porte pas de num_demand — migration impossible.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        zone = _zone_str(dossier)
        if zone not in {'cavally', 'worodougou'}:
            return Response({'detail': f"Zone du dossier non reconnue : {zone!r}."}, status=400)

        try:
            migrer_parcelle(
                zone=zone, dossier=dossier,
                table_source=self.table_source, table_cible=self.table_cible,
                nouveau_statut=self.nouveau_statut, user=request.user,
            )
        except MigrationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'id':             dossier.id,
            'numero_dossier': dossier.numero_dossier,
            'statut_cf':      dossier.statut_cf,
        })


@extend_schema(
    tags=['Publicité'],
    summary='Mettre un dossier CF en publicité',
    description=(
        'Requiert `statut_cf == DEF`. Migre la parcelle (identifiée par `NUM_DEMAND`) de la '
        'couche **CF – Définitif** vers **CF – En publicité**, puis passe `statut_cf` à '
        '`EN_PUBLICITE`.'
    ),
    request=None,
    responses=TRANSITION_RESPONSE,
)
class MettreEnPubliciteView(_TransitionView):
    statut_attendu = 'DEF'
    table_source   = CF_DEF_TABLE
    table_cible    = CF_EN_PUBLICITE_TABLE
    nouveau_statut = 'EN_PUBLICITE'


@extend_schema(
    tags=['Publicité'],
    summary='Approuver un dossier CF en publicité',
    description=(
        'Requiert `statut_cf == EN_PUBLICITE`. Migre la parcelle de **CF – En publicité** '
        'vers **CF – Approuvée**, puis passe `statut_cf` à `APPROUVE`.'
    ),
    request=None,
    responses=TRANSITION_RESPONSE,
)
class ApprouverView(_TransitionView):
    statut_attendu = 'EN_PUBLICITE'
    table_source   = CF_EN_PUBLICITE_TABLE
    table_cible    = CF_APPROUVEE_TABLE
    nouveau_statut = 'APPROUVE'


@extend_schema(
    tags=['Publicité'],
    summary='Rejeter un dossier CF en publicité',
    description=(
        'Requiert `statut_cf == EN_PUBLICITE`. Migre la parcelle de **CF – En publicité** '
        'vers **CF – Rejetée**, puis passe `statut_cf` à `REJETE`.'
    ),
    request=None,
    responses=TRANSITION_RESPONSE,
)
class RejeterView(_TransitionView):
    statut_attendu = 'EN_PUBLICITE'
    table_source   = CF_EN_PUBLICITE_TABLE
    table_cible    = CF_REJETEE_TABLE
    nouveau_statut = 'REJETE'


@extend_schema(
    tags=['Publicité'],
    summary='Valider un dossier CF approuvé',
    description=(
        'Requiert `statut_cf == APPROUVE`. Migre la parcelle de **CF – Approuvée** vers '
        '**CF – Validée** (état final du workflow), puis passe `statut_cf` à `VALIDE`.'
    ),
    request=None,
    responses=TRANSITION_RESPONSE,
)
class ValiderView(_TransitionView):
    statut_attendu = 'APPROUVE'
    table_source   = CF_APPROUVEE_TABLE
    table_cible    = CF_VALIDEE_TABLE
    nouveau_statut = 'VALIDE'


@extend_schema(
    tags=['Publicité'],
    summary="Historique des migrations de couches d'un dossier",
    description=(
        'Retourne toutes les tentatives de migration de couche pour ce dossier, y compris '
        'les échecs (`succes=false`), pour audit et réconciliation manuelle si nécessaire.'
    ),
    responses=HistoriqueMigrationCoucheSerializer(many=True),
)
class HistoriqueMigrationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dossier_id):
        qs = HistoriqueMigrationCouche.objects.filter(dossier_id=dossier_id)
        return Response(HistoriqueMigrationCoucheSerializer(qs, many=True).data)
