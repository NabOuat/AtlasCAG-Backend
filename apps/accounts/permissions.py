from rest_framework.permissions import SAFE_METHODS, BasePermission

# Profils autorisés à créer/modifier/supprimer les données de référence sensibles
# (régions, départements, sous-préfectures, villages, comptes utilisateurs).
ROLES_GESTION_SENSIBLE = {'ADMIN', 'CHEF_PROJET'}


class IsAdminOuChefProjet(BasePermission):
    """Lecture ouverte à tout utilisateur authentifié ; écriture (création, modification,
    suppression) réservée aux profils Administrateur et Chef de Projet (ou superuser Django).

    Utilisée sur les endpoints exposant des données de référence sensibles (référentiel
    géographique, comptes utilisateurs) pour que n'importe quel agent authentifié puisse
    consulter, mais que seuls l'administrateur ou le chef de projet puissent créer/modifier."""

    message = "Seuls les profils Administrateur ou Chef de projet peuvent effectuer cette action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.is_superuser or getattr(user, 'profil', None) in ROLES_GESTION_SENSIBLE)
