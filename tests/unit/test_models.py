"""Unit tests of the models: properties, save() rules, database constraints.

@pytest.mark.parametrize runs one test function with several inputs:
every tuple is a separate test in the report (test_x[in_stock], ...).
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from books.models import Book, BookQuerySet
from orders.models import Order
from payments.models import Payment
from users.models import User

from ..factories import BookFactory, OrderFactory, OrderItemFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db  # every test in this file uses the database


# ---------------------------------------------------------------------------
# users.User
# ---------------------------------------------------------------------------


def test_user_email_is_saved_in_lowercase():
    user = User.objects.create_user("ann", email="Ann.Shevchenko@Mail.COM", password="x")

    user.refresh_from_db()
    assert user.email == "ann.shevchenko@mail.com"


def test_user_email_lowercase_constraint_protects_update():
    """QuerySet.update() skips save(): the database CHECK constraint stops it."""
    user = UserFactory()

    with pytest.raises(IntegrityError):
        User.objects.filter(pk=user.pk).update(email="UPPER@EXAMPLE.COM")


# ---------------------------------------------------------------------------
# books.Book
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stock", "expected"),
    [(0, False), (1, True), (5, True), (6, False)],
)
def test_book_is_low_stock(stock, expected):
    # build(): an object in memory only, a property needs no database
    assert BookFactory.build(stock=stock).is_low_stock is expected


def test_book_without_cover_uses_placeholder():
    assert BookFactory.build(cover="").cover_url.endswith("img/no-cover.svg")


def test_book_str_has_title_and_author():
    book = BookFactory(title="Kobzar", author__name="Taras Shevchenko")

    assert str(book) == "Kobzar — Taras Shevchenko"


@pytest.mark.parametrize(
    ("status", "expected_titles"),
    [
        (BookQuerySet.STOCK_IN, {"low", "plenty"}),
        (BookQuerySet.STOCK_LOW, {"low"}),
        (BookQuerySet.STOCK_OUT, {"none"}),
        ("", {"none", "low", "plenty"}),  # empty / unknown -> no filter
    ],
)
def test_books_by_stock_status(status, expected_titles):
    BookFactory(title="none", stock=0)
    BookFactory(title="low", stock=3)
    BookFactory(title="plenty", stock=50)

    titles = set(Book.objects.by_stock_status(status).values_list("title", flat=True))

    assert titles == expected_titles


# ---------------------------------------------------------------------------
# orders.Order / OrderItem
# ---------------------------------------------------------------------------


def test_order_item_cost_is_price_times_quantity():
    item = OrderItemFactory(book__price=Decimal("120.50"), quantity=3)

    assert item.cost == Decimal("361.50")


def test_order_item_quantity_zero_is_rejected_by_database():
    with pytest.raises(IntegrityError):
        OrderItemFactory(quantity=0)


@pytest.mark.parametrize(
    ("paid", "expected_status", "expected_percent"),
    [
        ([], Order.PaymentStatus.UNPAID, 0),
        (["100.00"], Order.PaymentStatus.PARTIALLY_PAID, 40),
        (["100.00", "150.00"], Order.PaymentStatus.PAID, 100),
    ],
)
def test_order_payment_status_follows_succeeded_payments(paid, expected_status, expected_percent):
    order = OrderFactory(total=Decimal("250.00"))
    for amount in paid:
        PaymentFactory(order=order, amount=Decimal(amount), status=Payment.Status.SUCCEEDED)
    # A pending payment never counts
    PaymentFactory(order=order, amount=Decimal("250.00"), status=Payment.Status.PENDING)

    order.refresh_payment_status()

    order.refresh_from_db()
    assert order.payment_status == expected_status
    assert order.paid_percent == expected_percent
    assert order.amount_due == Decimal("250.00") - sum(Decimal(a) for a in paid)


def test_order_refresh_payment_status_reports_no_change():
    order = OrderFactory(total=Decimal("250.00"))

    assert order.refresh_payment_status() is False  # unpaid -> unpaid


@pytest.mark.parametrize(
    ("status", "payment_status", "expected"),
    [
        (Order.Status.NEW, Order.PaymentStatus.UNPAID, True),
        (Order.Status.NEW, Order.PaymentStatus.PARTIALLY_PAID, False),
        (Order.Status.PROCESSING, Order.PaymentStatus.UNPAID, False),
        (Order.Status.CANCELLED, Order.PaymentStatus.UNPAID, False),
    ],
)
def test_order_can_be_cancelled_by_customer(status, payment_status, expected):
    order = OrderFactory.build(status=status, payment_status=payment_status)

    assert order.can_be_cancelled_by_customer is expected


# ---------------------------------------------------------------------------
# payments.Payment
# ---------------------------------------------------------------------------


def test_payment_same_stripe_session_cannot_be_saved_twice():
    PaymentFactory(external_id="cs_test_same")

    with pytest.raises(IntegrityError):
        PaymentFactory(external_id="cs_test_same")


def test_two_manual_payments_without_external_id_are_allowed():
    order = OrderFactory(total=Decimal("250.00"))
    PaymentFactory(order=order, provider=Payment.Provider.MANUAL, external_id="", amount=10)
    PaymentFactory(order=order, provider=Payment.Provider.MANUAL, external_id="", amount=20)

    assert order.payments.count() == 2
