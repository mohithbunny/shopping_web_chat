UI.renderHeader("shop");

const state = { search: "", category: "", sort: "newest" };
const grid = document.getElementById("product-grid");

async function loadCategories() {
  const cats = await Api.listCategories();
  const list = document.getElementById("category-list");
  list.innerHTML = ["", ...cats].map(c =>
    `<li><button type="button" data-cat="${UI.esc(c)}" aria-pressed="${c === state.category}">${c ? UI.esc(c) : "All products"}</button></li>`
  ).join("");
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-cat]");
    if (!btn) return;
    state.category = btn.dataset.cat;
    list.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b === btn));
    loadProducts();
  });
}

function productCard(p) {
  let stockNote = "";
  if (p.stock === 0) stockNote = `<span class="stock-note">Out of stock</span>`;
  else if (p.stock <= 5) stockNote = `<span class="stock-note">Only ${p.stock} left</span>`;
  return `
    <article class="card">
      ${UI.thumb(p, `<span class="price-tag">${UI.money(p.price)}</span>`)}
      <div class="card-body">
        <span class="muted small">${UI.esc(p.category)}</span>
        <h3>${UI.esc(p.name)}</h3>
        <p class="desc">${UI.esc(p.description)}</p>
        ${stockNote}
        <button class="btn" type="button" data-add="${p.id}" ${p.stock === 0 ? "disabled" : ""}>Add to cart</button>
      </div>
    </article>`;
}

async function loadProducts() {
  try {
    const { items, total } = await Api.searchProducts({
      search: state.search, category: state.category, sort: state.sort, limit: 100,
    });
    document.getElementById("result-count").textContent = `${total} product${total === 1 ? "" : "s"}`;
    grid.innerHTML = items.length
      ? items.map(productCard).join("")
      : `<div class="empty" style="grid-column:1/-1"><h2>No products match</h2><p>Try a different search or pick another category.</p></div>`;
  } catch (err) {
    grid.innerHTML = `<div class="form-error" style="grid-column:1/-1">Couldn't load products: ${UI.esc(err.message)}</div>`;
  }
}

grid.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-add]");
  if (!btn) return;
  if (!Auth.isLoggedIn()) {
    location.href = "/login.html?next=/";
    return;
  }
  btn.disabled = true;
  try {
    const cart = await Api.addToCart(Number(btn.dataset.add), 1);
    UI.setCartCount(cart.total_items);
    UI.toast("Added to cart");
  } catch (err) {
    UI.toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  state.search = document.getElementById("search-input").value.trim();
  loadProducts();
});

document.getElementById("sort-select").addEventListener("change", (e) => {
  state.sort = e.target.value;
  loadProducts();
});

loadCategories();
loadProducts();
