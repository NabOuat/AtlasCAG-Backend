from rest_framework.routers import DefaultRouter
from .views import FichierViewSet, ExcelPubliciteViewSet

router = DefaultRouter()
router.register('', FichierViewSet, basename='fichier')
router.register('excel-publicite', ExcelPubliciteViewSet, basename='excel-publicite')

urlpatterns = router.urls
