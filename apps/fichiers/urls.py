from rest_framework.routers import DefaultRouter
from .views import FichierViewSet, ExcelPubliciteViewSet

router = DefaultRouter()
# 'excel-publicite' doit être enregistré AVANT '' : le préfixe vide de FichierViewSet génère une
# route de détail '^(?P<pk>[^/.]+)/$' qui, si elle est enregistrée en premier, capture
# 'excel-publicite/' comme pk='excel-publicite' avant que la route dédiée ne soit essayée
# (même piège que documenté dans apps/dossiers/urls.py pour 'suivi-cf').
router.register('excel-publicite', ExcelPubliciteViewSet, basename='excel-publicite')
router.register('', FichierViewSet, basename='fichier')

urlpatterns = router.urls
