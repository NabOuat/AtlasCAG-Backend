import io
import zipfile

from django.http import HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from apps.referentiel.models import Village
from apps.dossiers.models import VagueEnvoi
from .models import FichierDossier, FichierExcelPublicite
from .serializers import FichierDossierSerializer, FichierExcelPubliciteSerializer
from .services import importer_excel_publicite, ImportExcelPubliciteError


@extend_schema_view(
    list=extend_schema(
        tags=['Fichiers'],
        summary='Liste des fichiers',
        description='Retourne tous les fichiers attachés aux dossiers. Filtrable par dossier, village, sous-préfecture, type et zone.',
        parameters=[
            OpenApiParameter('dossier',      description='ID du dossier', required=False),
            OpenApiParameter('village',      description='ID du village', required=False),
            OpenApiParameter('sous_pref',    description='Nom partiel de la sous-préfecture', required=False),
            OpenApiParameter('type_fichier', description='`PLAN`, `PV`, `PHOTO`, `DOCUMENT`, `RAPPORT`, `AUTRE`', required=False),
            OpenApiParameter('zone',         description='ID de la zone', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Fichiers'], summary='Détail d\'un fichier'),
    create=extend_schema(
        tags=['Fichiers'],
        summary='Uploader un fichier',
        description=(
            'Attache un fichier à un dossier (résolu par ID, `numero_dossier` ou `num_demand` — '
            'voir `DossierPKOuCodeField`). Envoyer en **multipart/form-data**.\n\n'
            '**Un seul plan par dossier** : si un fichier de type `PLAN` existe déjà pour ce '
            'dossier, il est supprimé (fichier physique inclus) avant l\'enregistrement du nouveau.'
        ),
        request={'multipart/form-data': FichierDossierSerializer},
    ),
    update=extend_schema(tags=['Fichiers'], summary='Modifier les métadonnées d\'un fichier'),
    partial_update=extend_schema(tags=['Fichiers'], summary='Modifier partiellement un fichier'),
    destroy=extend_schema(tags=['Fichiers'], summary='Supprimer un fichier'),
)
class FichierViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = FichierDossierSerializer

    def get_queryset(self):
        qs           = FichierDossier.objects.select_related(
            'dossier__village', 'dossier__zone', 'televerse_par'
        ).order_by('-televerse_le')
        dossier      = self.request.query_params.get('dossier')
        village      = self.request.query_params.get('village')
        sous_pref    = self.request.query_params.get('sous_pref')
        type_fichier = self.request.query_params.get('type_fichier')
        zone         = self.request.query_params.get('zone')
        if dossier:      qs = qs.filter(dossier__id=dossier)
        if village:      qs = qs.filter(dossier__village__id=village)
        if sous_pref:    qs = qs.filter(dossier__village__sous_prefecture__icontains=sous_pref)
        if type_fichier: qs = qs.filter(type_fichier=type_fichier)
        if zone:         qs = qs.filter(dossier__zone__id=zone)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        fichier      = self.request.FILES.get('fichier')
        taille       = fichier.size if fichier else None
        type_fichier = serializer.validated_data.get('type_fichier') or 'AUTRE'
        dossier      = serializer.validated_data.get('dossier')

        # Un seul plan par dossier — le nouveau remplace l'ancien (fichier physique effacé,
        # pas seulement l'enregistrement). Cf. LOGIQUE_METIER_PUBLICITE.pdf §4.
        if type_fichier == 'PLAN' and dossier is not None:
            ancien = FichierDossier.objects.filter(dossier=dossier, type_fichier='PLAN').first()
            if ancien:
                ancien.fichier.delete(save=False)
                ancien.delete()

        serializer.save(televerse_par=self.request.user, taille=taille)

    @extend_schema(
        tags=['Fichiers'],
        summary='Télécharger en masse les plans PDF de plusieurs dossiers (ZIP)',
        description=(
            'Prend une liste d\'IDs de dossiers et retourne une archive ZIP contenant le plan '
            '(type `PLAN`) de chacun, préfixé par son `numero_dossier` pour éviter les collisions '
            'de noms. Les dossiers sans PDF sont ignorés silencieusement.'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {'dossiers': {'type': 'array', 'items': {'type': 'integer'}}},
                'required': ['dossiers'],
            }
        },
        responses={200: {'description': 'Archive ZIP (application/zip)'}, 400: {'description': 'Liste de dossiers manquante'}},
    )
    @action(detail=False, methods=['post'], url_path='telecharger-zip')
    def telecharger_zip(self, request):
        dossier_ids = request.data.get('dossiers') or []
        if not isinstance(dossier_ids, list) or not dossier_ids:
            return Response({'detail': "Le champ 'dossiers' (liste d'IDs) est requis."}, status=status.HTTP_400_BAD_REQUEST)

        plans = (
            FichierDossier.objects
            .filter(dossier_id__in=dossier_ids, type_fichier='PLAN')
            .select_related('dossier')
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for plan in plans:
                if not plan.fichier:
                    continue
                ext = plan.fichier.name.rsplit('.', 1)[-1] if '.' in plan.fichier.name else 'pdf'
                arcname = f'{plan.dossier.numero_dossier}.{ext}'
                try:
                    with plan.fichier.open('rb') as f:
                        zf.writestr(arcname, f.read())
                except Exception:
                    continue  # fichier physique manquant — ignoré silencieusement, pas de dossier bloquant

        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="plans_cf.zip"'
        return response


@extend_schema_view(
    list=extend_schema(
        tags=['Fichiers'],
        summary='Liste des fichiers Excel de publicité',
        description='Retourne les fichiers Excel des listes de parcelles envoyées en publicité. Filtrable par village, sous-préfecture et zone.',
        parameters=[
            OpenApiParameter('village',   description='ID du village', required=False),
            OpenApiParameter('sous_pref', description='Nom partiel de la sous-préfecture', required=False),
            OpenApiParameter('zone',      description='ID de la zone', required=False),
        ],
    ),
    retrieve=extend_schema(tags=['Fichiers'], summary='Détail d\'un fichier Excel publicité'),
    create=extend_schema(
        tags=['Fichiers'],
        summary='Importer un fichier Excel de publicité',
        description=(
            'Importe en masse une liste de parcelles pour un village et une vague d\'envoi '
            'donnés (**multipart/form-data**, champs `fichier`, `village`, `vague_envoi`, `nom`, '
            '`description`). Chaque ligne est upsertée en `Dossier` (clé `NUM_DEMAND` '
            '[+ N° PARCELLE]). Ne modifie jamais `statut_cf` ; ne fait passer `statut_publicite` '
            'à `EN_PUBLICITE` que pour un dossier qui n\'en a encore aucun. Voir '
            'LOGIQUE_METIER_PUBLICITE.pdf §3 pour le détail des colonnes reconnues.'
        ),
        request={'multipart/form-data': FichierExcelPubliciteSerializer},
    ),
    update=extend_schema(tags=['Fichiers'], summary='Modifier un fichier Excel publicité'),
    partial_update=extend_schema(tags=['Fichiers'], summary='Modifier partiellement un fichier Excel publicité'),
    destroy=extend_schema(tags=['Fichiers'], summary='Supprimer un fichier Excel publicité'),
)
class ExcelPubliciteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = FichierExcelPubliciteSerializer

    def get_queryset(self):
        qs        = FichierExcelPublicite.objects.select_related('village__zone', 'vague_envoi', 'televerse_par').order_by('-televerse_le')
        village   = self.request.query_params.get('village')
        sous_pref = self.request.query_params.get('sous_pref')
        zone      = self.request.query_params.get('zone')
        if village:   qs = qs.filter(village__id=village)
        if sous_pref: qs = qs.filter(village__sous_prefecture__icontains=sous_pref)
        if zone:      qs = qs.filter(village__zone__id=zone)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        village     = serializer.validated_data['village']
        vague_envoi = serializer.validated_data.get('vague_envoi')
        fichier     = request.FILES.get('fichier')

        if not isinstance(village, Village):
            return Response({'detail': 'village invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        # vague_envoi est nullable au niveau du modèle (un enregistrement FichierExcelPublicite
        # peut exister sans vague dans d'autres contextes), mais obligatoire pour cette action
        # d'import (cf. LOGIQUE_METIER_PUBLICITE.pdf §3.1, « Vague de publicité * ») — sans ce
        # contrôle, une requête l'omettant écraserait silencieusement à None la vague déjà
        # rattachée à un dossier existant lors d'une mise à jour.
        if vague_envoi is None:
            return Response({'detail': 'vague_envoi requis.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(vague_envoi, VagueEnvoi):
            return Response({'detail': 'vague_envoi invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        if not fichier:
            return Response({'detail': 'fichier requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            resultat = importer_excel_publicite(
                fichier=fichier, village=village, vague_envoi=vague_envoi, user=request.user,
            )
        except ImportExcelPubliciteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        fichier.seek(0)
        instance = serializer.save(
            televerse_par=request.user, taille=fichier.size,
            nb_parcelles=resultat['nb_parcelles'], nb_crees=resultat['nb_crees'],
            nb_maj=resultat['nb_maj'], superficie_totale=resultat['superficie_totale'],
            erreurs=resultat['erreurs'],
        )
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)
