from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Order, User
from app.services.errors import AuthError, ConflictError, NotFoundError
from app.services import order_service


def register_user(db: Session, name: str, email: str, password: str, role: str = "customer") -> User:
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("An account with this email already exists")
    user = User(name=name.strip(), email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("Email or password is incorrect")
    return user


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return user


def _customer_summary_query():
    # Cancelled orders don't count toward spend or order count.
    return (
        select(
            User,
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .outerjoin(Order, and_(Order.user_id == User.id, Order.status != "cancelled"))
        .where(User.role == "customer")
        .group_by(User.id)
    )


def _row_to_summary(row) -> dict:
    user, order_count, total_spent, last_order_at = row
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at,
        "order_count": order_count,
        "total_spent": round(float(total_spent), 2),
        "last_order_at": last_order_at,
    }


def list_customers(db: Session, search: Optional[str] = None) -> list[dict]:
    """All customers with order count, total spent and last order date."""
    q = _customer_summary_query()
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(User.name.ilike(like), User.email.ilike(like)))
    rows = db.execute(q.order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())).all()
    return [_row_to_summary(r) for r in rows]


def get_customer_detail(db: Session, user_id: int) -> dict:
    row = db.execute(_customer_summary_query().where(User.id == user_id)).first()
    if not row:
        raise NotFoundError(f"Customer {user_id} not found")
    orders, _ = order_service.list_orders(db, user_id=user_id, limit=200)
    return {**_row_to_summary(row), "orders": orders}
