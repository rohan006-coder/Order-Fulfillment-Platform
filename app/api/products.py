from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import get_current_user, require_roles
from app.models.entities import Product, UserRole, Status
from app.schemas.products import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.common import MessageResponse
from app.services.audit import audit

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.post("", response_model=ProductResponse, status_code=201)
def create(payload: ProductCreate, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    if db.query(Product).filter_by(sku=payload.sku).first():
        raise HTTPException(409, {"code": "DUPLICATE_SKU", "message": f"Product SKU {payload.sku} already exists"})
    p = Product(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    audit(db, user.id, "PRODUCT_CREATED", "product", p.id, metadata=payload.model_dump(mode="json"))
    db.commit()
    return p

@router.get("", response_model=list[ProductResponse])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    category_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Product)
    if status:
        q = q.filter(Product.status == status)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()

@router.get("/{product_id}", response_model=ProductResponse)
def get(product_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Product not found"})
    return p

@router.patch("/{product_id}", response_model=ProductResponse)
def update(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN))
):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Product not found"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    audit(db, user.id, "PRODUCT_UPDATED", "product", p.id, metadata=payload.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    db.refresh(p)
    return p

@router.post("/{product_id}/activate", response_model=MessageResponse)
def activate(product_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Product not found"})
    p.status = Status.ACTIVE
    audit(db, user.id, "PRODUCT_ACTIVATED", "product", p.id)
    db.commit()
    return {"success": True, "message": "Product activated"}

@router.post("/{product_id}/deactivate", response_model=MessageResponse)
def deactivate(product_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Product not found"})
    p.status = Status.INACTIVE
    audit(db, user.id, "PRODUCT_DEACTIVATED", "product", p.id)
    db.commit()
    return {"success": True, "message": "Product deactivated"}
