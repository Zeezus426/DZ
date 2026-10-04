"""Blanket authentication guard for the internal portal."""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login

#: Everything under this prefix requires a session. Kept here rather than in
#: settings because it has to stay in step with core/urls.py, not deployment.
PORTAL_PREFIX = '/portal/'


class PortalLoginRequiredMiddleware:
    """
    Redirect anonymous requests for anything under ``/portal/`` to the login
    page, carrying the original path in ``?next=``.

    The views are individually decorated with ``@login_required`` already;
    this is the backstop, so a view added later without the decorator fails
    closed instead of quietly serving the register to the public. Must sit
    after ``AuthenticationMiddleware`` — ``request.user`` has to exist.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(PORTAL_PREFIX) and not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                settings.LOGIN_URL,
            )
        return self.get_response(request)
