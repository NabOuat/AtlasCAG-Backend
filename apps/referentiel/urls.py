from rest_framework.routers import DefaultRouter
from .views import ZoneViewSet, RegionViewSet, DepartementViewSet, SousPrefectureViewSet, VillageViewSet

router = DefaultRouter()
router.register('zones',            ZoneViewSet,            basename='zone')
router.register('regions',          RegionViewSet,          basename='region')
router.register('departements',     DepartementViewSet,     basename='departement')
router.register('sous-prefectures', SousPrefectureViewSet,  basename='sous-prefecture')
router.register('villages',         VillageViewSet,         basename='village')

urlpatterns = router.urls
