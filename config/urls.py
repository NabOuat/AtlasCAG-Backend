"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth JWT
    path('api/token/',         TokenObtainPairView.as_view(),  name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(),     name='token_refresh'),

    # Apps
    path('api/accounts/',    include('apps.accounts.urls')),
    path('api/referentiel/', include('apps.referentiel.urls')),
    path('api/dossiers/',    include('apps.dossiers.urls')),
    path('api/controle/',    include('apps.controle.urls')),
    path('api/fichiers/',    include('apps.fichiers.urls')),
    path('api/stats/',       include('apps.stats.urls')),
    path('api/rapports/',    include('apps.rapports.urls')),
    path('api/terrain/',     include('apps.terrain.urls')),
    path('api/geo/',         include('apps.geo.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
