from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin
from app.schemas import ProductCreate, ProductList, ProductOut, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductList, operation_id="search_products")
def search_products(
    search: Optional[str] = Query(None, description="Matches name, description or category"),
    category: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    in_stock_only: bool = False,
    sort: Literal["newest", "price_asc", "price_desc", "name"] = "newest",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Browse or search products available in the shop. Public."""
    items, total = product_service.list_products(
        db, search=search, category=category, min_price=min_price, max_price=max_price,
        in_stock_only=in_stock_only, sort=sort, skip=skip, limit=limit,
    )
    return {"items": items, "total": total}


@router.get("/categories", response_model=list[str], operation_id="list_categories")
def list_categories(db: Session = Depends(get_db)):
    """All product categories currently in the shop."""
    return product_service.list_categories(db)


@router.get("/{product_id}", response_model=ProductOut, operation_id="get_product")
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Details for one product."""
    return product_service.get_product(db, product_id)


# ----- Admin only -----
@router.post("", response_model=ProductOut, status_code=201, operation_id="create_product",
             dependencies=[Depends(require_admin)])
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    """Admin: add a new product."""
    return product_service.create_product(db, body.model_dump())


@router.patch("/{product_id}", response_model=ProductOut, operation_id="update_product",
              dependencies=[Depends(require_admin)])
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    """Admin: change any product fields, including price, stock, or is_active."""
    return product_service.update_product(db, product_id, body.model_dump(exclude_unset=True))


@router.delete("/{product_id}", response_model=ProductOut, operation_id="deactivate_product",
               dependencies=[Depends(require_admin)])
def deactivate_product(product_id: int, db: Session = Depends(get_db)):
    """Admin: hide a product from the shop. Order history is kept."""
    return product_service.deactivate_product(db, product_id)
