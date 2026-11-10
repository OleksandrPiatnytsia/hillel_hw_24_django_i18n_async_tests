from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OrdersConfig(AppConfig):
    name = "orders"
    # Section title in the admin
    verbose_name = _("Orders")
