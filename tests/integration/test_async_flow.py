"""Integration: the async views inside real user flows, through AsyncClient
(the ASGI path, as in Docker). See tests/unit/test_async_views.py for why
transaction=True and sync_to_async."""

from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from django.test import AsyncClient, Client
from django.urls import reverse

from orders.models import Order

from ..factories import BookFactory, OrderFactory, UserFactory
from ..fakes import stripe_event_payload, stripe_webhook_headers

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.usefixtures("async_db_connections"),
]


async def test_payment_page_polls_status_until_webhook_confirms(fake_stripe):
    """Customer comes back from Stripe before the webhook: the page shows
    "being confirmed" and polls /orders/<pk>/status/; the webhook arrives;
    the next poll sees "paid"."""
    user = await sync_to_async(UserFactory)(username="ann")
    book = await sync_to_async(BookFactory)(price=Decimal("250.00"))
    order = await sync_to_async(OrderFactory)(user=user, items=[(book, 1)])
    customer = AsyncClient()
    await customer.aforce_login(user)

    # "Pay" -> a Stripe session; the customer returns, Stripe hasn't confirmed yet
    await customer.post(reverse("payments:pay", args=[order.pk]))
    session_id = (await order.payments.afirst()).external_id
    page = await customer.get(reverse("payments:success"), {"session_id": session_id})
    html = page.content.decode()
    status_url = reverse("orders:status", args=[order.pk])
    assert f'data-order-status-url="{status_url}"' in html
    assert "js/payment_status.js" in html

    first_poll = await customer.get(status_url)
    assert first_poll.json()["payment_status"] == Order.PaymentStatus.UNPAID

    # Stripe: the money is there, the webhook comes (a sync client: no
    # session, no cookies, as a request from Stripe's servers)
    fake_stripe.pay(session_id)
    payload = stripe_event_payload("checkout.session.completed", session_id)
    webhook = await sync_to_async(Client().post)(
        reverse("payments:webhook", args=["stripe"]),
        data=payload,
        content_type="application/json",
        headers=stripe_webhook_headers(payload),
    )
    assert webhook.status_code == 200

    second_poll = await customer.get(status_url)
    assert second_poll.json()["payment_status"] == Order.PaymentStatus.PAID
    assert second_poll.json()["amount_due"] in ("0,00", "0.00")


async def test_search_suggestion_leads_to_the_book_page():
    await sync_to_async(BookFactory)(title="Kobzar", author__name="Taras Shevchenko")
    client = AsyncClient()

    suggestions = (await client.get(reverse("books:search"), {"q": "shevch"})).json()["results"]
    page = await client.get(suggestions[0]["url"])

    assert page.status_code == 200
    assert "Kobzar" in page.content.decode()
    # The navbar of every page has the search form wired to the async view
    assert f'data-search-url="{reverse("books:search")}"' in page.content.decode()
