# Haul: shopping website (FastAPI + SQLite + plain HTML/JS)

Customers can browse, add to cart, check out and see their order history.
The admin can manage products and orders and see a weekly sales dashboard with graphs.
The API is designed so a chatbot can reuse the same shop services.

## Run it

You need Python 3.10 or newer.

```bash
cd backend
python -m venv venv
# Windows:      venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt

python seed.py                      # creates shop.db with an admin + demo data
uvicorn app.main:app --reload       # start the server
```

Open http://localhost:8000 for the website and http://localhost:8000/docs for interactive API docs.

Demo accounts:

| Role     | Email               | Password      |
|----------|---------------------|---------------|
| Admin    | admin@shop.com      | admin123      |
| Customer | customer@shop.com   | customer123   |

Other seed commands:

```bash
python seed.py --no-demo   # only the admin account, no demo products/orders
python seed.py --reset     # wipe the database and seed again
```

To use a different admin email or password, edit `ADMIN` in `seed.py` before seeding.

## Project layout

```
backend/
  app/
    core/        config.py, database.py, security.py (bcrypt + JWT)
    services/    ALL business logic, the part a chatbot will reuse
    routers/     thin HTTP routes, one file per area
    models.py    database tables
    schemas.py   request and response shapes
    deps.py      "must be logged in" / "must be admin" checks
    main.py      app setup; also serves the frontend
  seed.py
frontend/
  index.html     shop
  login.html     log in / create account
  cart.html      cart + checkout
  orders.html    order history
  admin.html     dashboard, products, orders, customers
  js/api.js      one JS function per API endpoint
  js/ui.js       header, formatting, toasts
  js/vendor/     Chart.js (bundled, works offline)
```

## Database

`shop.db` (SQLite) is created in `backend/`. Tables: `users`, `products`, `cart_items`,
`orders`, `order_items`. Order items store the product name and price at the time of purchase,
so editing a product later doesn't change past orders. Products are hidden rather than deleted.

To move to Postgres later (for example Supabase or Neon), install a driver
(`pip install "psycopg[binary]"`) and set:

```bash
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

No code changes are needed.

## API reference

All routes start with `/api`. Logged-in routes need the header
`Authorization: Bearer <access_token>` (the token comes from login or register).
The name in brackets is the `operation_id`, which you can use as the chatbot tool name.

**Auth**
- `POST /auth/register` (register): create a customer account
- `POST /auth/login` (login)
- `GET /auth/me` (get_current_user)

**Products** (public)
- `GET /products` (search_products): `search`, `category`, `min_price`, `max_price`, `in_stock_only`, `sort`, `skip`, `limit`
- `GET /products/categories` (list_categories)
- `GET /products/{id}` (get_product)
- `POST /chatbot`: accepts `{ "messages": [{ "role": "user", "content": "..." }] }` and replies with in-stock product suggestions.

**Cart** (logged in; every call returns the full updated cart)
- `GET /cart` (get_cart)
- `POST /cart/items` (add_to_cart): `{ "product_id": 1, "quantity": 2 }`
- `PATCH /cart/items/{product_id}` (update_cart_item): `{ "quantity": 3 }`, 0 removes
- `DELETE /cart/items/{product_id}` (remove_from_cart)
- `DELETE /cart` (clear_cart)

**Orders** (logged in)
- `POST /orders/checkout` (checkout_cart): `{ "shipping_address": "..." }`
- `POST /orders` (create_order): order specific items without the cart:
  `{ "items": [{ "product_id": 5, "quantity": 1 }], "shipping_address": "..." }`
- `GET /orders` (list_my_orders): optional `status`
- `GET /orders/{id}` (get_my_order)
- `POST /orders/{id}/cancel` (cancel_my_order): only while placed or processing

**Admin** (admin only)
- `POST /products` (create_product), `PATCH /products/{id}` (update_product), `DELETE /products/{id}` (deactivate_product)
- `GET /admin/products` (admin_list_products): includes hidden products
- `GET /admin/customers` (admin_list_customers): with order count and total spent
- `GET /admin/customers/{id}` (admin_get_customer): with full order history
- `GET /admin/orders` (admin_list_orders): `customer_id`, `status`, `date_from`, `date_to`
- `GET /admin/orders/{id}` (admin_get_order)
- `PATCH /admin/orders/{id}/status` (admin_update_order_status): `{ "status": "shipped" }`
- `GET /admin/stats/overview` (admin_overview_stats)
- `GET /admin/stats/weekly` (admin_weekly_stats): optional `week_of=YYYY-MM-DD`

Order statuses: `placed → processing → shipped → delivered`, or `cancelled` (stock is returned).
Weeks run Monday to Sunday in UTC.

Errors always come back as `{ "detail": "plain-language message" }` with a fitting HTTP status.

## Chatbot

The shop page includes a simple product assistant. It searches active, in-stock products
through the existing product service; it does not use an external LLM or look up orders.

## Before going live

- Set a long random `SECRET_KEY` environment variable (the default is for development only).
- Restrict `allow_origins` in `app/main.py` to your domain.
- Change the demo passwords or seed with `--no-demo`.
- Checkout records the order but doesn't take payment; add a payment gateway if you need one.
