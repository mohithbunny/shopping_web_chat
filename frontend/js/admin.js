const COLORS = {
  ink: "#18222f", teal: "#0e6b66", marigold: "#f3b13b", muted: "#5b6875", line: "#d9e0de",
  series: ["#0e6b66", "#f3b13b", "#2c4686", "#8a2f52", "#3e6420", "#5b3a86", "#b83a26", "#7a8b99"],
  status: { placed: "#f3b13b", processing: "#5c78c4", shipped: "#0e6b66", delivered: "#4c9a44", cancelled: "#b5b5b5" },
};
const STATUSES = ["placed", "processing", "shipped", "delivered", "cancelled"];


// ---------------- Tabs ----------------
const loaded = {};
function initTabs() {
  const buttons = document.querySelectorAll(".admin-side [data-tab]");
  buttons.forEach(btn => btn.addEventListener("click", () => showTab(btn.dataset.tab)));
}
function showTab(name) {
  document.querySelectorAll(".admin-side [data-tab]").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
  document.querySelectorAll(".admin-main > section").forEach(s => { s.hidden = s.id !== `tab-${name}`; });
  if (name === "dashboard") loadDashboard();
  if (name === "products") loadProducts();
  if (name === "orders") { if (!loaded.orders) loadCustomerFilter(); loadOrders(); }
  if (name === "customers") loadCustomers();
  loaded[name] = true;
}

// ---------------- Dashboard ----------------
const charts = {};
let weekOf = null;            // null = current week
let currentWeekStart = null;  // Monday of the real current week (from the server)

