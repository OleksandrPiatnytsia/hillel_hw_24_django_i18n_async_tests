from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """The built-in user admin, plus email on the "Add user" page.

    BaseUserAdmin already shows email on the edit page ("Personal info").
    The add page only has username + passwords, but email is now required,
    so without it the form could not be saved.
    """

    # The edit page: the built-in sections + the delivery details
    fieldsets = (
        *BaseUserAdmin.fieldsets,
        (_("Delivery details"), {"fields": ("phone", "address")}),
        (_("Language"), {"fields": ("language",)}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
