from rest_framework.routers import DefaultRouter
from .views import RapportViewSet

router = DefaultRouter()
router.register('', RapportViewSet, basename='rapport')

urlpatterns = router.urls
