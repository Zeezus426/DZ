"""Base settings for the OTEC project."""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'anymail',
    'home',
    'orders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Backstop for the internal portal — must follow AuthenticationMiddleware
    # so request.user is populated.
    'orders.middleware.PortalLoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='dz'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Australia/Sydney'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise configuration (middleware/storage are wired up in prod.py only)
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = False  # Only reload in debug mode

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# EMAIL CONFIGURATION (Brevo via Anymail)
# ==========================================
# Anymail talks to Brevo's v3 HTTP API instead of SMTP, which is what gives us
# per-message tags, metadata and delivery/bounce webhooks — none of which
# survive a plain SMTP hand-off. The SMTP credentials below are kept as the
# fallback so a deployment without BREVO_API_KEY still sends mail rather than
# failing closed.

ANYMAIL = {
    'BREVO_API_KEY': config('BREVO_API_KEY', default=''),
    # Shared secret appended to the webhook URL as ?secret=... — set it before
    # wiring delivery/bounce webhooks up in the Brevo dashboard.
    'WEBHOOK_SECRET': config('ANYMAIL_WEBHOOK_SECRET', default=''),
}

EMAIL_BACKEND = (
    'anymail.backends.brevo.EmailBackend'
    if ANYMAIL['BREVO_API_KEY']
    else 'django.core.mail.backends.smtp.EmailBackend'
)

# --- SMTP fallback (used only when BREVO_API_KEY is unset) ------------------

# Map the deployment's environment variables to Django's SMTP settings
EMAIL_HOST = config('BREVO_SMTP', default='smtp-relay.brevo.com')
EMAIL_PORT = config('BREVO_PORT', default=587, cast=int)
# Derive the encryption mode from the port so the two can never mismatch
# (a mismatch raises "SSL: WRONG_VERSION_NUMBER"):
#   port 465      -> implicit SSL
#   port 587/2525 -> STARTTLS
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = not EMAIL_USE_SSL

EMAIL_HOST_USER = config('BREVO_LOGIN', default='')
EMAIL_HOST_PASSWORD = config('BREVO_PASSWORD', default='')

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='info@otec-au.com')
CONTACT_EMAIL = config('CONTACT_EMAIL', default='info@otec-au.com')
EMAIL_SUBJECT_PREFIX = '[OTEC] '
SERVER_EMAIL = config('SERVER_EMAIL', default='noreply@otec-au.com')

# Security Settings (Base)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Allowed hosts (overridden in environment-specific settings)
ALLOWED_HOSTS = []


# ==========================================
# AUTHENTICATION (internal order portal)
# ==========================================
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'orders:order_list'
LOGOUT_REDIRECT_URL = 'home'


# Rate limiting settings
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_USE_CACHE = 'default'
