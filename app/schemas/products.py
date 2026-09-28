from decimal import Decimal
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str
    description: str | None = None
    category_id: int | None = None
    price: Decimal = Field(gt=0)
    cost_price: Decimal = Field(ge=0)

class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: int | None = None
    price: Decimal | None = Field(default=None, gt=0)
    cost_price: Decimal | None = Field(default=None, ge=0)

class ProductResponse(ProductCreate):
    id: int
    status: str
