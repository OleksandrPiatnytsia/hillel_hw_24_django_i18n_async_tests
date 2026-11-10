from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BooksConfig(AppConfig):
    name = "books"
    # Section title in the admin
    verbose_name = _("Books")
