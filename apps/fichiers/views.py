from rest_framework import viewsets, permissions
from .models import FichierDossier
from .serializers import FichierDossierSerializer


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
