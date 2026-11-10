from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import health, set_language

urlpatterns = [
    path("admin/", admin.site.urls),
    # 200 / 503: are PostgreSQL and Redis reachable (docker-compose healthcheck)
    path("health/", health, name="health"),
    # The language switcher (navbar): POST -> cookie + User.language -> back.
    # The same name as Django's view: {% url 'set_language' %}
    path("i18n/setlang/", set_language, name="set_language"),
    # Login / logout / sign up: /accounts/login/, ... (namespace "users")
    path("accounts/", include("users.urls")),
    # Session cart: /cart/, /cart/add/<book_id>/, ... (namespace "cart")
    path("cart/", include("cart.urls")),
    # Checkout and the user's orders: /orders/checkout/, /orders/<pk>/, ...
    path("orders/", include("orders.urls")),
    # "Pay" button and Stripe's return pages: /payments/pay/<order_id>/, ...
    path("payments/", include("payments.urls")),
    # Bookstore catalog lives at the site root; namespace "books" comes
    # from app_name in books/urls.py
    path("", include("books.urls")),
]

if settings.DEBUG:
    # Uploaded files (covers) in development. runserver serves static files
    # by itself, but not media. In production nginx / storage does this.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.ENABLE_DEBUG_TOOLBAR:
    # Imported here: without requirements-dev.txt the package doesn't exist.
    # /__debug__/... — the toolbar loads its panels from these URLs.
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
