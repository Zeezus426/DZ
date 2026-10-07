"""Sitemap for OTEC's public marketing pages.

Deliberately NOT using django.contrib.sites
---------------------------------------------
django.contrib.sitemaps normally resolves the domain to put in each URL via
the Sites framework (a DB-backed Site row) or, failing that, via
``RequestSite(request)`` — which derives the domain from whatever Host
header the ``/sitemap.xml`` request itself arrived on.

Both are wrong for us, and neither is needed:

* Adding django.contrib.sites just to answer "what's my domain" would pull
  in a DB-backed model, a migration, and admin registration for a value
  that's already a plain setting on a single-domain site. That's a hard
  dependency for no real benefit here.
* The request-based fallback (``RequestSite``) is actively unsafe:
  ``https://www.otec.ltd/sitemap.xml`` and the other ALLOWED_HOSTS aliases
  all resolve to this same app, so a crawler hitting sitemap.xml on a
  non-canonical host (before it has followed the redirect, or from a stale
  DNS/crawl cache) would get back a sitemap full of ``www.`` URLs instead
  of the canonical apex ones — precisely the duplicate-content problem this
  whole change exists to fix.

``StaticPagesSitemap.get_domain()`` below sidesteps both by returning
``settings.CANONICAL_HOST`` unconditionally, so every URL in the sitemap is
always on the apex host regardless of how the request came in.
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticPagesSitemap(Sitemap):
    """The three public pages: home, about, certification."""

    # Also the class default (Sitemap.get_protocol() falls back to
    # 'https'), but set explicitly since correctness here matters and
    # shouldn't depend on a base-class default a future reader might not
    # know about.
    protocol = 'https'

    # No changefreq / priority: Google has stated for years it ignores
    # both for ranking/crawling purposes, so including them is dead weight
    # in the payload — omitted rather than set to a value nobody consumes.

    # No lastmod: there is no verifiable modification timestamp for these
    # pages anywhere in the app right now — no Last-Modified from the
    # view, no CMS revision field on a model. Emitting datetime.now() (or
    # any other guessed value) at generation time would be a fabricated
    # date, which search engines can and do penalize trust for once they
    # catch it. If a real timestamp becomes available later (e.g. an
    # `updated_at` field once these pages are backed by a model), add a
    # `lastmod(self, item)` method here that reads it — don't fake one in
    # the meantime.

    def items(self):
        return ['home', 'about', 'certification']

    def location(self, item):
        # Resolved via reverse() on the URL name, not a hardcoded path —
        # if home/urls.py ever changes these paths, the sitemap follows
        # automatically instead of silently going stale.
        return reverse(item)

    def get_domain(self, site=None):
        return settings.CANONICAL_HOST
