from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaymentsConfig(AppConfig):
    name = "payments"
    # Section title in the admin
    verbose_name = _("Payments")
