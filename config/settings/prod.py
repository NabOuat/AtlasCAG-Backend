from .base import *
from decouple import config as env

DEBUG = False
ALLOWED_HOSTS = env('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

CORS_ALLOWED_ORIGINS = env(
    'CORS_ORIGINS',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
