from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MeView, UtilisateurViewSet

router = DefaultRouter()
router.register('users', UtilisateurViewSet, basename='user')

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
] + router.urls
