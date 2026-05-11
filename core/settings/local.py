"""
Local development settings.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Database - PostgreSQL for local development
from decouple import config
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='mydatabase'),
        'USER': config('POSTGRES_USER', default='myuser'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='mypassword'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5433'),
    }
}

# Use console backend for local development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable security features for local development
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
