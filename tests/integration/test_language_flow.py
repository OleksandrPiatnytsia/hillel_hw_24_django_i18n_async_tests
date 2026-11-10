"""Integration: the chosen language follows the user.

guest switches -> sign up (saved in the profile) -> another device ->
login -> the site is in the saved language again.
"""

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from users.models import User

from ..factories import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

COOKIE = settings.LANGUAGE_COOKIE_NAME


def test_guest_switches_to_english_and_signs_up_with_it(client):
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    # The test client keeps cookies between requests, like a browser
    assert client.get(reverse("books:list"))["Content-Language"] == "en"

    client.post(
        reverse("users:signup"),
        {
            "username": "john",
            "email": "john@example.com",
            "password1": "Very-strong-pass-42",
            "password2": "Very-strong-pass-42",
        },
    )

    assert User.objects.get(username="john").language == "en"


def test_saved_language_comes_back_at_login_on_another_device(customer, customer_client):
    # 1. On the laptop: switch to English -> saved in the profile
    customer_client.post(reverse("set_language"), {"language": "en", "next": "/"})
    customer.refresh_from_db()
    assert customer.language == "en"

    # 2. A phone: a new browser, no cookies -> Ukrainian before the login
    phone = Client()
    assert phone.get(reverse("books:list"))["Content-Language"] == "uk"

    # 3. Login -> the cookie with the saved language
    response = phone.post(reverse("users:login"), {"username": "ann", "password": DEFAULT_PASSWORD})

    assert response.cookies[COOKIE].value == "en"
    assert phone.get(reverse("books:list"))["Content-Language"] == "en"


def test_switching_back_updates_the_profile_again(customer, customer_client):
    customer_client.post(reverse("set_language"), {"language": "en", "next": "/"})
    customer_client.post(reverse("set_language"), {"language": "uk", "next": "/"})

    customer.refresh_from_db()
    assert customer.language == "uk"
    assert customer_client.get(reverse("books:list"))["Content-Language"] == "uk"
