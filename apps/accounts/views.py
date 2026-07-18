from rest_framework.views import APIView
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from .models import Utilisateur
from .serializers import (
    UtilisateurMeSerializer,
    UtilisateurListSerializer,
    UtilisateurCreateSerializer,
    UtilisateurUpdateSerializer,
)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UtilisateurMeSerializer(request.user).data)


class UtilisateurViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Utilisateur.objects.all().order_by('last_name', 'first_name')

    def get_serializer_class(self):
        if self.action == 'create':
            return UtilisateurCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UtilisateurUpdateSerializer
        return UtilisateurListSerializer

    def get_queryset(self):
        qs     = super().get_queryset()
        profil = self.request.query_params.get('profil')
        search = self.request.query_params.get('search')
        actif  = self.request.query_params.get('actif')
        if profil:        qs = qs.filter(profil=profil)
        if search:        qs = qs.filter(username__icontains=search) | qs.filter(last_name__icontains=search)
        if actif == '1':  qs = qs.filter(is_active=True)
        if actif == '0':  qs = qs.filter(is_active=False)
        return qs