// Dates from the API are plain YYYY-MM-DD; treat them as UTC days to avoid timezone drift.
const dayUTC = (s) => new Date(s + "T00:00:00Z");
const addDays = (s, n) => { const d = dayUTC(s); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const fmtDay = (s, opts) => dayUTC(s).toLocaleDateString(undefined, { timeZone: "UTC", ...opts });

function delta(now, before) {
  if (!before) return now ? `<span class="delta up">New this week</span>` : `<span class="delta">No change</span>`;
  const pct = ((now - before) / before) * 100;
  const cls = pct >= 0 ? "up" : "down";
  return `<span class="delta ${cls}">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(0)}% vs previous week</span>`;
}

function drawChart(id, config) {
  if (!window.Chart) return;
  charts[id]?.destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

async function loadDashboard() {
  try {
    const [overview, w] = await Promise.all([Api.admin.overview(), Api.admin.weekly(weekOf)]);
    if (!currentWeekStart) currentWeekStart = w.week_start;
    renderOverview(overview);
    renderWeek(w);
  } catch (err) {
    UI.toast(err.message, "error");
  }
}

function renderOverview(o) {
  document.getElementById("all-time").textContent =
    `All time: ${UI.money(o.total_revenue)} from ${o.total_orders} orders, ${o.total_customers} customers, ${o.total_products} products`;
  const alerts = [];
  if (o.open_orders) alerts.push(`<div class="alert">${o.open_orders} order${o.open_orders === 1 ? "" : "s"} waiting to ship</div>`);
  for (const p of o.low_stock) {
    alerts.push(`<div class="alert">${p.stock === 0 ? "Out of stock" : `Low stock (${p.stock} left)`}: ${UI.esc(p.name)}</div>`);
  }
  document.getElementById("alerts").innerHTML = alerts.join("");
}

function renderWeek(w) {
  const isCurrent = w.week_start === currentWeekStart;
  document.getElementById("week-title").textContent = isCurrent ? "Sales this week" : "Sales for the week";
  document.getElementById("week-label").textContent =
    `${fmtDay(w.week_start, { day: "numeric", month: "short" })} – ${fmtDay(w.week_end, { day: "numeric", month: "short", year: "numeric" })}`;
  document.getElementById("next-week").disabled = isCurrent;

  document.getElementById("weekly-stats").innerHTML = `
    <div class="stat lead"><div class="label">Revenue</div><div class="value">${UI.money(w.revenue)}</div>${delta(w.revenue, w.previous_week_revenue)}</div>
    <div class="stat"><div class="label">Orders</div><div class="value">${w.orders}</div>${delta(w.orders, w.previous_week_orders)}</div>
    <div class="stat"><div class="label">Average order</div><div class="value">${UI.money(w.average_order_value)}</div></div>
    <div class="stat"><div class="label">Items sold</div><div class="value">${w.items_sold}</div></div>
    <div class="stat"><div class="label">Customers who ordered</div><div class="value">${w.customers_ordered}</div></div>
    <div class="stat"><div class="label">New customers</div><div class="value">${w.new_customers}</div></div>`;

  const money = (v) => UI.money(v);
  // Days later than today haven't happened yet: leave them blank instead of showing 0.
  const today = new Date().toISOString().slice(0, 10);
  const upToToday = (key) => w.daily.map(d => (d.date > today ? null : d[key]));

  drawChart("daily-chart", {
    data: {
      labels: w.daily.map(d => fmtDay(d.date, { weekday: "short", day: "numeric" })),
      datasets: [
        { type: "bar", label: "Revenue", data: upToToday("revenue"), backgroundColor: COLORS.teal, borderRadius: 4, yAxisID: "y", order: 2 },
        { type: "line", label: "Orders", data: upToToday("orders"), borderColor: COLORS.marigold, backgroundColor: COLORS.marigold, borderWidth: 3, tension: 0.3, yAxisID: "y1", order: 1 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { beginAtZero: true, ticks: { callback: money } },
        y1: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false }, ticks: { precision: 0 } },
        x: { grid: { display: false } },
      },
      plugins: { tooltip: { callbacks: { label: (c) => c.dataset.yAxisID === "y" ? `Revenue: ${money(c.raw)}` : `Orders: ${c.raw}` } } },
    },
  });

  drawChart("category-chart", {
    type: "doughnut",
    data: {
      labels: w.category_revenue.map(c => c.category),
      datasets: [{ data: w.category_revenue.map(c => c.revenue), backgroundColor: COLORS.series, borderWidth: 2, borderColor: "#fff" }],
    },
    options: {
      maintainAspectRatio: false, cutout: "60%",
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } }, tooltip: { callbacks: { label: (c) => `${c.label}: ${money(c.raw)}` } } },
    },
  });

  drawChart("products-chart", {
    type: "bar",
    data: {
      labels: w.top_products.map(p => p.name),
      datasets: [{ label: "Units sold", data: w.top_products.map(p => p.quantity), backgroundColor: COLORS.ink, borderRadius: 4 }],
    },
    options: {
      indexAxis: "y", maintainAspectRatio: false,
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: (c) => `Revenue: ${money(w.top_products[c.dataIndex].revenue)}` } } },
    },
  });

  const statuses = STATUSES.filter(s => w.status_breakdown[s]);
  drawChart("status-chart", {
    type: "doughnut",
    data: {
      labels: statuses,
      datasets: [{ data: statuses.map(s => w.status_breakdown[s]), backgroundColor: statuses.map(s => COLORS.status[s]), borderWidth: 2, borderColor: "#fff" }],
    },
    options: { maintainAspectRatio: false, cutout: "60%", plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } } },
  });

  document.getElementById("weekly-customers").innerHTML = w.customers.length ? `
    <table class="data">
      <thead><tr><th>Customer</th><th class="num">Orders</th><th class="num">Items</th><th class="num">Spent</th><th>Products ordered</th></tr></thead>
      <tbody>${w.customers.map(c => `
        <tr>
          <td><strong>${UI.esc(c.name)}</strong><br><span class="muted small">${UI.esc(c.email)}</span></td>
          <td class="num">${c.orders}</td>
          <td class="num">${c.items_bought}</td>
          <td class="num"><strong>${UI.money(c.spent)}</strong></td>
          <td><div class="chips">${c.items.map(i => `<span class="chip">${UI.esc(i.product_name)} × ${i.quantity}</span>`).join("")}</div></td>
        </tr>`).join("")}
      </tbody>
    </table>` : `<p class="muted">No orders this week.</p>`;
}

document.getElementById("prev-week").addEventListener("click", () => {
  weekOf = addDays(weekOf || currentWeekStart, -7);
  loadDashboard();
});
document.getElementById("next-week").addEventListener("click", () => {
  const next = addDays(weekOf || currentWeekStart, 7);
  weekOf = next >= currentWeekStart ? null : next;
  loadDashboard();
});

// ---------------- Products ----------------
let products = [];
let editingId = null;
const pf = {
  form: document.getElementById("product-form"),
  name: document.getElementById("p-name"), category: document.getElementById("p-category"),
  price: document.getElementById("p-price"), stock: document.getElementById("p-stock"),
  image: document.getElementById("p-image"), desc: document.getElementById("p-desc"),
  error: document.getElementById("product-error"), submit: document.getElementById("product-submit"),
  cancel: document.getElementById("product-cancel"), title: document.getElementById("product-form-title"),
};

