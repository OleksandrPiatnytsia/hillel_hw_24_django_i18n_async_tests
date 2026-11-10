"""Settings for the tests (pytest.ini: DJANGO_SETTINGS_MODULE = config.settings_test).

Everything from config/settings.py, plus a few changes that make the tests
fast, repeatable and independent of the local .env:

- a fast password hasher: the default one (PBKDF2, ~1 million rounds) makes
  every create_user() / login take ~0.3 s;
- the cache in memory (LocMemCache) instead of Redis: tests don't touch
  the cache and sessions of the running site, and conftest.py clears it
  before every test;
- fixed fake Stripe keys: the Stripe client is replaced by a fake in tests
  (tests/fakes.py), the webhook secret signs the test webhook requests;
- no log file: test runs don't write to logs/app.log;
- no STATIC_ROOT: collectstatic is not needed for the tests.

The database stays PostgreSQL from .env (the Docker db container on
localhost:5432): pytest-django creates a separate database "test_<name>"
next to the real one, the real data is never touched.
Emails: pytest-django replaces every mailer with the locmem backend
(mail.outbox, the `mailoutbox` fixture), nothing is sent.
"""

from .settings import *  # noqa: F403 (all settings, then the changes below)
from .settings import LOGGING

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# No collected static files in tests: without this WhiteNoise warns
# "No directory at: .../staticfiles/" on every request. {% static %} in the
# templates still builds the URLs (it doesn't read the files).
STATIC_ROOT = None

STRIPE_SECRET_KEY = "sk_test_fake"
STRIPE_WEBHOOK_SECRET = "whsec_test_fake"

# Links in emails; "testserver" is the host of Django's test client
SITE_URL = "http://testserver"
DEFAULT_FROM_EMAIL = "Bookstore <noreply@localhost>"

# Remove the "file" handler: dictConfig opens the file of every handler in
# the list, even an unused one. Records still go to the console handler,
# pytest captures them and shows them only for a failed test.
LOGGING["handlers"].pop("file")
for logger_config in LOGGING["loggers"].values():
    logger_config["handlers"] = [
        handler for handler in logger_config["handlers"] if handler != "file"
    ]
