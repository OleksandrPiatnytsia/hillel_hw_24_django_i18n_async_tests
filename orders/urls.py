from django.urls import path

from . import views

# Namespace: "orders:list", "orders:checkout", "orders:detail", "orders:cancel"
app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="list"),
    path("checkout/", views.checkout, name="checkout"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/cancel/", views.order_cancel, name="cancel"),
    # JSON for the "payment is being confirmed" page (async view)
    path("<int:pk>/status/", views.order_status, name="status"),
]
