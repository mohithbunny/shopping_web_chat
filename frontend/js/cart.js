const root = document.getElementById("cart-root");

if (UI.requireLogin()) {
  UI.renderHeader("cart");
  loadCart();
}

function render(cart) {
  UI.setCartCount(cart.total_items);
  if (!cart.items.length) {
    root.innerHTML = `
      <div class="panel empty">
        <h2>Your cart is empty</h2>
        <p>Browse the shop and add a few things you need.</p>
        <a class="btn" href="/">Go to shop</a>
      </div>`;
    return;
  }
  const blocked = cart.items.some(i => !i.available);
  const rows = cart.items.map(({ product: p, quantity, line_total, available }) => `
    <div class="cart-row">
      ${UI.thumb(p)}
      <div>
        <h3>${UI.esc(p.name)}</h3>
        <span class="muted small">${UI.money(p.price)} each</span>
        ${available ? "" : `<div class="warn">${p.is_active ? `Only ${p.stock} in stock. Lower the quantity.` : "No longer sold. Remove it to check out."}</div>`}
        <div><button type="button" class="link-btn" data-remove="${p.id}">Remove</button></div>
      </div>
      <div class="qty" aria-label="Quantity for ${UI.esc(p.name)}">
        <button type="button" data-qty="${p.id}" data-value="${quantity - 1}" aria-label="Decrease">−</button>
        <span>${quantity}</span>
        <button type="button" data-qty="${p.id}" data-value="${quantity + 1}" aria-label="Increase" ${quantity >= p.stock ? "disabled" : ""}>+</button>
      </div>
      <div class="line-total">${UI.money(line_total)}</div>
    </div>`).join("");

  root.innerHTML = `
    <div class="cart-layout">
      <div class="panel" id="cart-items">${rows}</div>
      <aside class="panel summary">
        <h2>Order summary</h2>
        <div class="summary-line"><span>Items</span><span>${cart.total_items}</span></div>
        <div class="summary-line"><span>Delivery</span><span>Free</span></div>
        <div class="summary-total"><span>Total</span><span>${UI.money(cart.total_amount)}</span></div>
        <form id="checkout-form">
          <div class="field">
            <label for="address">Delivery address</label>
            <textarea id="address" required minlength="5" placeholder="House number, street, city, PIN code"></textarea>
          </div>
          <p class="form-error hidden" id="checkout-error"></p>
          <button class="btn block" type="submit" ${blocked ? "disabled" : ""}>Place order</button>
        </form>
      </aside>
    </div>`;
}

async function loadCart() {
  try {
    render(await Api.getCart());
  } catch (err) {
    root.innerHTML = `<p class="form-error">Couldn't load your cart: ${UI.esc(err.message)}</p>`;
  }
}

root.addEventListener("click", async (e) => {
  const qtyBtn = e.target.closest("button[data-qty]");
  const removeBtn = e.target.closest("button[data-remove]");
  try {
    if (qtyBtn) {
      qtyBtn.disabled = true;
      render(await Api.updateCartItem(Number(qtyBtn.dataset.qty), Number(qtyBtn.dataset.value)));
    } else if (removeBtn) {
      render(await Api.removeFromCart(Number(removeBtn.dataset.remove)));
      UI.toast("Removed from cart");
    }
  } catch (err) {
    UI.toast(err.message, "error");
    loadCart();
  }
});

root.addEventListener("submit", async (e) => {
  if (e.target.id !== "checkout-form") return;
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  const errorEl = document.getElementById("checkout-error");
  const address = document.getElementById("address").value.trim();
  if (address.length < 5) {
    errorEl.textContent = "Enter a full delivery address.";
    errorEl.classList.remove("hidden");
    return;
  }
  btn.disabled = true;
  try {
    const order = await Api.checkoutCart(address);
    location.href = `/orders.html?placed=${order.id}`;
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
    btn.disabled = false;
  }
});
