// API client. Every backend endpoint has one function here.
const API_BASE = "/api";

const Auth = {
  get token() { return localStorage.getItem("haul_token"); },
  get user() {
    try { return JSON.parse(localStorage.getItem("haul_user")); } catch { return null; }
  },
  save(token, user) {
    localStorage.setItem("haul_token", token);
    localStorage.setItem("haul_user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("haul_token");
    localStorage.removeItem("haul_user");
  },
  isLoggedIn() { return Boolean(this.token); },
  isAdmin() { return this.user?.role === "admin"; },
};

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

function errorText(data, status) {
  if (!data) return `Request failed (${status})`;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    // FastAPI validation errors
    return data.detail.map(e => {
      const field = (e.loc || []).slice(1).join(".");
      return field ? `${field}: ${e.msg}` : e.msg;
    }).join("; ");
  }
  return `Request failed (${status})`;
}

async function request(path, { method = "GET", body, query } = {}) {
  let url = API_BASE + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") params.append(k, v);
    }
    const qs = params.toString();
    if (qs) url += "?" + qs;
  }
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (Auth.token) headers.Authorization = `Bearer ${Auth.token}`;

  const res = await fetch(url, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && Auth.token) Auth.clear();
    throw new ApiError(errorText(data, res.status), res.status);
  }
  return data;
}

const Api = {
  // Auth
  register: (name, email, password) => request("/auth/register", { method: "POST", body: { name, email, password } }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/auth/me"),

  // Products
  searchProducts: (query = {}) => request("/products", { query }),
  listCategories: () => request("/products/categories"),
  getProduct: (id) => request(`/products/${id}`),

  // Cart
  getCart: () => request("/cart"),
  addToCart: (productId, quantity = 1) => request("/cart/items", { method: "POST", body: { product_id: productId, quantity } }),
  updateCartItem: (productId, quantity) => request(`/cart/items/${productId}`, { method: "PATCH", body: { quantity } }),
  removeFromCart: (productId) => request(`/cart/items/${productId}`, { method: "DELETE" }),
  clearCart: () => request("/cart", { method: "DELETE" }),

  // Orders
  checkoutCart: (shippingAddress) => request("/orders/checkout", { method: "POST", body: { shipping_address: shippingAddress } }),
  createOrder: (items, shippingAddress) => request("/orders", { method: "POST", body: { items, shipping_address: shippingAddress } }),
  listMyOrders: (query = {}) => request("/orders", { query }),
  getMyOrder: (id) => request(`/orders/${id}`),
  cancelMyOrder: (id) => request(`/orders/${id}/cancel`, { method: "POST" }),

  // Admin
  admin: {
    createProduct: (data) => request("/products", { method: "POST", body: data }),
    updateProduct: (id, changes) => request(`/products/${id}`, { method: "PATCH", body: changes }),
    deactivateProduct: (id) => request(`/products/${id}`, { method: "DELETE" }),
    listProducts: (query = {}) => request("/admin/products", { query }),
    listCustomers: (query = {}) => request("/admin/customers", { query }),
    getCustomer: (id) => request(`/admin/customers/${id}`),
    listOrders: (query = {}) => request("/admin/orders", { query }),
    getOrder: (id) => request(`/admin/orders/${id}`),
    updateOrderStatus: (id, status) => request(`/admin/orders/${id}/status`, { method: "PATCH", body: { status } }),
    overview: () => request("/admin/stats/overview"),
    weekly: (weekOf) => request("/admin/stats/weekly", { query: { week_of: weekOf } }),
  },
};
