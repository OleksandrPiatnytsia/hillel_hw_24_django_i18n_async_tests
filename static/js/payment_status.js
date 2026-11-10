// "The payment is being confirmed" page: asks the server every 2 seconds
// whether the order's payment status has changed (the Stripe webhook may
// come a few seconds after the customer returns). When it changes, opens
// the order page. GET /orders/<pk>/status/ -> JSON (async view
// orders.views.order_status).
(() => {
  const box = document.querySelector("[data-order-status-url]");
  if (!box) return;
  const INTERVAL_MS = 2000;
  const MAX_TRIES = 30; // ~1 minute, then a note instead of endless polling
  let tries = 0;

  async function check() {
    tries += 1;
    try {
      const response = await fetch(box.dataset.orderStatusUrl, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        if (data.payment_status !== box.dataset.paymentStatus) {
          window.location.assign(box.dataset.orderUrl);
          return;
        }
      }
    } catch (error) {
      // Network hiccup: just try again next time
    }
    if (tries < MAX_TRIES) {
      setTimeout(check, INTERVAL_MS);
    } else {
      box.querySelector("[data-status-timeout]")?.classList.remove("d-none");
    }
  }

  setTimeout(check, INTERVAL_MS);
})();
