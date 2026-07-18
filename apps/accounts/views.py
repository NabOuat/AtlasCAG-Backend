from rest_framework.views import APIView
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Utilisateur
from .serializers import (
    UtilisateurMeSerializer,
    UtilisateurListSerializer,
    UtilisateurCreateSerializer,
    UtilisateurUpdateSerializer,
)


@extend_schema(
    tags=['Comptes'],
    summary='Profil de l\'utilisateur connecté',
    description=(
        'Retourne les informations du compte actuellement authentifié : '
        'nom, prénom, email, profil (rôle), zone assignée, statut actif.'
    ),
    responses={200: UtilisateurMeSerializer},
)
class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UtilisateurMeSerializer(request.user).data)


@extend_schema_view(
    list=extend_schema(
        tags=['Comptes'],
        summary='Liste des utilisateurs',
        description='Retourne tous les comptes utilisateurs. Filtrable par profil, recherche et statut actif.',
        parameters=[
            OpenApiParameter('profil',  description='Filtrer par rôle : ADMIN, CONTROLEUR, ASF, SUPERVISEUR', required=False),
            OpenApiParameter('search',  description='Recherche sur le nom ou le username', required=False),
            OpenApiParameter('actif',   description='`1` = actifs uniquement, `0` = inactifs uniquement', required=False),
        ],
    ),
    retrieve=extend_schema(
        tags=['Comptes'],
        summary='Détail d\'un utilisateur',
        description='Retourne toutes les informations d\'un compte utilisateur identifié par son `id`.',
    ),
    create=extend_schema(
        tags=['Comptes'],
        summary='Créer un utilisateur',
        description='Crée un nouveau compte. Le mot de passe est haché automatiquement.',
        request=UtilisateurCreateSerializer,
    ),
    update=extend_schema(
        tags=['Comptes'],
        summary='Modifier un utilisateur (remplacement complet)',
        request=UtilisateurUpdateSerializer,
    ),
    partial_update=extend_schema(
        tags=['Comptes'],
        summary='Modifier un utilisateur (partiel)',
        description='Met à jour un ou plusieurs champs d\'un compte sans toucher aux autres.',
        request=UtilisateurUpdateSerializer,
    ),
    destroy=extend_schema(
        tags=['Comptes'],
        summary='Supprimer un utilisateur',
    ),
)
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
