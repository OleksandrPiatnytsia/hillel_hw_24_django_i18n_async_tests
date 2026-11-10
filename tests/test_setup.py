"""Checks of the test infrastructure itself: settings, factories, fakes.

If one of these fails, the other tests can't be trusted either.
"""

from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib.auth.models import Group
from django.test import RequestFactory

from orders.emails import send_order_created_email
from payments.providers.registry import get_provider

from .factories import DEFAULT_PASSWORD, BookFactory, OrderFactory, PaymentFactory
from .fakes import stripe_event_payload, stripe_webhook_headers


def test_test_settings_are_used():
    assert settings.PASSWORD_HASHERS == ["django.contrib.auth.hashers.MD5PasswordHasher"]
    assert settings.CACHES["default"]["BACKEND"].endswith("LocMemCache")
    assert "file" not in settings.LOGGING["handlers"]
    assert not settings.ENABLE_DEBUG_TOOLBAR


def test_groups_from_data_migrations_exist(db):
    names = set(Group.objects.values_list("name", flat=True))
    assert {"Customers", "Editors", "Managers"} <= names


def test_factory_user_can_log_in_with_default_password(client, customer):
    assert client.login(username="ann", password=DEFAULT_PASSWORD)
    assert customer.groups.filter(name="Customers").exists()


def test_order_factory_with_items_counts_total(db):
    book = BookFactory(price=Decimal("100.50"))
    order = OrderFactory(items=[(book, 2)])

    assert order.items.count() == 1
    assert order.total == Decimal("201.00")


def test_fake_stripe_replaces_the_real_client(fake_stripe, db):
    payment = PaymentFactory(external_id="")
    request = RequestFactory().get("/")

    session = get_provider("stripe").start(payment, request)

    assert session.external_id in fake_stripe.sessions
    assert fake_stripe.created[0]["params"]["line_items"][0]["price_data"]["unit_amount"] == 25000
    fake_stripe.pay(session.external_id)
    payment.external_id = session.external_id
    assert get_provider("stripe").fetch_status(payment) == "succeeded"


def test_webhook_signature_passes_the_real_stripe_check():
    payload = stripe_event_payload("checkout.session.completed", "cs_test_1")
    headers = stripe_webhook_headers(payload)

    event = stripe.Webhook.construct_event(
        payload, headers["Stripe-Signature"], settings.STRIPE_WEBHOOK_SECRET
    )

    assert event.type == "checkout.session.completed"
    assert event.data.object.payment_status == "paid"


def test_failing_mailer_makes_email_fail_quietly(failing_mailer, mailoutbox, db):
    order = OrderFactory(items=[(BookFactory(), 1)])

    assert send_order_created_email(order.pk) is False
    assert mailoutbox == []