async function loadProducts() {
  try {
    products = (await Api.admin.listProducts()).items;
    const cats = [...new Set(products.map(p => p.category))].sort();
    document.getElementById("category-options").innerHTML = cats.map(c => `<option value="${UI.esc(c)}">`).join("");
    document.getElementById("product-table").innerHTML = `
      <table class="data">
        <thead><tr><th>Product</th><th class="num">Price</th><th class="num">Stock</th><th>Status</th><th></th></tr></thead>
        <tbody>${products.map(p => `
          <tr class="${p.is_active ? "" : "inactive"}">
            <td><strong>${UI.esc(p.name)}</strong><br><span class="muted small">${UI.esc(p.category)}</span></td>
            <td class="num">${UI.money(p.price)}</td>
            <td class="num" ${p.stock <= 5 && p.is_active ? 'style="color:var(--danger);font-weight:600"' : ""}>${p.stock}</td>
            <td>${p.is_active ? "In shop" : "Hidden"}</td>
            <td class="num">
              <button type="button" class="btn secondary small" data-edit="${p.id}">Edit</button>
              ${p.is_active
                ? `<button type="button" class="btn danger small" data-hide="${p.id}">Hide</button>`
                : `<button type="button" class="btn secondary small" data-show="${p.id}">Show</button>`}
            </td>
          </tr>`).join("")}
        </tbody>
      </table>`;
  } catch (err) {
    UI.toast(err.message, "error");
  }
}

function resetProductForm() {
  editingId = null;
  pf.form.reset();
  pf.error.classList.add("hidden");
  pf.title.textContent = "Add a product";
  pf.submit.textContent = "Add product";
  pf.cancel.classList.add("hidden");
}

function editProduct(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;
  editingId = id;
  pf.name.value = p.name; pf.category.value = p.category; pf.price.value = p.price;
  pf.stock.value = p.stock; pf.image.value = p.image_url || ""; pf.desc.value = p.description;
  pf.title.textContent = `Edit ${p.name}`;
  pf.submit.textContent = "Save changes";
  pf.cancel.classList.remove("hidden");
  pf.error.classList.add("hidden");
  pf.form.scrollIntoView({ behavior: "smooth", block: "start" });
  pf.name.focus();
}

pf.cancel.addEventListener("click", resetProductForm);

pf.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    name: pf.name.value.trim(),
    category: pf.category.value.trim(),
    price: Number(pf.price.value),
    stock: Number(pf.stock.value),
    image_url: pf.image.value.trim() || null,
    description: pf.desc.value.trim(),
  };
  const problems = [];
  if (!data.name) problems.push("Enter a name");
  if (!data.category) problems.push("Enter a category");
  if (!(data.price > 0)) problems.push("Price must be more than 0");
  if (!Number.isInteger(data.stock) || data.stock < 0) problems.push("Stock must be a whole number, 0 or more");
  if (problems.length) {
    pf.error.textContent = problems.join(". ") + ".";
    pf.error.classList.remove("hidden");
    return;
  }
  pf.submit.disabled = true;
  try {
    if (editingId) {
      await Api.admin.updateProduct(editingId, data);
      UI.toast("Changes saved");
    } else {
      await Api.admin.createProduct(data);
      UI.toast("Product added");
    }
    resetProductForm();
    loadProducts();
  } catch (err) {
    pf.error.textContent = err.message;
    pf.error.classList.remove("hidden");
  } finally {
    pf.submit.disabled = false;
  }
});

document.getElementById("product-table").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  try {
    if (btn.dataset.edit) editProduct(Number(btn.dataset.edit));
    if (btn.dataset.hide) { await Api.admin.deactivateProduct(btn.dataset.hide); UI.toast("Product hidden from shop"); loadProducts(); }
    if (btn.dataset.show) { await Api.admin.updateProduct(btn.dataset.show, { is_active: true }); UI.toast("Product back in shop"); loadProducts(); }
  } catch (err) {
    UI.toast(err.message, "error");
  }
});

// ---------------- Orders ----------------
async function loadCustomerFilter() {
  try {
    const customers = await Api.admin.listCustomers();
    document.getElementById("f-customer").innerHTML = `<option value="">All customers</option>` +
      customers.sort((a, b) => a.name.localeCompare(b.name))
        .map(c => `<option value="${c.id}">${UI.esc(c.name)}</option>`).join("");
  } catch { /* filter stays at "All customers" */ }
}

async function loadOrders() {
  const query = {
    status: document.getElementById("f-status").value,
    customer_id: document.getElementById("f-customer").value,
    date_from: document.getElementById("f-from").value,
    date_to: document.getElementById("f-to").value,
    limit: 200,
  };
  try {
    const { items, total } = await Api.admin.listOrders(query);
    document.getElementById("orders-count").textContent =
      items.length < total ? `Showing ${items.length} of ${total} orders` : `${total} order${total === 1 ? "" : "s"}`;
    document.getElementById("orders-table").innerHTML = items.length ? `
      <table class="data">
        <thead><tr><th>Order</th><th>Customer</th><th>Placed</th><th>Items</th><th class="num">Total</th><th>Status</th></tr></thead>
        <tbody>${items.map(o => `
          <tr>
            <td><strong>#${o.id}</strong></td>
            <td>${UI.esc(o.customer_name)}<br><span class="muted small">${UI.esc(o.customer_email)}</span></td>
            <td class="small">${UI.dateTime(o.created_at)}</td>
            <td><div class="chips">${o.items.map(i => `<span class="chip">${UI.esc(i.product_name)} × ${i.quantity}</span>`).join("")}</div></td>
            <td class="num"><strong>${UI.money(o.total_amount)}</strong></td>
            <td>
              <select data-order="${o.id}" data-current="${o.status}" aria-label="Status for order ${o.id}" ${o.status === "cancelled" ? "disabled" : ""}>
                ${STATUSES.map(s => `<option value="${s}" ${s === o.status ? "selected" : ""}>${s}</option>`).join("")}
              </select>
            </td>
          </tr>`).join("")}
        </tbody>
      </table>` : `<p class="muted">No orders match these filters.</p>`;
  } catch (err) {
    UI.toast(err.message, "error");
  }
}

