from rest_framework.routers import DefaultRouter
from .views import FichierViewSet, ExcelPubliciteViewSet

router = DefaultRouter()
# Attention à l'ordre : 'excel-publicite' doit être enregistré AVANT le préfixe vide ''
# (FichierViewSet), sinon la route détail générée pour ce dernier (^(?P<pk>[^/.]+)/$)
# intercepterait /fichiers/excel-publicite/ en l'interprétant comme pk='excel-publicite'
# (même défaut déjà rencontré et corrigé sur apps/dossiers/urls.py).
router.register('excel-publicite', ExcelPubliciteViewSet, basename='excel-publicite')
router.register('',                FichierViewSet,        basename='fichier')

urlpatterns = router.urls
