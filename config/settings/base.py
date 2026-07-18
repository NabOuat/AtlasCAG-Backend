from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')

INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    # Apps métier
    'apps.accounts',
    'apps.referentiel',
    'apps.dossiers',
    'apps.controle',
    'apps.fichiers',
    'apps.stats',
    'apps.rapports',
    'apps.terrain',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME':     config('DB_NAME',     default='foncier'),
        'USER':     config('DB_USER',     default='postgres'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST',     default='127.0.0.1'),
        'PORT':     config('DB_PORT',     default='5432'),
    },
    # Bases spatiales OVH (données QGIS, lecture seule)
    'cavally_spatial': {
        'ENGINE':  'django.db.backends.postgresql',
        'NAME':    config('GEO_CAVALLY_DB',       default='cavally'),
        'USER':    config('GEO_CAVALLY_USER',     default='cavally'),
        'PASSWORD':config('GEO_CAVALLY_PASSWORD', default=''),
        'HOST':    config('GEO_HOST',  default='localhost'),
        'PORT':    config('GEO_PORT',  default='5432'),
        'OPTIONS': {'sslmode': 'prefer'},
        'TEST':    {'NAME': None},          # pas de DB de test sur ces connexions
    },
    'worodougou_spatial': {
        'ENGINE':  'django.db.backends.postgresql',
        'NAME':    config('GEO_WORODOUGOU_DB',       default='worodougou'),
        'USER':    config('GEO_WORODOUGOU_USER',     default='worodougou'),
        'PASSWORD':config('GEO_WORODOUGOU_PASSWORD', default=''),
        'HOST':    config('GEO_HOST',  default='localhost'),
        'PORT':    config('GEO_PORT',  default='5432'),
        'OPTIONS': {'sslmode': 'prefer'},
        'TEST':    {'NAME': None},
    },
}

AUTH_USER_MODEL = 'accounts.Utilisateur'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ──────────────────────────────────────────────
# Django REST Framework
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ──────────────────────────────────────────────
# drf-spectacular — Documentation OpenAPI/Swagger
# ──────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'AtlasCAG API',
    'DESCRIPTION': (
        '## API du système de gestion foncière AtlasCAG\n\n'
        '**Organisation** : AFOR — Agence Foncière Rurale, Côte d\'Ivoire\n\n'
        '### Authentification\n'
        'Tous les endpoints (sauf `/api/token/`) nécessitent un **Bearer token JWT**.\n\n'
        '1. `POST /api/token/` -> obtenir `access` + `refresh`\n'
        '2. `POST /api/token/refresh/` -> renouveler le token\n'
        '3. Envoyer le token dans le header : `Authorization: Bearer <access_token>`\n\n'
        '### Zones géographiques\n'
        'La plateforme couvre deux zones : **cavally** et **worodougou**.\n'
        'Les endpoints géospatiaux prennent `{zone}` en paramètre de chemin.\n\n'
        '### Pagination\n'
        'Les listes paginées retournent : `{ count, next, previous, results }`\n'
        'Paramètre : `?page=<n>` (25 items par page par défaut)\n'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'name': 'AFOR', 'email': 'contact@afor.ci'},
    'SCHEMA_PATH_PREFIX': '/api',
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'ENUM_NAME_OVERRIDES': {
        'StatutDossierEnum':   'apps.dossiers.models.Dossier.STATUT_CHOICES',
        'StatutControleEnum':  'apps.controle.models.ControleQualite.STATUT_CHOICES',
        'StatutEnvoiEnum':     'apps.controle.models.EnvoiEntreprise.STATUT_CHOICES',
        'StatutRapportEnum':   'apps.rapports.models.RapportPeriodique.STATUT_CHOICES',
    },
    'TAGS': [
        {
            'name': 'Authentification',
            'description': 'Obtention et renouvellement des tokens JWT. Aucune authentification requise.',
        },
        {
            'name': 'Comptes',
            'description': 'Gestion des comptes utilisateurs AtlasCAG (CRUD + profil connecté).',
        },
        {
            'name': 'Référentiel',
            'description': 'Données de référence géographique : zones, régions, villages. Lecture seule.',
        },
        {
            'name': 'Dossiers',
            'description': 'Dossiers CF (Certificats Fonciers) et DTV (Délimitations Territoriales Villageoises).',
        },
        {
            'name': 'Fichiers',
            'description': 'Upload et gestion des fichiers attachés aux dossiers (PDFs, plans, scans).',
        },
        {
            'name': 'Contrôle Qualité',
            'description': (
                'Workflow de contrôle qualité : sélection des villages -> fichiers PLAN -> '
                'contrôle DIGIFOR vs Shapefile. Inclut les anomalies et les envois entreprises.'
            ),
        },
        {
            'name': 'Géoportail',
            'description': (
                'Accès aux données spatiales PostGIS (lecture seule, bases OVH). '
                'Retourne des GeoJSON ou des données tabulaires pour les couches CF, DTV, sous-préfectures.'
            ),
        },
        {
            'name': 'Statistiques',
            'description': 'Dashboard KPIs globaux et faits agrégés par période.',
        },
        {
            'name': 'Terrain',
            'description': 'Planning journalier des missions ASF et identification des layons.',
        },
        {
            'name': 'Rapports',
            'description': 'Rapports périodiques (hebdomadaire, mensuel, trimestriel) par zone.',
        },
    ],
}

# ──────────────────────────────────────────────
# JWT — tokens
# ──────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
