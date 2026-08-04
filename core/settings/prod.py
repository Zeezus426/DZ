"""Production settings for DZ Commodities project."""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='otec.ltd,www.otec.ltd,otec-au.com,www.otec-au.com',
).split(',')

# CSRF trusted origins are derived from ALLOWED_HOSTS — Django requires the
# scheme here, so bare hostnames are promoted to https:// and duplicates
# (a host listed both bare and with a scheme) collapse to one entry.
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    host if host.startswith('http') else f'https://{host}'
    for host in ALLOWED_HOSTS
    if host not in ('localhost', '127.0.0.1', '*')
))

# ---------------------------------------------------------------------------
# Static files (WhiteNoise)
# Local dev serves static directly via runserver (base.py intentionally omits
# WhiteNoise so source edits in static/ appear on refresh without collectstatic).
# In production we serve the collected files through WhiteNoise, with gzip/brotli
# compression and hashed, cache-busted filenames.
# ---------------------------------------------------------------------------
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # immediately after SecurityMiddleware

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookie security
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Content Security Policy (basic implementation)
# You may want to customize this based on your actual needs
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'",)
CSP_IMG_SRC = ("'self'", 'data:', 'https:')
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)

# Database - PostgreSQL configuration for production
# Configure these environment variables in CapRover:
# DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

# Connection pool settings for PostgreSQL
DATABASES['default'].update({
    'CONN_MAX_AGE': 600,  # 10 minutes connection pool
    'OPTIONS': {
        'connect_timeout': 10,
    },
})

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

print("Running in PRODUCTION mode with security settings enabled.")
