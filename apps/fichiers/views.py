from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
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
        description='Importe la liste Excel des parcelles envoyées en publicité pour un village. **multipart/form-data**.',
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
            'village__zone', 'televerse_par'
        ).order_by('-televerse_le')
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

    def perform_create(self, serializer):
        fichier = self.request.FILES.get('fichier')
        taille  = fichier.size if fichier else None
        serializer.save(televerse_par=self.request.user, taille=taille)
