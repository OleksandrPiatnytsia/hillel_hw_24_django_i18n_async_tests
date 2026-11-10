from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CartConfig(AppConfig):
    name = "cart"
    # Section title in the admin
    verbose_name = _("Cart")
