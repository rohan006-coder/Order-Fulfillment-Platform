from pydantic import BaseModel, Field

class WarehouseCreate(BaseModel):
    name: str
    location: str
    capacity: int = Field(gt=0)

class WarehouseUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    capacity: int | None = Field(default=None, gt=0)

class WarehouseResponse(WarehouseCreate):
    id: int
    status: str
