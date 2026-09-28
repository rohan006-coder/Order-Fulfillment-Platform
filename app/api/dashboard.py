from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import get_current_user, require_roles, require_warehouse_access
from app.models.entities import Order, OrderStatus, PaymentStatus, Inventory, WarehouseUser, UserRole, AuditLog

router = APIRouter(tags=["Dashboard & Audit"])

@router.get("/api/dashboard/admin")
def admin_dashboard(db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN))):
    oq = db.query(Order)
    iq = db.query(Inventory)
    return {
        "total_orders": oq.count(),
        "pending_orders": oq.filter(Order.status == OrderStatus.PENDING).count(),
        "processing_orders": oq.filter(Order.status == OrderStatus.PROCESSING).count(),
        "completed_orders": oq.filter(Order.status == OrderStatus.DELIVERED).count(),
        "cancelled_orders": oq.filter(Order.status == OrderStatus.CANCELLED).count(),
        "total_revenue": float(oq.filter(Order.payment_status == PaymentStatus.PAID).with_entities(func.coalesce(func.sum(Order.total_amount), 0)).scalar()),
        "low_stock_products": iq.filter(Inventory.available_quantity <= Inventory.reorder_level).count(),
        "out_of_stock_products": iq.filter(Inventory.available_quantity == 0).count()
    }

@router.get("/api/dashboard/warehouse-manager")
def warehouse_manager_dashboard(
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    if warehouse_id:
        require_warehouse_access(db, user, warehouse_id)
        w_ids = [warehouse_id]
    else:
        if user.role == UserRole.ADMIN:
            w_ids = None
        else:
            w_ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]

    oq = db.query(Order)
    iq = db.query(Inventory)
    if w_ids is not None:
        oq = oq.filter(Order.warehouse_id.in_(w_ids))
        iq = iq.filter(Inventory.warehouse_id.in_(w_ids))

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    return {
        "warehouse_inventory": iq.count(),
        "pending_fulfillment": oq.filter(Order.status == OrderStatus.PENDING).count(),
        "processing_orders": oq.filter(Order.status == OrderStatus.PROCESSING).count(),
        "low_stock_items": iq.filter(Inventory.available_quantity <= Inventory.reorder_level).count(),
        "todays_shipments": oq.filter(Order.status == OrderStatus.SHIPPED, Order.updated_at >= today_start).count()
    }

@router.get("/api/dashboard/customer")
def customer_dashboard(db: Session = Depends(get_db), user=Depends(require_roles(UserRole.CUSTOMER))):
    oq = db.query(Order).filter(Order.customer_id == user.id)
    total = oq.count()
    completed = oq.filter(Order.status == OrderStatus.DELIVERED).count()
    cancelled = oq.filter(Order.status == OrderStatus.CANCELLED).count()
    spending = oq.with_entities(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    
    return {
        "total_orders": total,
        "active_orders": total - completed - cancelled,
        "completed_orders": completed,
        "cancelled_orders": cancelled,
        "total_spending": float(spending)
    }

@router.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == UserRole.ADMIN:
        return admin_dashboard(db, user)
    elif user.role == UserRole.WAREHOUSE_MANAGER:
        return warehouse_manager_dashboard(None, db, user)
    elif user.role == UserRole.CUSTOMER:
        return customer_dashboard(db, user)
    else:
        # Fulfillment Agent summary
        w_ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]
        oq = db.query(Order).filter(Order.warehouse_id.in_(w_ids))
        return {
            "assigned_orders": oq.filter(Order.assigned_agent_id == user.id).count(),
            "pending_orders": oq.filter(Order.status == OrderStatus.PENDING).count(),
            "processing_orders": oq.filter(Order.status == OrderStatus.PROCESSING).count()
        }

@router.get("/api/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    entity: str | None = None,
    user_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN))
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity:
        q = q.filter(AuditLog.entity == entity)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
        
    offset = (page - 1) * page_size
    return q.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()
