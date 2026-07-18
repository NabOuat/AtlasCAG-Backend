from rest_framework.routers import DefaultRouter
from .views import PlanningViewSet, LayonViewSet

router = DefaultRouter()
router.register('planning', PlanningViewSet, basename='planning')
router.register('layons',   LayonViewSet,    basename='layon')

urlpatterns = router.urls
