"""Request and response shapes. These also become the OpenAPI schema,
which is what a chatbot will read to learn how to call each endpoint."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

OrderStatus = Literal["placed", "processing", "shipped", "delivered", "cancelled"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth / users ----------
class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Products ----------
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    """Send only the fields you want to change."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[float] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(ORMModel):
    id: int
    name: str
    description: str
    category: str
    price: float
    stock: int
    image_url: Optional[str]
    is_active: bool
    created_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int


# ---------- Cart ----------
class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=0, description="New quantity. 0 removes the item.")


class CartItemOut(BaseModel):
    product: ProductOut
    quantity: int
    line_total: float
    available: bool = Field(description="False if the product is inactive or stock is too low")


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_items: int
    total_amount: float


# ---------- Orders ----------
class CheckoutRequest(BaseModel):
    shipping_address: str = Field(min_length=5, max_length=500)


class OrderLineIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)


class OrderCreate(BaseModel):
    """Place an order directly, without using the cart."""
    items: list[OrderLineIn] = Field(min_length=1)
    shipping_address: str = Field(min_length=5, max_length=500)


class OrderItemOut(ORMModel):
    product_id: int
    product_name: str
    unit_price: float
    quantity: int
    subtotal: float


class OrderOut(ORMModel):
    id: int
    user_id: int
    customer_name: str
    customer_email: str
    status: OrderStatus
    total_amount: float
    shipping_address: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]


class OrderList(BaseModel):
    items: list[OrderOut]
    total: int


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


# ---------- Admin ----------
class CustomerSummary(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    order_count: int
    total_spent: float
    last_order_at: Optional[datetime]


class CustomerDetail(CustomerSummary):
    orders: list[OrderOut]


class LowStockProduct(BaseModel):
    id: int
    name: str
    stock: int


class OverviewStats(BaseModel):
    total_customers: int
    total_products: int
    total_orders: int
    total_revenue: float
    open_orders: int
    low_stock: list[LowStockProduct]


class DailyPoint(BaseModel):
    date: date
    revenue: float
    orders: int


class TopProduct(BaseModel):
    product_id: int
    name: str
    quantity: int
    revenue: float


class CategoryRevenue(BaseModel):
    category: str
    revenue: float


class PurchasedItem(BaseModel):
    product_name: str
    quantity: int


class WeeklyCustomer(BaseModel):
    user_id: int
    name: str
    email: str
    orders: int
    items_bought: int
    spent: float
    items: list[PurchasedItem]


class WeeklyStats(BaseModel):
    week_start: date
    week_end: date
    revenue: float
    orders: int
    items_sold: int
    average_order_value: float
    customers_ordered: int
    new_customers: int
    cancelled_orders: int
    previous_week_revenue: float
    previous_week_orders: int
    daily: list[DailyPoint]
    top_products: list[TopProduct]
    category_revenue: list[CategoryRevenue]
    customers: list[WeeklyCustomer]
    status_breakdown: dict[str, int]
