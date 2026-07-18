from rest_framework.routers import DefaultRouter
from .views import FichierViewSet

router = DefaultRouter()
router.register('', FichierViewSet, basename='fichier')

urlpatterns = router.urls
