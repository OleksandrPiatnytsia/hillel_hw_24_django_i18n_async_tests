import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, resolve_url
from django.urls import reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView, UpdateView

from config.i18n import set_language_cookie

from .forms import LoginForm, ProfileForm, SignUpForm

logger = logging.getLogger(__name__)  # "users.views"

# Group every new user gets (created by the users.0003_create_groups migration)
DEFAULT_GROUP_NAME = "Customers"


class UserLoginView(SuccessMessageMixin, LoginView):
    """Login page.

    LoginView itself: validates the form, calls login() (creates the
    session) and redirects to ?next=... or to LOGIN_REDIRECT_URL.
    """

    template_name = "users/auth_form.html"
    form_class = LoginForm
    # A logged-in user who opens /accounts/login/ is sent away right away
    redirect_authenticated_user = True
    success_message = "Welcome back, %(username)s!"
    extra_context = {"title": "Log in", "submit_label": "Log in"}

    def form_valid(self, form):
        """Log in, then switch the site to the language saved in the profile.

        activate() first: the "Welcome back" message is made in this
        language. The cookie: the next requests come in it too (on a new
        device, or after somebody switched the language as a guest).
        """
        language = form.get_user().language
        translation.activate(language)
        response = super().form_valid(form)
        return set_language_cookie(response, language)


class UserLogoutView(LogoutView):
    """Logout: POST only (Django 5+), then redirect to LOGOUT_REDIRECT_URL."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Added after logout(): the session is already flushed, but the
        # message storage still works for this response
        messages.info(request, "You have been logged out.")
        return response


class SignUpView(SuccessMessageMixin, CreateView):
    """Registration + automatic login of the new user."""

    form_class = SignUpForm
    template_name = "users/auth_form.html"
    success_message = "Account created. Welcome, %(username)s!"
    extra_context = {"title": "Sign up", "submit_label": "Create account"}

    def dispatch(self, request, *args, **kwargs):
        # Same as redirect_authenticated_user in LoginView
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # The language the guest is using the site in right now (chosen by
        # LocaleMiddleware): emails to the new user come in it
        form.instance.language = translation.get_language()
        # super() saves the user (self.object) and returns the redirect
        response = super().form_valid(form)
        # filter().first() instead of get(): if the group is missing (e.g. it
        # was deleted in the admin), registration still works, just without it
        group = Group.objects.filter(name=DEFAULT_GROUP_NAME).first()
        if group:
            self.object.groups.add(group)
        else:
            logger.warning("Group %r not found, new user left without it", DEFAULT_GROUP_NAME)
        # Only username and id: email is personal data, logs are read by more
        # people (and kept longer) than the database
        logger.info("Sign up: user=%s id=%s", self.object.username, self.object.pk)
        # Log in right away, so the user doesn't type the password twice
        login(self.request, self.object)
        return response

    def get_success_url(self):
        # Like LoginView: go back to ?next=... if it points to our site.
        # The check protects from "open redirect" to another domain.
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # LoginView puts "next" into context itself; do the same here so
        # the shared template keeps it in a hidden field
        context["next"] = self.request.GET.get("next", "")
        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    """Current user's page: groups and effective permissions.

    LoginRequiredMixin: an anonymous user is redirected to LOGIN_URL
    (?next=/accounts/profile/). Unlike the book views, there is no specific
    permission to check here — any logged-in user may open their profile.
    """

    template_name = "users/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["groups"] = user.groups.order_by("name")
        # get_all_permissions(): own permissions + permissions of all groups,
        # as "app_label.codename" strings. A superuser gets every permission.
        context["permissions"] = sorted(user.get_all_permissions())
        return context


class ProfileEditView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Edit name, phone and delivery address (prefilled at checkout).

    get_object(): always the current user — there is no <pk> in the URL,
    so nobody can open someone else's profile by changing a number.
    """

    form_class = ProfileForm
    template_name = "users/profile_edit.html"
    success_url = reverse_lazy("users:profile")
    success_message = "Your profile is saved."

    def get_object(self, queryset=None):
        return self.request.user
