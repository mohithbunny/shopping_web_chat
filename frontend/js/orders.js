const root = document.getElementById("orders-root");
const CANCELLABLE = ["placed", "processing"];

if (UI.requireLogin()) {
  UI.renderHeader("orders");
  const placed = new URLSearchParams(location.search).get("placed");
  if (placed) {
    UI.toast(`Order #${placed} placed`);
    history.replaceState(null, "", "/orders.html");
  }
  loadOrders();
}

function orderCard(o) {
  const items = o.items.map(i => `
    <tr>
      <td>${UI.esc(i.product_name)} <span class="muted">× ${i.quantity}</span></td>
      <td>${UI.money(i.subtotal)}</td>
    </tr>`).join("");
  return `
    <article class="order">
      <div class="order-head">
        <h3>Order #${o.id}</h3>
        <span class="muted small">${UI.dateTime(o.created_at)}</span>
        ${UI.statusBadge(o.status)}
        <span class="total">${UI.money(o.total_amount)}</span>
      </div>
      <div class="order-body">
        <table class="order-items"><tbody>${items}</tbody></table>
        <div class="order-foot">
          <span class="muted small">Delivering to: ${UI.esc(o.shipping_address)}</span>
          ${CANCELLABLE.includes(o.status) ? `<button type="button" class="btn danger small" data-cancel="${o.id}">Cancel order</button>` : ""}
        </div>
      </div>
    </article>`;
}

async function loadOrders() {
  try {
    const { items } = await Api.listMyOrders({ limit: 200 });
    root.innerHTML = items.length
      ? items.map(orderCard).join("")
      : `<div class="panel empty"><h2>No orders yet</h2><p>When you place an order, it shows up here with its status.</p><a class="btn" href="/">Go to shop</a></div>`;
  } catch (err) {
    root.innerHTML = `<p class="form-error">Couldn't load your orders: ${UI.esc(err.message)}</p>`;
  }
}

root.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-cancel]");
  if (!btn) return;
  const id = btn.dataset.cancel;
  if (!confirm(`Cancel order #${id}?`)) return;
  btn.disabled = true;
  try {
    await Api.cancelMyOrder(id);
    UI.toast(`Order #${id} cancelled`);
    loadOrders();
  } catch (err) {
    UI.toast(err.message, "error");
    btn.disabled = false;
  }
});
