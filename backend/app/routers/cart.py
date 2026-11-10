from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import CartItemAdd, CartItemUpdate, CartOut
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["Cart"])

# Every cart endpoint returns the full updated cart, so a caller
# (website or chatbot) always knows the current state after one call.


@router.get("", response_model=CartOut, operation_id="get_cart")
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The logged-in user's cart with line totals and grand total."""
    return cart_service.get_cart(db, user.id)


@router.post("/items", response_model=CartOut, operation_id="add_to_cart")
def add_to_cart(body: CartItemAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a product to the cart (adds to the quantity if already there)."""
    return cart_service.add_to_cart(db, user.id, body.product_id, body.quantity)


@router.patch("/items/{product_id}", response_model=CartOut, operation_id="update_cart_item")
def update_cart_item(product_id: int, body: CartItemUpdate,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Set the quantity of a product in the cart. 0 removes it."""
    return cart_service.update_cart_item(db, user.id, product_id, body.quantity)


@router.delete("/items/{product_id}", response_model=CartOut, operation_id="remove_from_cart")
def remove_from_cart(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a product from the cart."""
    return cart_service.remove_from_cart(db, user.id, product_id)


@router.delete("", response_model=CartOut, operation_id="clear_cart")
def clear_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Empty the cart."""
    return cart_service.clear_cart(db, user.id)
