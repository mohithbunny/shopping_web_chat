"""Numbers for the admin dashboard. Weeks run Monday to Sunday, in UTC.

Weekly figures are aggregated in Python after one query, which keeps the code
easy to read and works on any database. If order volume grows large, move
these sums into SQL GROUP BY queries."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import LOW_STOCK_THRESHOLD
from app.core.database import utcnow
from app.models import ORDER_STATUSES, Order, OrderItem, Product, User


def week_bounds(any_day: Optional[date] = None) -> tuple[date, datetime, datetime]:
    day = any_day or utcnow().date()
    monday = day - timedelta(days=day.weekday())
    start = datetime.combine(monday, time.min)
    return monday, start, start + timedelta(days=7)


def overview(db: Session) -> dict:
    not_cancelled = Order.status != "cancelled"
    low_stock = db.scalars(
        select(Product)
        .where(Product.is_active.is_(True), Product.stock <= LOW_STOCK_THRESHOLD)
        .order_by(Product.stock, Product.name)
    ).all()
    return {
        "total_customers": db.scalar(select(func.count(User.id)).where(User.role == "customer")),
        "total_products": db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))),
        "total_orders": db.scalar(select(func.count(Order.id)).where(not_cancelled)),
        "total_revenue": round(float(db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(not_cancelled)
        )), 2),
        "open_orders": db.scalar(
            select(func.count(Order.id)).where(Order.status.in_(("placed", "processing")))
        ),
        "low_stock": [{"id": p.id, "name": p.name, "stock": p.stock} for p in low_stock],
    }


def weekly(db: Session, week_of: Optional[date] = None) -> dict:
    """Sales for the week containing `week_of` (defaults to this week)."""
    monday, start, end = week_bounds(week_of)

    orders = db.scalars(
        select(Order)
        .where(Order.created_at >= start, Order.created_at < end)
        .options(selectinload(Order.items).selectinload(OrderItem.product), selectinload(Order.user))
    ).all()
    valid = [o for o in orders if o.status != "cancelled"]

    daily = {monday + timedelta(days=i): {"revenue": 0.0, "orders": 0} for i in range(7)}
    products: dict[int, dict] = {}
    categories: dict[str, float] = defaultdict(float)
    customers: dict[int, dict] = {}

    for o in valid:
        day = daily[o.created_at.date()]
        day["revenue"] += o.total_amount
        day["orders"] += 1

        c = customers.setdefault(o.user_id, {
            "user_id": o.user_id, "name": o.customer_name, "email": o.customer_email,
            "orders": 0, "items_bought": 0, "spent": 0.0, "_items": defaultdict(int),
        })
        c["orders"] += 1
        c["spent"] += o.total_amount

        for it in o.items:
            p = products.setdefault(it.product_id, {
                "product_id": it.product_id, "name": it.product_name, "quantity": 0, "revenue": 0.0,
            })
            p["quantity"] += it.quantity
            p["revenue"] += it.subtotal
            categories[it.product.category if it.product else "Other"] += it.subtotal
            c["items_bought"] += it.quantity
            c["_items"][it.product_name] += it.quantity

    revenue = round(sum(o.total_amount for o in valid), 2)
    items_sold = sum(p["quantity"] for p in products.values())

    prev_start, prev_end = start - timedelta(days=7), start
    prev_filter = (Order.created_at >= prev_start, Order.created_at < prev_end, Order.status != "cancelled")
    prev_revenue = db.scalar(select(func.coalesce(func.sum(Order.total_amount), 0)).where(*prev_filter))
    prev_orders = db.scalar(select(func.count(Order.id)).where(*prev_filter))

    new_customers = db.scalar(
        select(func.count(User.id)).where(
            User.role == "customer", User.created_at >= start, User.created_at < end
        )
    )

    status_breakdown = {s: 0 for s in ORDER_STATUSES}
    for o in orders:
        status_breakdown[o.status] = status_breakdown.get(o.status, 0) + 1

    customer_list = []
    for c in sorted(customers.values(), key=lambda c: c["spent"], reverse=True):
        bought = c.pop("_items")
        c["spent"] = round(c["spent"], 2)
        c["items"] = [
            {"product_name": n, "quantity": q}
            for n, q in sorted(bought.items(), key=lambda kv: kv[1], reverse=True)
        ]
        customer_list.append(c)

    return {
        "week_start": monday,
        "week_end": monday + timedelta(days=6),
        "revenue": revenue,
        "orders": len(valid),
        "items_sold": items_sold,
        "average_order_value": round(revenue / len(valid), 2) if valid else 0.0,
        "customers_ordered": len(customers),
        "new_customers": new_customers,
        "cancelled_orders": len(orders) - len(valid),
        "previous_week_revenue": round(float(prev_revenue), 2),
        "previous_week_orders": prev_orders,
        "daily": [
            {"date": d, "revenue": round(v["revenue"], 2), "orders": v["orders"]}
            for d, v in daily.items()
        ],
        "top_products": [
            {**p, "revenue": round(p["revenue"], 2)}
            for p in sorted(products.values(), key=lambda p: p["quantity"], reverse=True)[:8]
        ],
        "category_revenue": [
            {"category": k, "revenue": round(v, 2)}
            for k, v in sorted(categories.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "customers": customer_list,
        "status_breakdown": status_breakdown,
    }
