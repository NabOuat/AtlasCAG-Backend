from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ControleViewSet, EnvoiViewSet, qc_villages, qc_dossiers

router = DefaultRouter()
router.register('controles', ControleViewSet, basename='controle')
router.register('envois',    EnvoiViewSet,    basename='envoi')

urlpatterns = router.urls + [
    path('qc/villages/', qc_villages, name='qc-villages'),
    path('qc/dossiers/', qc_dossiers, name='qc-dossiers'),
]
