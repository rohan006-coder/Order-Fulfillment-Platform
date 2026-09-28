from pydantic import BaseModel, Field
from app.models.entities import ReturnStatus

class ReturnItemCreate(BaseModel):
    order_item_id: int
    quantity: int = Field(gt=0)

class ReturnCreate(BaseModel):
    order_id: int
    reason: str = Field(min_length=3)
    items: list[ReturnItemCreate] = Field(min_length=1)

class ReturnResponse(BaseModel):
    id: int
    order_id: int
    customer_id: int
    status: ReturnStatus
    reason: str
