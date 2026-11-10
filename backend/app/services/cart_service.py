"""Cart operations. Items are addressed by product_id (not cart row id),
which is how a person or chatbot naturally refers to them."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CartItem
from app.services import product_service
from app.services.errors import NotFoundError, ServiceError


def _rows(db: Session, user_id: int) -> list[CartItem]:
    return list(db.scalars(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.product))
        .order_by(CartItem.added_at, CartItem.id)
    ).all())


def get_cart(db: Session, user_id: int) -> dict:
    items = []
    for row in _rows(db, user_id):
        p = row.product
        items.append({
            "product": p,
            "quantity": row.quantity,
            "line_total": round(p.price * row.quantity, 2),
            "available": p.is_active and p.stock >= row.quantity,
        })
    return {
        "items": items,
        "total_items": sum(i["quantity"] for i in items),
        "total_amount": round(sum(i["line_total"] for i in items), 2),
    }


def _find(db: Session, user_id: int, product_id: int) -> CartItem | None:
    return db.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
    )


def _check_stock(product, quantity: int) -> None:
    if quantity > product.stock:
        if product.stock == 0:
            raise ServiceError(f"'{product.name}' is out of stock")
        raise ServiceError(f"Only {product.stock} of '{product.name}' left in stock")


def add_to_cart(db: Session, user_id: int, product_id: int, quantity: int = 1) -> dict:
    """Add a product, or increase its quantity if it's already in the cart."""
    product = product_service.get_product(db, product_id)
    item = _find(db, user_id, product_id)
    new_qty = (item.quantity if item else 0) + quantity
    _check_stock(product, new_qty)
    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(user_id=user_id, product_id=product_id, quantity=new_qty))
    db.commit()
    return get_cart(db, user_id)


def update_cart_item(db: Session, user_id: int, product_id: int, quantity: int) -> dict:
    """Set an exact quantity. Quantity 0 removes the item."""
    item = _find(db, user_id, product_id)
    if not item:
        raise NotFoundError("That product isn't in your cart")
    if quantity == 0:
        db.delete(item)
    else:
        product = product_service.get_product(db, product_id)
        _check_stock(product, quantity)
        item.quantity = quantity
    db.commit()
    return get_cart(db, user_id)


def remove_from_cart(db: Session, user_id: int, product_id: int) -> dict:
    item = _find(db, user_id, product_id)
    if not item:
        raise NotFoundError("That product isn't in your cart")
    db.delete(item)
    db.commit()
    return get_cart(db, user_id)


def clear_cart(db: Session, user_id: int) -> dict:
    for row in _rows(db, user_id):
        db.delete(row)
    db.commit()
    return get_cart(db, user_id)
