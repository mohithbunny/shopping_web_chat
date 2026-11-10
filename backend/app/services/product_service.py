from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Product
from app.services.errors import NotFoundError

SORTS = {
    "newest": Product.created_at.desc(),
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
    "name": Product.name.asc(),
}


def list_products(
    db: Session,
    *,
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    include_inactive: bool = False,
    sort: str = "newest",
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Product], int]:
    """Search and filter products. Returns (page of products, total matches)."""
    q = select(Product)
    if not include_inactive:
        q = q.where(Product.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(
            Product.name.ilike(like),
            Product.description.ilike(like),
            Product.category.ilike(like),
        ))
    if category:
        q = q.where(func.lower(Product.category) == category.strip().lower())
    if min_price is not None:
        q = q.where(Product.price >= min_price)
    if max_price is not None:
        q = q.where(Product.price <= max_price)
    if in_stock_only:
        q = q.where(Product.stock > 0)

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    order = SORTS.get(sort, SORTS["newest"])
    items = db.scalars(q.order_by(order, Product.id.desc()).offset(skip).limit(limit)).all()
    return list(items), total


def get_product(db: Session, product_id: int, include_inactive: bool = False) -> Product:
    product = db.get(Product, product_id)
    if not product or (not product.is_active and not include_inactive):
        raise NotFoundError(f"Product {product_id} not found")
    return product


def list_categories(db: Session) -> list[str]:
    rows = db.scalars(
        select(Product.category).where(Product.is_active.is_(True)).distinct().order_by(Product.category)
    ).all()
    return list(rows)


def create_product(db: Session, data: dict) -> Product:
    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, changes: dict) -> Product:
    product = get_product(db, product_id, include_inactive=True)
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def deactivate_product(db: Session, product_id: int) -> Product:
    """Hide a product from the shop. Past orders keep referring to it."""
    return update_product(db, product_id, {"is_active": False})
