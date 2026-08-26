from rest_framework.permissions import SAFE_METHODS, BasePermission

# Profils autorisés à déposer un rapport Planning Bureau — mêmes profils que
# PROFILS_AUTORISES côté frontend (src/pages/planning/PlanningBureau.jsx).
ROLES_SAISIE_BUREAU = {'SIFOR_JUNIOR', 'SIFOR_SENIOR', 'ADMIN', 'CHEF_PROJET'}


class PeutSaisirRapportBureau(BasePermission):
    """Lecture ouverte à tout utilisateur authentifié ; dépôt/modification/suppression réservés
    aux profils SIFOR (junior/senior) ou aux profils de gestion (Administrateur, Chef de Projet)."""

    message = "Seuls les profils SIFOR (junior/senior), Administrateur ou Chef de projet peuvent déposer un rapport."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.is_superuser or getattr(user, 'profil', None) in ROLES_SAISIE_BUREAU)
