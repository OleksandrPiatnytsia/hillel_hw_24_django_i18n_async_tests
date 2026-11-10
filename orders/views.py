from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from books.views import ElidedPaginationMixin
from cart.cart import Cart

from .forms import CheckoutForm
from .models import Order
from .services import OrderError, cancel_order, create_order


@login_required  # anonymous -> LOGIN_URL?next=/orders/checkout/; the cart stays
def checkout(request):
    """Delivery form + cart summary; POST creates the order.

    GET  -> the form, prefilled from the profile.
    POST -> valid form -> create_order() (one transaction) -> clear the cart
            -> the order page with the "Pay" button. A stock problem -> back
            to the cart with the messages, nothing is saved.
    """
    cart = Cart(request)
    if not cart:
        messages.info(request, _("Your cart is empty."))
        return redirect("cart:detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                data = form.cleaned_data
                order = create_order(
                    request.user,
                    cart.quantities(),
                    full_name=data["full_name"],
                    phone=data["phone"],
                    address=data["address"],
                )
            except OrderError as error:
                for text in error.messages:
                    messages.error(request, text)
                # The cart page shows the current stock next to each book
                return redirect("cart:detail")

            # Only after a successful COMMIT: if create_order() failed,
            # the cart stays for the next attempt
            cart.clear()
            if data["save_to_profile"]:
                # The next checkout is prefilled with these. The name is not
                # saved: "full name" can't be split into first / last name
                # reliably; it's edited on the profile page.
                request.user.phone = data["phone"]
                request.user.address = data["address"]
                request.user.save(update_fields=["phone", "address"])
            messages.success(
                request,
                _(
                    "%(order)s is created, the books are reserved for you. "
                    "Pay for it with the “Pay” button."
                )
                % {"order": order},
            )
            # To the order page, not straight to Stripe: the customer sees the
            # created order first and pays with the "Pay" button
            # (payments.views.pay) — now or later from "My orders".
            return redirect(order)  # Order.get_absolute_url()
    else:
        # Prefilled from the profile (users.User): first + last name, phone,
        # address. Empty for a new user; the checkbox then saves them.
        form = CheckoutForm(
            initial={
                "full_name": request.user.get_full_name(),
                "phone": request.user.phone,
                "address": request.user.address,
            }
        )

    return render(request, "orders/checkout.html", {"form": form})


class OrderListView(LoginRequiredMixin, ElidedPaginationMixin, ListView):
    """My orders: only the current user's, newest first (Order.Meta.ordering).

    Template: orders/order_list.html
    """

    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .annotate(
                # Copies in the order (2 + 1 = 3), calculated by the database
                # in the same query: GROUP BY order + SUM, not one query per row
                books_count=Sum("items__quantity")
            )
            # Explicit: Django drops Meta.ordering from queries with GROUP BY
            # (aggregation), the list would come in any order. "-pk": a stable
            # order for equal dates, so pages don't repeat or skip orders.
            .order_by("-created_at", "-pk")
        )


@login_required
def order_detail(request, pk):
    # user=request.user: someone else's order -> 404, the same as a missing
    # one (403 would tell that order #pk exists)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__book"), pk=pk, user=request.user
    )
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, pk):
    # Someone else's or a missing order -> 404, like order_detail.
    # cancel_order() checks the owner again under the lock; this is for
    # the right answer to the user.
    get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order = cancel_order(pk, user=request.user)
    except OrderError as error:
        for text in error.messages:
            messages.error(request, text)
    else:
        messages.success(
            request, _("%(order)s is cancelled. The books are back in stock.") % {"order": order}
        )
    return redirect("orders:detail", pk=pk)
