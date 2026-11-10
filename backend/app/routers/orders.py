from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import CheckoutRequest, OrderCreate, OrderList, OrderOut, OrderStatus
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/checkout", response_model=OrderOut, status_code=201, operation_id="checkout_cart")
def checkout(body: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Place an order for everything in the cart, then empty the cart."""
    return order_service.checkout_cart(db, user.id, body.shipping_address)


@router.post("", response_model=OrderOut, status_code=201, operation_id="create_order")
def create_order(body: OrderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Place an order for specific products directly, without using the cart."""
    lines = [(line.product_id, line.quantity) for line in body.items]
    return order_service.create_order(db, user.id, lines, body.shipping_address)


@router.get("", response_model=OrderList, operation_id="list_my_orders")
def list_my_orders(
    status: Optional[OrderStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The logged-in user's order history, newest first."""
    items, total = order_service.list_orders(db, user_id=user.id, status=status, skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.get("/{order_id}", response_model=OrderOut, operation_id="get_my_order")
def get_my_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One of the logged-in user's orders, with its items."""
    return order_service.get_order(db, order_id, user_id=user.id)


@router.post("/{order_id}/cancel", response_model=OrderOut, operation_id="cancel_my_order")
def cancel_my_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancel an order that hasn't shipped yet. Stock is returned."""
    return order_service.cancel_order(db, order_id, user.id)
