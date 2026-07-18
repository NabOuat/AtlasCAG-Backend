from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import FichierDossier
from .serializers import FichierDossierSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Fichiers'],
        summary='Liste des fichiers',
        description='Retourne tous les fichiers attachés aux dossiers. Filtrable par dossier.',
        parameters=[
            OpenApiParameter('dossier', description='ID du dossier pour filtrer ses fichiers', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Fichiers'],
        summary='Détail d\'un fichier',
        description='Retourne les métadonnées d\'un fichier avec son URL de téléchargement.',
    ),
    create=extend_schema(
        tags=['Fichiers'],
        summary='Uploader un fichier',
        description=(
            'Attache un fichier à un dossier. Envoyer en **multipart/form-data**.\n\n'
            '**Champs requis** :\n'
            '- `dossier` : ID du dossier\n'
            '- `fichier` : fichier binaire\n'
            '- `type_fichier` : `PLAN`, `RAPPORT`, `SCAN`, `AUTRE`\n'
            '- `nom` : nom descriptif du fichier\n\n'
            'La taille est calculée automatiquement côté serveur.'
        ),
        request={'multipart/form-data': FichierDossierSerializer},
    ),
    update=extend_schema(
        tags=['Fichiers'],
        summary='Modifier les métadonnées d\'un fichier',
    ),
    partial_update=extend_schema(
        tags=['Fichiers'],
        summary='Modifier partiellement un fichier',
        description='Met à jour le nom ou le type d\'un fichier sans changer le fichier binaire.',
    ),
    destroy=extend_schema(
        tags=['Fichiers'],
        summary='Supprimer un fichier',
        description='Supprime le fichier et son enregistrement en base. Irréversible.',
    ),
)
class FichierViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = FichierDossierSerializer

    def get_queryset(self):
        qs      = FichierDossier.objects.select_related('dossier', 'televerse_par').order_by('-televerse_le')
        dossier = self.request.query_params.get('dossier')
        if dossier: qs = qs.filter(dossier__id=dossier)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        fichier = self.request.FILES.get('fichier')
        taille  = fichier.size if fichier else None
        serializer.save(televerse_par=self.request.user, taille=taille)
