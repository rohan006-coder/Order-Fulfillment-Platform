from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.entities import OrderStatus, PaymentStatus

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class OrderCreate(BaseModel):
    warehouse_id: int
    items: list[OrderItemCreate] = Field(min_length=1)

class OrderItemResponse(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal

class OrderResponse(BaseModel):
    id: int
    order_number: str
    customer_id: int
    warehouse_id: int
    total_amount: Decimal
    status: OrderStatus
    payment_status: PaymentStatus
    items: list[OrderItemResponse]
    created_at: datetime
