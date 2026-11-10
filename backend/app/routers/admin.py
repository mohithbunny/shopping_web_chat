from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin
from app.schemas import (
    CustomerDetail, CustomerSummary, OrderList, OrderOut, OrderStatus,
    OrderStatusUpdate, OverviewStats, ProductList, WeeklyStats,
)
from app.services import order_service, product_service, stats_service, user_service

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


# ----- Products -----
@router.get("/products", response_model=ProductList, operation_id="admin_list_products")
def admin_list_products(
    search: Optional[str] = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    """All products, including hidden ones."""
    items, total = product_service.list_products(
        db, search=search, include_inactive=include_inactive, sort="name", limit=500
    )
    return {"items": items, "total": total}


# ----- Customers -----
@router.get("/customers", response_model=list[CustomerSummary], operation_id="admin_list_customers")
def admin_list_customers(search: Optional[str] = None, db: Session = Depends(get_db)):
    """Every customer with order count, total spent and last order date."""
    return user_service.list_customers(db, search)


@router.get("/customers/{user_id}", response_model=CustomerDetail, operation_id="admin_get_customer")
def admin_get_customer(user_id: int, db: Session = Depends(get_db)):
    """One customer's summary and full order history."""
    return user_service.get_customer_detail(db, user_id)


# ----- Orders -----
@router.get("/orders", response_model=OrderList, operation_id="admin_list_orders")
def admin_list_orders(
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    date_from: Optional[date] = Query(None, description="Inclusive, YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="Inclusive, YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """All orders, filterable by customer, status and date range."""
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None
    items, total = order_service.list_orders(
        db, user_id=customer_id, status=status, start=start, end=end, skip=skip, limit=limit
    )
    return {"items": items, "total": total}


@router.get("/orders/{order_id}", response_model=OrderOut, operation_id="admin_get_order")
def admin_get_order(order_id: int, db: Session = Depends(get_db)):
    return order_service.get_order(db, order_id)


@router.patch("/orders/{order_id}/status", response_model=OrderOut, operation_id="admin_update_order_status")
def admin_update_order_status(order_id: int, body: OrderStatusUpdate, db: Session = Depends(get_db)):
    """Move an order to a new status. Cancelling returns stock."""
    return order_service.update_order_status(db, order_id, body.status)


# ----- Dashboard -----
@router.get("/stats/overview", response_model=OverviewStats, operation_id="admin_overview_stats")
def admin_overview(db: Session = Depends(get_db)):
    """All-time totals, open orders and low-stock products."""
    return stats_service.overview(db)


@router.get("/stats/weekly", response_model=WeeklyStats, operation_id="admin_weekly_stats")
def admin_weekly(
    week_of: Optional[date] = Query(None, description="Any date in the week (YYYY-MM-DD). Defaults to this week."),
    db: Session = Depends(get_db),
):
    """Revenue, orders, customers, top products and per-customer purchases for one week."""
    return stats_service.weekly(db, week_of)
