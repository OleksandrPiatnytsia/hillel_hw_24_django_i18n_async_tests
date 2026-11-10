from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "users"
    # Section title in the admin
    verbose_name = _("Users")

    def ready(self):
        # Importing the module runs the @receiver decorators, which connect
        # the signal handlers. ready() runs once, after all apps are loaded.
        from . import signals  # noqa: F401
