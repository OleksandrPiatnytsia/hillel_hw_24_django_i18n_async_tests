"""Project middleware. Both classes work in both modes:

- WSGI (runserver, tests with Client): get_response is a normal function,
  __call__ runs the sync code;
- ASGI (gunicorn + uvicorn in Docker, AsyncClient): get_response is a
  coroutine function, __call__ returns the coroutine of __acall__.

Why both: Django builds the chain once at start and checks every middleware.
A sync-only middleware under ASGI makes Django run it (and everything below
it, the views too) in a worker thread for EVERY request: the async views
would lose their point. sync_capable / async_capable + markcoroutinefunction
tell Django "I can work in the mode of my neighbours, no adapter needed".
https://docs.djangoproject.com/en/6.1/topics/http/middleware/#asynchronous-support
"""

import logging
import time

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.conf import settings
from whitenoise.middleware import WhiteNoiseMiddleware

logger = logging.getLogger(__name__)  # "config.middleware"


class RequestTimingMiddleware:
    """Measures how long each request takes, logs it and returns it in headers.

    Log line:  GET /authors/?page=2 200 12.3ms user=ann
    Headers:   X-Request-Duration: 12.3ms
               Server-Timing: app;dur=12.3   (shown in DevTools -> Network -> Timing)

    Placed FIRST in MIDDLEWARE, so the measured time includes all other
    middleware (sessions, auth, CSRF, ...) plus the view and the template.
    It can still log the user: AuthenticationMiddleware, further down the
    chain, sets request.user on the same request object, so it is there by
    the time get_response() returns.
    """

    sync_capable = True
    async_capable = True

    # Requests that are not worth a log line (the header is still added):
    # the toolbar's own AJAX calls, book covers (up to 10 per catalog page)
    # and /health/ (Docker calls it every few seconds; a failed check is
    # logged by the health view itself, with the reason)
    SKIP_LOG_PREFIXES = (
        "/__debug__/",
        "/" + settings.MEDIA_URL.lstrip("/"),
        "/health/",
    )

    def __init__(self, get_response):
        # Called ONCE, when the server starts. get_response is the next
        # middleware in the chain (or the view itself for the last one).
        self.get_response = get_response
        # Slower requests are logged as WARNING instead of INFO
        self.slow_ms = getattr(settings, "REQUEST_SLOW_MS", 500)
        # The next one is async (ASGI) -> this object behaves as an async
        # function too: Django awaits what __call__ returns
        self.is_async = iscoroutinefunction(get_response)
        if self.is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        # Called for EVERY request.
        if self.is_async:
            return self.__acall__(request)
        # perf_counter(): a monotonic high-resolution clock for measuring
        # intervals (time.time() can jump when the system clock is adjusted)
        start = time.perf_counter()

        # ---- everything before this line runs on the way IN ----
        response = self.get_response(request)
        # ---- everything after it runs on the way OUT ----

        self._finish(request, response, start, self.get_username(request))
        return response

    async def __acall__(self, request):
        start = time.perf_counter()
        response = await self.get_response(request)
        self._finish(request, response, start, await self.aget_username(request))
        return response

    def _finish(self, request, response, start, username):
        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration"] = f"{duration_ms:.1f}ms"
        response["Server-Timing"] = f"app;dur={duration_ms:.1f}"

        if not request.path.startswith(self.SKIP_LOG_PREFIXES):
            level = logging.WARNING if duration_ms >= self.slow_ms else logging.INFO
            logger.log(
                level,
                "%s %s %s %.1fms user=%s",
                request.method,
                request.get_full_path(),  # path + query string (?page=2)
                response.status_code,
                duration_ms,
                username,
            )

    @staticmethod
    def get_username(request):
        # request.user may be missing if a middleware above AuthenticationMiddleware
        # returned a response early (e.g. SecurityMiddleware's HTTPS redirect)
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return "anonymous"
        return user.username

    @staticmethod
    async def aget_username(request):
        # In async code request.user can't be used: it loads the user with a
        # sync database query (SynchronousOnlyOperation). request.auser()
        # (AuthenticationMiddleware) is its async version.
        auser = getattr(request, "auser", None)
        if auser is None:
            return "anonymous"
        user = await auser()
        return user.username if user.is_authenticated else "anonymous"


class AsyncWhiteNoiseMiddleware(WhiteNoiseMiddleware):
    """WhiteNoise (static files without nginx) that also works under ASGI.

    WhiteNoise 6.12 is sync only (see the module docstring for the cost).
    This subclass keeps WhiteNoise's own logic and adds the async path:
    - a static URL -> WhiteNoise's response, its file is read in a worker
      thread chunk by chunk (no blocking of the event loop);
    - anything else -> straight to the next middleware, awaited.
    In settings.MIDDLEWARE instead of "whitenoise.middleware.WhiteNoiseMiddleware".
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response=None, settings=settings):
        super().__init__(get_response, settings)
        self.is_async = iscoroutinefunction(get_response)
        if self.is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.is_async:
            return self.__acall__(request)
        return super().__call__(request)

    async def __acall__(self, request):
        # The same lookup as WhiteNoiseMiddleware.__call__. find_file() reads
        # the disk (only with autorefresh = DEBUG): in a thread.
        if self.autorefresh:
            static_file = await sync_to_async(self.find_file)(request.path_info)
        else:
            static_file = self.files.get(request.path_info)  # a dict, in memory
        if static_file is None:
            return await self.get_response(request)

        response = await sync_to_async(self.serve)(static_file, request)
        if response.streaming:
            # A FileResponse iterates over an open file (sync). Django's ASGI
            # handler would read it whole into memory with a warning
            # ("StreamingHttpResponse must consume synchronous iterators");
            # an async iterator reads it in chunks in a thread instead.
            response.streaming_content = _read_in_thread(iter(response.streaming_content))
        return response


async def _read_in_thread(chunks):
    """Async iterator over a sync one: every next() runs in a worker thread."""
    end = object()
    while (chunk := await sync_to_async(next, thread_sensitive=False)(chunks, end)) is not end:
        yield chunk
