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

import re

from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.static import serve as serve_static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.utils import extend_schema

# Annotations JWT — SimpleJWT n'a pas de tags par défaut
TokenObtainPairView  = extend_schema(
    tags=['Authentification'],
    summary='Connexion — obtenir les tokens JWT',
    description=(
        'Authentifie un utilisateur et retourne un **access token** (8h) et un **refresh token** (30j).\n\n'
        '**Corps** : `{ "username": "...", "password": "..." }`\n\n'
        '**Réponse** : `{ "access": "eyJ...", "refresh": "eyJ..." }`\n\n'
        'Utiliser le `access` token dans le header de toutes les requêtes suivantes :\n'
        '`Authorization: Bearer <access_token>`'
    ),
)(TokenObtainPairView)

TokenRefreshView = extend_schema(
    tags=['Authentification'],
    summary='Rafraîchir le token d\'accès',
    description=(
        'Renouvelle le token d\'accès à partir d\'un refresh token valide.\n\n'
        '**Corps** : `{ "refresh": "eyJ..." }`\n\n'
        '**Réponse** : `{ "access": "eyJ...", "refresh": "eyJ..." }` '
        '(le refresh token est roté automatiquement — l\'ancien est blacklisté).'
    ),
)(TokenRefreshView)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Documentation OpenAPI ────────────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(),                              name='schema'),
    path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'),         name='swagger-ui'),
    path('api/redoc/',  SpectacularRedocView.as_view(url_name='schema'),           name='redoc'),

    # ── Auth JWT ─────────────────────────────────────────────────────────────
    path('api/token/',         TokenObtainPairView.as_view(),  name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(),     name='token_refresh'),

    # ── Apps ─────────────────────────────────────────────────────────────────
    path('api/accounts/',    include('apps.accounts.urls')),
    path('api/referentiel/', include('apps.referentiel.urls')),
    path('api/dossiers/',    include('apps.dossiers.urls')),
    path('api/controle/',    include('apps.controle.urls')),
    path('api/fichiers/',    include('apps.fichiers.urls')),
    path('api/stats/',       include('apps.stats.urls')),
    path('api/rapports/',    include('apps.rapports.urls')),
    path('api/terrain/',     include('apps.terrain.urls')),
    path('api/planning-bureau/', include('apps.bureau.urls')),
    path('api/geo/',         include('apps.geo.urls')),
    path('api/publicite/',   include('apps.publicite.urls')),
]

# Fichiers media (plans PDF, etc.) — servis uniquement en DEBUG, comme le fait le helper
# `django.conf.urls.static.static` habituel. Exemptés de X-Frame-Options (par défaut 'DENY'
# depuis Django 6, appliqué globalement par XFrameOptionsMiddleware à toute réponse, y compris
# les fichiers statiques) : ces PDF doivent pouvoir s'afficher dans un <iframe> intégré
# (module Contrôle Qualité), ce que 'DENY' bloque inconditionnellement même en same-origin.
# Le reste de l'application (API JSON, admin) garde le comportement strict par défaut.
if settings.DEBUG:
    urlpatterns += [
        re_path(
            r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')),
            xframe_options_exempt(serve_static),
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]
