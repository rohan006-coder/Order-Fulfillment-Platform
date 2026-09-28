from pydantic import BaseModel, Field
from typing import Any

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail

class MessageResponse(BaseModel):
    success: bool = True
    message: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class Page(BaseModel):
    items: list[Any]
    page: int
    page_size: int
    total: int
