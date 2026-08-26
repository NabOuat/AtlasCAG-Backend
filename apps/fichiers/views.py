import zipfile
from io import BytesIO

from django.http import HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from apps.dossiers.services import ImportADSError, importer_excel_publicite
from .models import FichierDossier, FichierExcelPublicite
from .serializers import FichierDossierSerializer, FichierExcelPubliciteSerializer


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
        description='Attache un fichier à un dossier. Envoyer en **multipart/form-data**.',
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
        fichier = self.request.FILES.get('fichier')
        taille  = fichier.size if fichier else None
        serializer.save(televerse_par=self.request.user, taille=taille)

    @extend_schema(
        tags=['Fichiers'],
        summary='Télécharger plusieurs plans PDF en une archive ZIP',
        description=(
            'Regroupe et télécharge en une seule archive ZIP tous les plans PDF (`type_fichier`'
            ' = `PLAN`) des dossiers dont les ID sont fournis — utilisé par la sélection multiple'
            ' du Canevas Publicité. Les dossiers sans PDF sont ignorés silencieusement (pas'
            ' d\'erreur) ; un dossier ayant plusieurs plans les inclut tous.\n\n'
            '**Corps** : `{ "dossiers": [12, 45, 78, ...] }`'
        ),
        request={'application/json': {
            'type': 'object',
            'properties': {'dossiers': {'type': 'array', 'items': {'type': 'integer'}}},
            'required': ['dossiers'],
        }},
        responses={
            200: {'description': 'Archive ZIP (application/zip)'},
            400: {'description': 'Champ "dossiers" manquant ou vide'},
            404: {'description': 'Aucun PDF trouvé pour les dossiers fournis'},
        },
    )
    @action(detail=False, methods=['post'], url_path='telecharger-zip')
    def telecharger_zip(self, request):
        ids = request.data.get('dossiers')
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'Le champ "dossiers" (liste d\'ID) est requis et ne peut pas être vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fichiers = FichierDossier.objects.filter(
            dossier_id__in=ids, type_fichier='PLAN',
        ).select_related('dossier').order_by('dossier_id', 'televerse_le')

        if not fichiers.exists():
            return Response(
                {'detail': 'Aucun PDF trouvé pour les dossiers sélectionnés.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        buffer = BytesIO()
        used_names: set[str] = set()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for f in fichiers:
                if not f.fichier:
                    continue
                # Préfixe par le numéro de dossier pour que le nom reste lisible et unique même
                # si plusieurs dossiers ont téléversé un fichier au même nom de base.
                stem = f'{f.dossier.numero_dossier}_{f.nom}'.replace('/', '-').strip() or f'fichier_{f.id}'
                name, n = f'{stem}.pdf', 1
                while name in used_names:
                    name = f'{stem}_{n}.pdf'
                    n += 1
                used_names.add(name)
                with f.fichier.open('rb') as fh:
                    archive.writestr(name, fh.read())

        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="plans_publicite.zip"'
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
            'Importe la liste Excel des parcelles envoyées en publicité pour un village et une '
            'vague donnés (`vague` requis). Chaque ligne (une parcelle) crée ou complète le '
            '`Dossier` correspondant — identifié par `NUM_DEMAND`, sans jamais dupliquer un '
            'import déjà effectué. **multipart/form-data**.'
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
        qs        = FichierExcelPublicite.objects.select_related(
            'village__zone', 'vague', 'televerse_par'
        ).order_by('-televerse_le')
        village   = self.request.query_params.get('village')
        sous_pref = self.request.query_params.get('sous_pref')
        zone      = self.request.query_params.get('zone')
        vague     = self.request.query_params.get('vague')
        if village:   qs = qs.filter(village__id=village)
        if sous_pref: qs = qs.filter(village__sous_prefecture__icontains=sous_pref)
        if zone:      qs = qs.filter(village__zone__id=zone)
        if vague:     qs = qs.filter(vague__id=vague)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fichier  = request.FILES.get('fichier')
        taille   = fichier.size if fichier else None
        instance = serializer.save(televerse_par=request.user, taille=taille)

        try:
            with instance.fichier.open('rb') as f:
                resultat = importer_excel_publicite(
                    fichier=f, zone=instance.village.zone,
                    village=instance.village, vague=instance.vague,
                    user=request.user,
                )
        except ImportADSError as exc:
            instance.delete()
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        instance.nb_parcelles      = resultat['nb_parcelles']
        instance.nb_crees          = resultat['created']
        instance.nb_maj            = resultat['updated']
        instance.superficie_totale = resultat['superficie_totale']
        instance.erreurs           = resultat['errors']
        instance.save(update_fields=['nb_parcelles', 'nb_crees', 'nb_maj', 'superficie_totale', 'erreurs'])

        headers = self.get_success_headers(serializer.data)
        out = self.get_serializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)
