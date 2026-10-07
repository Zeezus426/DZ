"""Custom middleware for the OTEC project.

Two independent, path/host-keyed concerns live here — both are simple
stateless response/request policies with no shared logic, so splitting them
into separate files would be pure ceremony:

* ``CanonicalHostRedirectMiddleware`` — collapses every domain alias onto
  the canonical apex host.
* ``NoIndexHeaderMiddleware`` — stamps ``X-Robots-Tag`` on the internal
  portal/admin so it never gets indexed.
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """
    301-redirect any request whose Host is not ``settings.CANONICAL_HOST``
    to the same path (and query string) on ``https://{CANONICAL_HOST}``.

    Why this exists instead of a Django setting
    --------------------------------------------
    Django ships ``PREPEND_WWW``, which does the opposite of what we need
    (it *adds* a ``www.`` prefix to bare-domain requests). There is no
    built-in Django setting that *strips* a ``www.``/alternate-domain
    prefix down to one canonical host — that's the gap this middleware
    fills. Do not replace this with ``PREPEND_WWW`` later; that setting
    solves the reverse problem and would actively break this site's
    canonicalization (it would start adding www. instead of removing it).

    Ordering
    --------
    Inserted at index 0 of MIDDLEWARE (in ``core/settings/prod.py``,
    i.e. before ``SecurityMiddleware``). ``SecurityMiddleware``'s
    ``SECURE_SSL_REDIRECT`` already 301s ``http://`` -> ``https://`` on the
    *same* host. If this middleware ran after ``SecurityMiddleware``, a
    request for ``http://www.otec.ltd/x`` would take two redirect hops:
    http[www] -> https[www] -> https[apex]. Running first lets us jump
    straight from any incoming scheme/host combination to the final
    ``https://otec.ltd/x`` in a single 301 — one hop, not two, which
    matters for both crawl efficiency and real-user latency.

    Local development
    ------------------
    No-op unless ``settings.CANONICAL_HOST_REDIRECT_ENABLED`` is True.
    That flag defaults to False in ``core/settings/base.py`` and is only
    flipped on in ``core/settings/prod.py`` — and on top of that, this
    middleware class is only added to ``MIDDLEWARE`` at all in
    ``prod.py`` (see the splice there), so local ``runserver`` traffic
    against ``localhost``/``127.0.0.1`` never even passes through this
    code, let alone gets redirected to the live domain.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'CANONICAL_HOST_REDIRECT_ENABLED', False):
            canonical_host = getattr(settings, 'CANONICAL_HOST', None)
            if canonical_host:
                # get_host() strips a standard port and validates against
                # ALLOWED_HOSTS (raising DisallowedHost -> Django's normal
                # 400 response for anything not already allow-listed), so
                # by the time we compare, request_host is one of the
                # known ALLOWED_HOSTS entries.
                request_host = request.get_host().split(':')[0].lower()
                if request_host != canonical_host.lower():
                    redirect_url = f'https://{canonical_host}{request.get_full_path()}'
                    return HttpResponsePermanentRedirect(redirect_url)
        return self.get_response(request)


#: Path prefixes that must never be indexed: the internal order-fulfilment
#: portal, the login/logout/password-reset flow, and Django admin. Kept as
#: a tuple (not a setting) for the same reason PORTAL_PREFIX lives in
#: orders/middleware.py rather than settings — it has to stay in step with
#: core/urls.py, not deployment.
NOINDEX_PATH_PREFIXES = ('/portal/', '/accounts/', '/admin/')


class NoIndexHeaderMiddleware:
    """
    Add ``X-Robots-Tag: noindex, nofollow`` to every response under
    ``/portal/``, ``/accounts/`` or ``/admin/``.

    These paths are already login-gated (``PortalLoginRequiredMiddleware``,
    Django's own auth views, admin's own auth check) — this isn't an access
    control. It exists because a *login page* is still a perfectly normal,
    indexable 200 response in Google's eyes, and admin/portal URLs are pure
    crawl-budget waste for a public marketing site whose commercial value
    is entirely in the three public pages.

    A response header (rather than a ``<meta name="robots">`` tag in a
    template) because: (1) it needs no template changes — templates under
    ``home/`` and ``orders/`` are owned by other work in this repo right
    now; (2) it covers every response under the prefix uniformly, including
    redirects and any future non-HTML responses a ``<meta>`` tag can't
    reach.

    ``templates/robots.txt`` disallows these same prefixes for well-behaved
    crawlers; this header is the backstop for a crawler that fetches a
    login-walled URL anyway (e.g. reached via an external link) before, or
    without ever, consulting robots.txt.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(NOINDEX_PATH_PREFIXES):
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
