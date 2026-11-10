from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import CANCELLABLE_STATUSES, CartItem, Order, OrderItem, Product
from app.services.errors import NotFoundError, ServiceError

_LOAD = (selectinload(Order.items), selectinload(Order.user))


def _build_order(db: Session, user_id: int, lines: list[tuple[int, int]], shipping_address: str) -> Order:
    """Validate every line first, then reserve stock. Nothing changes if any line fails."""
    if not lines:
        raise ServiceError("An order needs at least one item")

    wanted: dict[int, int] = {}
    for product_id, qty in lines:
        if qty < 1:
            raise ServiceError("Quantities must be at least 1")
        wanted[product_id] = wanted.get(product_id, 0) + qty

    products = {
        p.id: p for p in db.scalars(select(Product).where(Product.id.in_(wanted))).all()
    }
    for product_id, qty in wanted.items():
        p = products.get(product_id)
        if not p or not p.is_active:
            raise NotFoundError(f"Product {product_id} is no longer available")
        if p.stock < qty:
            raise ServiceError(f"Only {p.stock} of '{p.name}' left in stock")

    order = Order(user_id=user_id, shipping_address=shipping_address.strip(), status="placed")
    total = 0.0
    for product_id, qty in wanted.items():
        p = products[product_id]
        subtotal = round(p.price * qty, 2)
        order.items.append(OrderItem(
            product_id=p.id, product_name=p.name, unit_price=p.price,
            quantity=qty, subtotal=subtotal,
        ))
        p.stock -= qty
        total += subtotal
    order.total_amount = round(total, 2)
    db.add(order)
    return order


def create_order(db: Session, user_id: int, lines: list[tuple[int, int]], shipping_address: str) -> Order:
    """Place an order for specific products, without touching the cart."""
    order = _build_order(db, user_id, lines, shipping_address)
    db.commit()
    return get_order(db, order.id)


def checkout_cart(db: Session, user_id: int, shipping_address: str) -> Order:
    """Turn the user's cart into an order and empty the cart."""
    cart_rows = list(db.scalars(select(CartItem).where(CartItem.user_id == user_id)).all())
    if not cart_rows:
        raise ServiceError("Your cart is empty")
    order = _build_order(db, user_id, [(r.product_id, r.quantity) for r in cart_rows], shipping_address)
    for row in cart_rows:
        db.delete(row)
    db.commit()
    return get_order(db, order.id)


def get_order(db: Session, order_id: int, user_id: Optional[int] = None) -> Order:
    """Fetch one order. Pass user_id to make sure it belongs to that user."""
    order = db.scalar(select(Order).where(Order.id == order_id).options(*_LOAD))
    if not order or (user_id is not None and order.user_id != user_id):
        raise NotFoundError(f"Order #{order_id} not found")
    return order


def list_orders(
    db: Session,
    *,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Order], int]:
    """Newest first. Filter by customer, status and/or date range [start, end)."""
    q = select(Order)
    if user_id is not None:
        q = q.where(Order.user_id == user_id)
    if status:
        q = q.where(Order.status == status)
    if start:
        q = q.where(Order.created_at >= start)
    if end:
        q = q.where(Order.created_at < end)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    orders = db.scalars(
        q.options(*_LOAD).order_by(Order.created_at.desc(), Order.id.desc()).offset(skip).limit(limit)
    ).all()
    return list(orders), total


def _restock(order: Order) -> None:
    for item in order.items:
        if item.product:
            item.product.stock += item.quantity


def cancel_order(db: Session, order_id: int, user_id: int) -> Order:
    """Customer cancels their own order. Only possible before it ships."""
    order = get_order(db, order_id, user_id=user_id)
    if order.status not in CANCELLABLE_STATUSES:
        raise ServiceError(f"Order #{order_id} is {order.status} and can no longer be cancelled")
    _restock(order)
    order.status = "cancelled"
    db.commit()
    return get_order(db, order_id)


def update_order_status(db: Session, order_id: int, status: str) -> Order:
    """Admin moves an order through placed → processing → shipped → delivered."""
    order = get_order(db, order_id)
    if order.status == status:
        return order
    if order.status == "cancelled":
        raise ServiceError("Cancelled orders can't be reopened")
    if status == "cancelled":
        _restock(order)
    order.status = status
    db.commit()
    return get_order(db, order_id)
