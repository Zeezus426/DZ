"""Production settings for the OTEC project."""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Hosts are stripped and empties dropped: the value is hand-edited in the
# CapRover dashboard, where "a.com, b.com" is the natural way to type a list.
# Django compares Host against these verbatim, so a stray space would reject
# the domain with a 400 that looks identical to the host being absent.
ALLOWED_HOSTS = [
    host.strip()
    for host in config(
        'ALLOWED_HOSTS',
        default='otec.ltd,www.otec.ltd,otec-au.com,www.otec-au.com',
    ).split(',')
    if host.strip()
]

# CSRF trusted origins are derived from ALLOWED_HOSTS — Django requires the
# scheme here, so bare hostnames are promoted to https:// and duplicates
# (a host listed both bare and with a scheme) collapse to one entry.
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    host if host.startswith('http') else f'https://{host}'
    for host in ALLOWED_HOSTS
    if host not in ('localhost', '127.0.0.1', '*')
))

# ---------------------------------------------------------------------------
# Canonical host redirect (SEO)
# otec.ltd, www.otec.ltd, otec-au.com and www.otec-au.com all currently
# serve byte-identical content — this collapses them onto https://otec.ltd
# with a 301. Only enabled/added here, never in base.py/local.py, so a
# developer on http://localhost:8000/ is never bounced to the live domain.
# ---------------------------------------------------------------------------
CANONICAL_HOST_REDIRECT_ENABLED = True

MIDDLEWARE = list(MIDDLEWARE)
# Inserted first (index 0), ahead of SecurityMiddleware, so a host/scheme
# combination that needs both an SSL redirect *and* a host redirect
# (e.g. http://www.otec.ltd/x) resolves in one 301 straight to
# https://otec.ltd/x instead of two chained redirects. See the docstring on
# CanonicalHostRedirectMiddleware in core/middleware.py for the full
# reasoning, including why PREPEND_WWW is not a substitute for this.
MIDDLEWARE.insert(0, 'core.middleware.CanonicalHostRedirectMiddleware')

# ---------------------------------------------------------------------------
# Static files (WhiteNoise)
# Local dev serves static directly via runserver (base.py intentionally omits
# WhiteNoise so source edits in static/ appear on refresh without collectstatic).
# In production we serve the collected files through WhiteNoise, with gzip/brotli
# compression and hashed, cache-busted filenames.
# ---------------------------------------------------------------------------
# Index 2: after CanonicalHostRedirectMiddleware (0) and SecurityMiddleware
# (now pushed to 1), same relative position ("immediately after
# SecurityMiddleware") as before that middleware existed.
MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')

# ---------------------------------------------------------------------------
# GZip compression for rendered HTML (SEO/perf audit finding: HTML was being
# served uncompressed — identical content-length with and without
# Accept-Encoding: gzip).
#
# Positioned *after* WhiteNoiseMiddleware (index 3), not before it: WhiteNoise
# short-circuits the middleware chain for static-file requests it recognizes
# (it returns the response itself without calling further down the chain), so
# with GZip listed after it, GZip's request-phase code never even runs for
# those requests — WhiteNoise's own CompressedManifestStaticFilesStorage
# already pre-compresses collected static assets, so there is nothing for
# GZipMiddleware to usefully do there. This leaves GZip to do the one thing
# it's actually here for: compressing Django's dynamically rendered
# responses (the HTML pages, robots.txt, sitemap.xml) that WhiteNoise never
# touches. (It's also a no-op safety net either way: GZipMiddleware skips
# any response that already has a Content-Encoding header, so even a static
# file that reached it would not be double-compressed.)
#
# BREACH consideration (Django's own docs warn about compressing responses
# containing secrets): Django has masked the CSRF token per-response since
# masking was introduced (a fresh random mask XORed with the secret each
# render), so the token literal is not stable across responses — that
# defeats the repeated-fixed-secret oracle BREACH depends on. None of these
# pages reflect attacker-controlled input back into the HTML body on GET
# (the contact form posts to a separate JSON endpoint, not back into a
# rendered page), so there's no attacker-chosen plaintext sitting alongside
# a secret in the same compressed response either. Given both mitigations
# hold, compressing globally here is judged safe; if a page is ever added
# that reflects raw query-string/user input into rendered HTML, revisit this
# for that view specifically (e.g. exclude it, or move compression to the
# proxy where it can be controlled per-path).
MIDDLEWARE.insert(3, 'django.middleware.gzip.GZipMiddleware')

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
