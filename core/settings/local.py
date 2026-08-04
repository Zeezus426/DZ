"""Local development settings for the OTEC project."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'otec-django.caprover.iqed.com.au']

# Print emails to the console instead of sending them. Swap to the SMTP backend
# below when you need to test real Brevo delivery from your machine.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Security settings for development
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Debug toolbar for development (optional)
DEBUG_TOOLBAR_ENABLED = False
try:
    import debug_toolbar
    DEBUG_TOOLBAR_ENABLED = True
    INSTALLED_APPS += ['debug_toolbar',]
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
    INTERNAL_IPS = ['127.0.0.1', '::1']
except ImportError:
    pass

# Allow all hosts for development
CORS_ALLOW_ALL_ORIGINS = True

# Disable rate limiting in development (set to True if you want to test it)
RATELIMIT_ENABLE = False

print("WARNING: Running in DEBUG mode with development settings.")