document.getElementById("order-filters").addEventListener("submit", (e) => { e.preventDefault(); loadOrders(); });
document.getElementById("order-filters").addEventListener("reset", () => setTimeout(loadOrders));

document.getElementById("orders-table").addEventListener("change", async (e) => {
  const sel = e.target.closest("select[data-order]");
  if (!sel) return;
  const id = sel.dataset.order;
  if (sel.value === "cancelled" && !confirm(`Cancel order #${id}? Stock will be returned and this can't be undone.`)) {
    sel.value = sel.dataset.current;
    return;
  }
  try {
    const order = await Api.admin.updateOrderStatus(id, sel.value);
    sel.dataset.current = order.status;
    if (order.status === "cancelled") sel.disabled = true;
    UI.toast(`Order #${id} marked ${order.status}`);
  } catch (err) {
    sel.value = sel.dataset.current;
    UI.toast(err.message, "error");
  }
});

// ---------------- Customers ----------------
async function loadCustomers() {
  const search = document.getElementById("customer-search-input").value.trim();
  try {
    const customers = await Api.admin.listCustomers({ search });
    document.getElementById("customers-table").innerHTML = customers.length ? `
      <table class="data">
        <thead><tr><th>Customer</th><th>Joined</th><th class="num">Orders</th><th class="num">Total spent</th><th>Last order</th></tr></thead>
        <tbody>${customers.map(c => `
          <tr class="clickable" data-customer="${c.id}" tabindex="0">
            <td><strong>${UI.esc(c.name)}</strong><br><span class="muted small">${UI.esc(c.email)}</span></td>
            <td class="small">${UI.dateOnly(c.created_at)}</td>
            <td class="num">${c.order_count}</td>
            <td class="num"><strong>${UI.money(c.total_spent)}</strong></td>
            <td class="small">${c.last_order_at ? UI.dateOnly(c.last_order_at) : "No orders yet"}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : `<p class="muted">No customers match that search.</p>`;
  } catch (err) {
    UI.toast(err.message, "error");
  }
}

async function showCustomer(id) {
  const box = document.getElementById("customer-detail");
  try {
    const c = await Api.admin.getCustomer(id);
    box.innerHTML = `
      <div class="panel">
        <h2>${UI.esc(c.name)}’s orders</h2>
        <p class="muted small">${UI.esc(c.email)}. ${c.order_count} orders, ${UI.money(c.total_spent)} spent (excluding cancelled).</p>
        ${c.orders.length ? `
        <div class="table-wrap"><table class="data">
          <thead><tr><th>Order</th><th>Placed</th><th>Items</th><th class="num">Total</th><th>Status</th></tr></thead>
          <tbody>${c.orders.map(o => `
            <tr>
              <td><strong>#${o.id}</strong></td>
              <td class="small">${UI.dateTime(o.created_at)}</td>
              <td><div class="chips">${o.items.map(i => `<span class="chip">${UI.esc(i.product_name)} × ${i.quantity}</span>`).join("")}</div></td>
              <td class="num">${UI.money(o.total_amount)}</td>
              <td>${UI.statusBadge(o.status)}</td>
            </tr>`).join("")}
          </tbody>
        </table></div>` : `<p class="muted">This customer hasn’t ordered anything yet.</p>`}
      </div>`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    UI.toast(err.message, "error");
  }
}

const customersTable = document.getElementById("customers-table");
customersTable.addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-customer]");
  if (row) showCustomer(row.dataset.customer);
});
customersTable.addEventListener("keydown", (e) => {
  const row = e.target.closest("tr[data-customer]");
  if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showCustomer(row.dataset.customer); }
});
document.getElementById("customer-search").addEventListener("submit", (e) => { e.preventDefault(); loadCustomers(); });

// ---------------- Start ----------------
if (UI.requireLogin({ admin: true })) {
  UI.renderHeader("admin");
  if (window.Chart) {
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = COLORS.muted;
    Chart.defaults.borderColor = COLORS.line;
  }
  initTabs();
  loadDashboard();
}
