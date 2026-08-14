from rest_framework.routers import DefaultRouter
from .views import DossierViewSet, VagueEnvoiViewSet, SuiviCFViewSet

router = DefaultRouter()
# Attention à l'ordre : 'vagues' et 'suivi-cf' doivent être enregistrés AVANT le préfixe vide ''
# (DossierViewSet), sinon la route détail générée pour ce dernier (^(?P<pk>[^/.]+)/$) intercepterait
# /dossiers/suivi-cf/ en l'interprétant comme pk='suivi-cf'.
router.register('vagues',   VagueEnvoiViewSet, basename='vague-envoi')
router.register('suivi-cf', SuiviCFViewSet,    basename='suivi-cf')
router.register('',         DossierViewSet,    basename='dossier')

urlpatterns = router.urls
