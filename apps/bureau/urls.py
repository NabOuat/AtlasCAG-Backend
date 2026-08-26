from rest_framework.routers import DefaultRouter
from .views import RapportBureauViewSet

router = DefaultRouter()
router.register('rapports', RapportBureauViewSet, basename='rapport-bureau')

urlpatterns = router.urls
