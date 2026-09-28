from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import get_current_user, require_roles, require_warehouse_access
from app.models.entities import Order, OrderItem, OrderStatus, OrderStatusHistory, OrderAssignment, User, UserRole, WarehouseUser, PaymentStatus
from app.schemas.orders import OrderCreate, OrderResponse
from app.services.orders import create_order, cancel_order, change_status
from app.services.audit import audit
from app.services.notifications import notify
from app.services.idempotency import process_idempotency

router = APIRouter(prefix="/api/orders", tags=["Orders"])

def serialize_order(o: Order, db: Session):
    items = db.query(OrderItem).filter_by(order_id=o.id).all()
    return {
        "id": o.id,
        "order_number": o.order_number,
        "customer_id": o.customer_id,
        "warehouse_id": o.warehouse_id,
        "total_amount": o.total_amount,
        "status": o.status,
        "payment_status": o.payment_status,
        "created_at": o.created_at,
        "assigned_agent_id": o.assigned_agent_id,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount": item.discount,
                "tax": item.tax,
                "total": item.total
            } for item in items
        ]
    }

@router.post("", status_code=201)
def create(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.CUSTOMER))
):
    def execute():
        try:
            order = create_order(db, user, payload)
            db.commit()
            db.refresh(order)
            serialized = serialize_order(order, db)
            return serialized, 201
        except Exception:
            db.rollback()
            raise

    if idempotency_key:
        return process_idempotency(db, idempotency_key, user.id, "/api/orders", payload.model_dump(), execute)

    res, status_code = execute()
    return res

@router.get("")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    warehouse_id: int | None = None,
    customer_id: int | None = None,
    payment_status: str | None = None,
    min_total: Decimal | None = None,
    max_total: Decimal | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Order)
    if user.role == UserRole.CUSTOMER:
        q = q.filter(Order.customer_id == user.id)
    elif user.role != UserRole.ADMIN:
        ids = [x.warehouse_id for x in db.query(WarehouseUser).filter_by(user_id=user.id).all()]
        q = q.filter(Order.warehouse_id.in_(ids))

    if status:
        q = q.filter(Order.status == status)
    if warehouse_id:
        q = q.filter(Order.warehouse_id == warehouse_id)
    if customer_id and user.role == UserRole.ADMIN:
        q = q.filter(Order.customer_id == customer_id)
    if payment_status:
        q = q.filter(Order.payment_status == payment_status)
    if min_total is not None:
        q = q.filter(Order.total_amount >= min_total)
    if max_total is not None:
        q = q.filter(Order.total_amount <= max_total)
    if start_date:
        q = q.filter(Order.created_at >= start_date)
    if end_date:
        q = q.filter(Order.created_at <= end_date)

    sort_col = getattr(Order, sort_by, Order.created_at)
    if sort_order.lower() == "asc":
        q = q.order_by(sort_col.asc())
    else:
        q = q.order_by(sort_col.desc())

    offset = (page - 1) * page_size
    orders = q.offset(offset).limit(page_size).all()
    return [serialize_order(o, db) for o in orders]

@router.get("/{order_id}")
def get(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    if user.role == UserRole.CUSTOMER and o.customer_id != user.id:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Not your order"})
    if user.role not in {UserRole.ADMIN, UserRole.CUSTOMER}:
        require_warehouse_access(db, user, o.warehouse_id)
    return serialize_order(o, db)

@router.get("/{order_id}/history")
def get_history(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    if user.role == UserRole.CUSTOMER and o.customer_id != user.id:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Not your order"})
    if user.role not in {UserRole.ADMIN, UserRole.CUSTOMER}:
        require_warehouse_access(db, user, o.warehouse_id)
    return db.query(OrderStatusHistory).filter_by(order_id=order_id).order_by(OrderStatusHistory.created_at.asc()).all()

@router.post("/{order_id}/cancel")
def cancel(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    try:
        cancel_order(db, o, user)
        db.commit()
        db.refresh(o)
        return serialize_order(o, db)
    except Exception:
        db.rollback()
        raise

@router.post("/{order_id}/accept")
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    
    if not o.assigned_agent_id and user.role == UserRole.FULFILLMENT_AGENT:
        o.assigned_agent_id = user.id
        db.add(OrderAssignment(order_id=o.id, agent_id=user.id, assigned_by=user.id))
        audit(db, user.id, "ORDER_SELF_ASSIGNED", "order", o.id)
        
    change_status(db, o, OrderStatus.CONFIRMED, user)
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/confirm")
def confirm(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    change_status(db, o, OrderStatus.CONFIRMED, user)
    notify(db, o.customer_id, "ORDER_CONFIRMED", "Order Confirmed", f"Order {o.order_number} has been confirmed.")
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/processing")
def processing(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    change_status(db, o, OrderStatus.PROCESSING, user)
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/packed")
def packed(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    change_status(db, o, OrderStatus.PACKED, user)
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/ship")
def ship(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    change_status(db, o, OrderStatus.SHIPPED, user)
    notify(db, o.customer_id, "ORDER_SHIPPED", "Order Shipped", f"Order {o.order_number} has been shipped.")
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/deliver")
def deliver(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))
):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    change_status(db, o, OrderStatus.DELIVERED, user)
    o.payment_status = PaymentStatus.PAID
    notify(db, o.customer_id, "ORDER_DELIVERED", "Order Delivered", f"Order {o.order_number} has been delivered.")
    db.commit()
    return serialize_order(o, db)

@router.post("/{order_id}/assign")
def assign(
    order_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))
):
    o = db.get(Order, order_id)
    agent = db.get(User, agent_id)
    if not o or not agent:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order or agent not found"})
    require_warehouse_access(db, user, o.warehouse_id)
    
    if agent.role != UserRole.FULFILLMENT_AGENT or not agent.is_active:
        raise HTTPException(400, {"code": "INVALID_AGENT", "message": "Target user must be an active fulfillment agent"})
        
    require_warehouse_access(db, agent, o.warehouse_id)
    
    prev_agent = o.assigned_agent_id
    o.assigned_agent_id = agent.id
    db.add(OrderAssignment(order_id=o.id, agent_id=agent.id, assigned_by=user.id))
    
    notify(db, agent.id, "ORDER_ASSIGNED", "New Order Assigned", f"Order {o.order_number} has been assigned to you.")
    if prev_agent and prev_agent != agent.id:
        notify(db, prev_agent, "ORDER_REASSIGNED", "Order Reassigned", f"Order {o.order_number} was reassigned.")
        
    audit(db, user.id, "ORDER_ASSIGNED", "order", o.id, metadata={"assigned_agent_id": agent.id})
    db.commit()
    return serialize_order(o, db)
