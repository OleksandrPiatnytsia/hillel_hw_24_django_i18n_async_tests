from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Site user.

    Inherits everything from the built-in user (username, password,
    first/last name, is_staff, groups, user_permissions, ...). Login stays
    by username; the only change is the email field.

    Even without extra fields a custom user model is worth having from the
    very first migration: switching AUTH_USER_MODEL later, when other tables
    already point to auth_user, is a painful manual migration.
    """

    # In AbstractUser email is optional (blank=True) and not unique.
    # Here it is required, unique and always stored in lowercase — so
    # "Ann@Mail.com" and "ann@mail.com" are the same email, and plain
    # unique=True is enough to allow only one account per email.
    email = models.EmailField(
        _("email address"),
        unique=True,
        error_messages={"unique": _("A user with this email already exists.")},
    )

    # Delivery details for the checkout form: filled in on the profile page
    # (or saved from the checkout), copied into every new order as its
    # prefilled values. Optional: a new user has none yet.
    # The name comes from first_name / last_name (AbstractUser).
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    address = models.TextField(_("delivery address"), blank=True)

    # The language the user chose with the switcher in the navbar (saved by
    # config.views.set_language). Used where there is no request to take
    # the language from: the emails (also those sent from the Stripe
    # webhook) and the language cookie that the login sets.
    language = models.CharField(
        _("language"),
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        help_text=_("Language of the site and of the emails."),
    )

    # Extra fields that `createsuperuser` asks for (besides USERNAME_FIELD
    # and password). AbstractUser already has ["email"]; kept explicit.
    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):
        # AbstractUser.Meta holds verbose_name "user"; inheriting it keeps
        # the admin labels the same as for the built-in model
        constraints = [
            # Database-level guarantee: even QuerySet.update() or raw SQL,
            # which skip save(), can't store an email with capital letters
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")),
                name="users_user_email_lowercase",
            ),
        ]

    def clean(self):
        # Called by full_clean() — in ModelForms (sign up, admin) it runs
        # BEFORE the unique / constraint checks, so they see the lowercase value.
        # super() trims the username and lowercases only the email domain.
        super().clean()
        self.email = self.email.lower()

    def save(self, *args, **kwargs):
        # save() is not preceded by clean() in every path:
        # createsuperuser, User.objects.create_user(), shell scripts
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)
