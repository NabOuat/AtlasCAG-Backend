from rest_framework.routers import DefaultRouter
from .views import ZoneViewSet, RegionViewSet, VillageViewSet

router = DefaultRouter()
router.register('zones',    ZoneViewSet,    basename='zone')
router.register('regions',  RegionViewSet,  basename='region')
router.register('villages', VillageViewSet, basename='village')

urlpatterns = router.urls
