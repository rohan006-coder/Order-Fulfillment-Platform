from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import get_current_user, require_roles, require_warehouse_access
from app.models.entities import Inventory, InventoryTransaction, WarehouseUser, UserRole
from app.schemas.inventory import InventoryAdjust, InventoryTransfer, InventoryResponse
from app.services.inventory import adjust_stock, transfer_stock
from app.services.audit import audit
from app.services.idempotency import process_idempotency

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

@router.get("", response_model=list[InventoryResponse])
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    warehouse_id: int | None = None,
    product_id: int | None = None,
    low_stock: bool = False,
    out_of_stock: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Inventory)
    if warehouse_id:
        require_warehouse_access(db, user, warehouse_id)
        q = q.filter(Inventory.warehouse_id == warehouse_id)
    elif user.role != UserRole.ADMIN:
        ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]
        q = q.filter(Inventory.warehouse_id.in_(ids))

    if product_id:
        q = q.filter(Inventory.product_id == product_id)
    if low_stock:
        q = q.filter(Inventory.available_quantity <= Inventory.reorder_level)
    if out_of_stock:
        q = q.filter(Inventory.available_quantity == 0)

    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()

@router.get("/low-stock", response_model=list[InventoryResponse])
def get_low_stock(db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Inventory).filter(Inventory.available_quantity <= Inventory.reorder_level)
    if user.role != UserRole.ADMIN:
        ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]
        q = q.filter(Inventory.warehouse_id.in_(ids))
    return q.all()

@router.get("/transactions")
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: int | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(InventoryTransaction)
    if warehouse_id:
        require_warehouse_access(db, user, warehouse_id)
        q = q.filter(InventoryTransaction.warehouse_id == warehouse_id)
    if product_id:
        q = q.filter(InventoryTransaction.product_id == product_id)
    offset = (page - 1) * page_size
    return q.order_by(InventoryTransaction.created_at.desc()).offset(offset).limit(page_size).all()

@router.get("/{product_id}", response_model=list[InventoryResponse])
def product_inventory(product_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Inventory).filter_by(product_id=product_id).all()

@router.post("/adjust")
def adjust(
    payload: InventoryAdjust,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    require_warehouse_access(db, user, payload.warehouse_id)

    def execute():
        inv = adjust_stock(db, payload.product_id, payload.warehouse_id, payload.quantity, payload.reason, user.id)
        audit(db, user.id, "INVENTORY_ADJUSTED", "inventory", inv.id, metadata=payload.model_dump())
        db.commit()
        db.refresh(inv)
        return {
            "id": inv.id,
            "product_id": inv.product_id,
            "warehouse_id": inv.warehouse_id,
            "available_quantity": inv.available_quantity,
            "reserved_quantity": inv.reserved_quantity,
            "damaged_quantity": inv.damaged_quantity,
            "reorder_level": inv.reorder_level
        }, 200

    if idempotency_key:
        return process_idempotency(db, idempotency_key, user.id, "/api/inventory/adjust", payload.model_dump(), execute)

    res, status_code = execute()
    return res

@router.post("/transfer")
def transfer(
    payload: InventoryTransfer,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    require_warehouse_access(db, user, payload.from_warehouse_id)

    def execute():
        ref = transfer_stock(db, payload.product_id, payload.from_warehouse_id, payload.to_warehouse_id, payload.quantity, payload.reason, user.id)
        audit(db, user.id, "INVENTORY_TRANSFERRED", "inventory_transfer", ref, metadata=payload.model_dump())
        db.commit()
        return {"success": True, "message": "Inventory transferred successfully", "reference_id": ref}, 200

    if idempotency_key:
        return process_idempotency(db, idempotency_key, user.id, "/api/inventory/transfer", payload.model_dump(), execute)

    res, status_code = execute()
    return res
