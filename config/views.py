"""Project-level views that don't belong to the books or users apps."""

import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.views.i18n import set_language as django_set_language

from .i18n import is_supported_language

logger = logging.getLogger(__name__)  # "config.views"


def check_database():
    """Run the simplest possible query: proves PostgreSQL accepts queries."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def check_cache():
    """Write a value to the cache (Redis) and read it back.

    A random value, so an old value left by another request (another
    gunicorn worker) can't make a broken cache look working.
    """
    value = uuid.uuid4().hex
    cache.set("health_check", value, timeout=10)
    if cache.get("health_check") != value:
        raise RuntimeError("the value read back differs from the value written")


CHECKS = {
    "database": check_database,
    "cache": check_cache,
}


@never_cache  # Cache-Control: no-cache..., so no proxy or browser keeps an old answer
@require_GET  # other methods -> 405
def health(request):
    """GET /health/ - is the app able to work right now?

    Used by the healthcheck of the web service in docker-compose.yml (and
    could be used by a load balancer or monitoring). Checks the services
    the app can't work without: PostgreSQL and Redis.

    200 {"status": "ok", "database": "ok", "cache": "ok"}
    503 {"status": "error", "database": "ok", "cache": "error"}

    503 Service Unavailable, not 500: the app itself works, a service it
    depends on doesn't. No login needed, so no session is read: the check
    works even when the session storage (Redis) is down.
    The error details go only to the log, not to the response: the URL is
    public, and an error message may reveal host names or settings.
    """
    results = {}
    for name, check in CHECKS.items():
        try:
            check()
        except Exception:
            # Any error counts: connection refused, timeout, wrong password...
            # logger.exception = ERROR level + the traceback
            logger.exception("Health check failed: %s", name)
            results[name] = "error"
        else:
            results[name] = "ok"

    healthy = all(result == "ok" for result in results.values())
    return JsonResponse(
        {"status": "ok" if healthy else "error", **results},
        status=200 if healthy else 503,
    )


@require_POST
def set_language(request):
    """The language switcher in the navbar: POST language=uk|en, next=<page>.

    Django's own set_language view does the main work: checks the language,
    sets the "django_language" cookie and redirects back to `next` (only to
    an address of this site). On top of it the choice of a logged-in user
    is saved in the profile (User.language): the emails come in this
    language, and the login sets it on another device.
    """
    language = request.POST.get("language", "")
    if not is_supported_language(language):
        # Django's view checks only that Django itself has translations for
        # the code (it has "de", "fr", ... for the admin), not
        # settings.LANGUAGES, and would put "de" into the cookie. Without
        # "language" in POST it sets no cookie and only redirects back.
        request.POST = request.POST.copy()  # request.POST itself is read-only
        request.POST.pop("language", None)
    response = django_set_language(request)
    user = request.user
    if user.is_authenticated and is_supported_language(language) and user.language != language:
        user.language = language
        user.save(update_fields=["language"])
    return response
