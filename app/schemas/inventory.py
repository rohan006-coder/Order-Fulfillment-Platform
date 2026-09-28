from pydantic import BaseModel, Field

class InventoryAdjust(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int
    reason: str = Field(min_length=2)

class InventoryTransfer(BaseModel):
    product_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=2)

class InventoryResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    available_quantity: int
    reserved_quantity: int
    damaged_quantity: int
    reorder_level: int
