from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# ── GDAL non installé sur Windows dev ────────────────────────────────────────
# GeoDjango (django.contrib.gis) nécessite GDAL.
# En dev Windows, on remplace par le backend PostgreSQL standard.
# En production (Linux VPS), GDAL + PostGIS sont installés normalement.
#
# Pour activer GeoDjango en dev Windows :
#   1. Télécharger OSGeo4W : https://trac.osgeo.org/osgeo4w/
#   2. Installer GDAL via l'installateur OSGeo4W
#   3. Supprimer les 4 lignes ci-dessous
# ─────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != 'django.contrib.gis']
DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Affiche les requêtes SQL en console en dev
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'ERROR',
        },
    },
}
