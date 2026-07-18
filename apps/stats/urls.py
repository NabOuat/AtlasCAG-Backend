from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DashboardView, FaitAgregeViewSet

router = DefaultRouter()
router.register('faits', FaitAgregeViewSet, basename='fait-agrege')

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
] + router.urls
