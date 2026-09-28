from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import require_roles, get_current_user, require_warehouse_access
from app.models.entities import Warehouse, WarehouseUser, User, UserRole, Status
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate, WarehouseResponse
from app.schemas.auth import UserResponse
from app.schemas.common import MessageResponse
from app.services.audit import audit

router = APIRouter(prefix="/api/warehouses", tags=["Warehouses"])

@router.post("", response_model=WarehouseResponse, status_code=201)
def create(payload: WarehouseCreate, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    w = Warehouse(**payload.model_dump())
    db.add(w)
    db.commit()
    db.refresh(w)
    audit(db, user.id, "WAREHOUSE_CREATED", "warehouse", w.id, metadata=payload.model_dump())
    db.commit()
    return w

@router.get("", response_model=list[WarehouseResponse])
def list_(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == UserRole.ADMIN:
        return db.query(Warehouse).all()
    # For Warehouse Managers / Agents, return warehouses they belong to
    ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]
    return db.query(Warehouse).filter(Warehouse.id.in_(ids)).all()

@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get(warehouse_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_warehouse_access(db, user, warehouse_id)
    w = db.get(Warehouse, warehouse_id)
    if not w:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Warehouse not found"})
    return w

@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
def update(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    require_warehouse_access(db, user, warehouse_id)
    w = db.get(Warehouse, warehouse_id)
    if not w:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Warehouse not found"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    audit(db, user.id, "WAREHOUSE_UPDATED", "warehouse", w.id, metadata=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(w)
    return w

@router.post("/{warehouse_id}/activate", response_model=MessageResponse)
def activate(warehouse_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    w = db.get(Warehouse, warehouse_id)
    if not w:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Warehouse not found"})
    w.status = Status.ACTIVE
    audit(db, user.id, "WAREHOUSE_ACTIVATED", "warehouse", w.id)
    db.commit()
    return {"success": True, "message": "Warehouse activated"}

@router.post("/{warehouse_id}/deactivate", response_model=MessageResponse)
def deactivate(warehouse_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    w = db.get(Warehouse, warehouse_id)
    if not w:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Warehouse not found"})
    w.status = Status.INACTIVE
    audit(db, user.id, "WAREHOUSE_DEACTIVATED", "warehouse", w.id)
    db.commit()
    return {"success": True, "message": "Warehouse deactivated"}

@router.post("/{warehouse_id}/users", response_model=MessageResponse)
def assign_user_to_warehouse(
    warehouse_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    require_warehouse_access(db, user, warehouse_id)
    w = db.get(Warehouse, warehouse_id)
    target = db.get(User, target_user_id)
    if not w or not target:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Warehouse or user not found"})
    existing = db.query(WarehouseUser).filter_by(warehouse_id=warehouse_id, user_id=target_user_id).first()
    if not existing:
        db.add(WarehouseUser(warehouse_id=warehouse_id, user_id=target_user_id))
        audit(db, user.id, "USER_ASSIGNED_TO_WAREHOUSE", "warehouse", warehouse_id, metadata={"user_id": target_user_id})
        db.commit()
    return {"success": True, "message": f"User {target_user_id} assigned to warehouse {warehouse_id}"}

@router.get("/{warehouse_id}/users", response_model=list[UserResponse])
def list_warehouse_users(
    warehouse_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    require_warehouse_access(db, user, warehouse_id)
    wu = db.query(WarehouseUser).filter_by(warehouse_id=warehouse_id).all()
    uids = [x.user_id for x in wu]
    return db.query(User).filter(User.id.in_(uids)).all()

@router.delete("/{warehouse_id}/users/{target_user_id}", response_model=MessageResponse)
def remove_user_from_warehouse(
    warehouse_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    require_warehouse_access(db, user, warehouse_id)
    wu = db.query(WarehouseUser).filter_by(warehouse_id=warehouse_id, user_id=target_user_id).first()
    if wu:
        db.delete(wu)
        audit(db, user.id, "USER_REMOVED_FROM_WAREHOUSE", "warehouse", warehouse_id, metadata={"user_id": target_user_id})
        db.commit()
    return {"success": True, "message": "User removed from warehouse"}
