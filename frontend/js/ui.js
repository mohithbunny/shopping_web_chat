// Shared UI helpers used by every page.
const CURRENCY = { code: "INR", locale: "en-IN" }; // change here to switch currency

const UI = (() => {
  const moneyFmt = new Intl.NumberFormat(CURRENCY.locale, {
    style: "currency", currency: CURRENCY.code, minimumFractionDigits: 0, maximumFractionDigits: 2,
  });
  const money = (n) => moneyFmt.format(n || 0);

  // Backend sends naive UTC timestamps; mark them as UTC so the browser shows local time.
  const parseDate = (s) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z");
  const dateTime = (s) => parseDate(s).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
  const dateOnly = (s) => parseDate(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const TINTS = [
    ["#e1efed", "#0e6b66"], ["#fdf1d8", "#8a5d07"], ["#e4e9f7", "#2c4686"],
    ["#f6e3ea", "#8a2f52"], ["#e7f0dc", "#3e6420"], ["#efe6f7", "#5b3a86"],
  ];
  function tintFor(text) {
    let h = 0;
    for (const ch of text || "") h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return TINTS[h % TINTS.length];
  }
  function initials(name) {
    return (name || "?").split(/\s+/).filter(w => /[a-z0-9]/i.test(w)).slice(0, 2).map(w => w[0].toUpperCase()).join("");
  }

  /** Product image, or a tinted tile with the product's initials when there's no image. */
  function thumb(product, extraHtml = "") {
    if (product.image_url) {
      return `<div class="thumb"><img src="${esc(product.image_url)}" alt="" loading="lazy">${extraHtml}</div>`;
    }
    const [bg, fg] = tintFor(product.category);
    return `<div class="thumb" style="background:${bg};color:${fg}" aria-hidden="true">${esc(initials(product.name))}${extraHtml}</div>`;
  }

  const statusBadge = (s) => `<span class="status status-${esc(s)}">${esc(s)}</span>`;

  function toast(message, type = "info") {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("role", "status");
      stack.setAttribute("aria-live", "polite");
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = `toast ${type === "error" ? "error" : ""}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  function setCartCount(n) {
    const el = document.getElementById("cart-count");
    if (el) { el.textContent = n; el.classList.toggle("hidden", !n); }
  }

  async function refreshCartCount() {
    if (!Auth.isLoggedIn()) return;
    try { setCartCount((await Api.getCart()).total_items); } catch { /* ignore */ }
  }

  function renderHeader(active) {
    const user = Auth.user;
    const link = (href, label, key) =>
      `<a href="${href}" class="${active === key ? "active" : ""}" ${active === key ? 'aria-current="page"' : ""}>${label}</a>`;
    let nav = link("/", "Shop", "shop");
    if (user) {
      nav += link("/orders.html", "Orders", "orders");
      nav += link("/cart.html", `Cart<span id="cart-count" class="cart-count hidden">0</span>`, "cart");
      if (user.role === "admin") nav += link("/admin.html", "Admin", "admin");
      nav += `<span class="user-name">${esc(user.name)}</span><button type="button" id="logout-btn">Log out</button>`;
    } else {
      nav += link("/login.html", "Log in", "login");
    }
    document.getElementById("site-header").innerHTML =
      `<div class="container topbar-inner"><a class="brand" href="/">haul</a><nav class="nav" aria-label="Main">${nav}</nav></div>`;
    document.getElementById("logout-btn")?.addEventListener("click", () => {
      Auth.clear();
      location.href = "/";
    });
    refreshCartCount();
  }

  /** Send to the login page if not logged in (or not admin, when required). */
  function requireLogin({ admin = false } = {}) {
    if (!Auth.isLoggedIn()) {
      location.href = `/login.html?next=${encodeURIComponent(location.pathname)}`;
      return false;
    }
    if (admin && !Auth.isAdmin()) {
      location.href = "/";
      return false;
    }
    return true;
  }

  return { money, dateTime, dateOnly, parseDate, esc, thumb, statusBadge, toast, setCartCount, refreshCartCount, renderHeader, requireLogin };
})();
