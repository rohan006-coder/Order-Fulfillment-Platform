from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.api.deps import get_current_user, require_roles
from app.models.entities import Return, ReturnItem, ReturnStatus, Order, OrderItem, OrderStatus, PaymentStatus, Inventory, InventoryTransaction, InventoryTransactionType, UserRole
from app.schemas.returns import ReturnCreate, ReturnResponse
from app.services.audit import audit
from app.services.notifications import notify
from app.services.inventory import get_or_create_locked_inventory

router = APIRouter(prefix="/api/returns", tags=["Returns"])

def serialize_return(r: Return, db: Session):
    items = db.query(ReturnItem).filter_by(return_id=r.id).all()
    return {
        "id": r.id,
        "order_id": r.order_id,
        "customer_id": r.customer_id,
        "status": r.status,
        "reason": r.reason,
        "created_at": r.created_at,
        "items": [{"order_item_id": i.order_item_id, "quantity": i.quantity} for i in items]
    }

@router.post("", status_code=201)
def create(payload: ReturnCreate, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.CUSTOMER))):
    order = db.get(Order, payload.order_id)
    if not order or order.customer_id != user.id:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Order not found"})
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(409, {"code": "INVALID_RETURN_STATUS", "message": "Only delivered orders are eligible for return"})
        
    existing_return = db.query(Return).filter_by(order_id=order.id).filter(Return.status != ReturnStatus.REJECTED).first()
    if existing_return:
        raise HTTPException(409, {"code": "DUPLICATE_RETURN", "message": "A return request already exists for this order"})

    r = Return(order_id=order.id, customer_id=user.id, reason=payload.reason, status=ReturnStatus.REQUESTED)
    db.add(r)
    db.flush()

    for item in payload.items:
        oi = db.get(OrderItem, item.order_item_id)
        if not oi or oi.order_id != order.id:
            raise HTTPException(400, {"code": "INVALID_ORDER_ITEM", "message": f"Order item {item.order_item_id} does not belong to order"})
        if item.quantity > oi.quantity:
            raise HTTPException(400, {"code": "INVALID_RETURN_QUANTITY", "message": "Return quantity exceeds purchased quantity"})
        db.add(ReturnItem(return_id=r.id, order_item_id=oi.id, quantity=item.quantity))

    notify(db, user.id, "RETURN_REQUESTED", "Return Requested", f"Return request for order {order.order_number} received.")
    audit(db, user.id, "RETURN_CREATED", "return", r.id)
    db.commit()
    db.refresh(r)
    return serialize_return(r, db)

@router.get("")
def list_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Return)
    if user.role == UserRole.CUSTOMER:
        q = q.filter(Return.customer_id == user.id)
    if status:
        q = q.filter(Return.status == status)
    offset = (page - 1) * page_size
    returns = q.order_by(Return.created_at.desc()).offset(offset).limit(page_size).all()
    return [serialize_return(r, db) for r in returns]

@router.get("/{return_id}")
def get_return(return_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.get(Return, return_id)
    if not r:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Return not found"})
    if user.role == UserRole.CUSTOMER and r.customer_id != user.id:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Access denied"})
    return serialize_return(r, db)

@router.post("/{return_id}/approve")
def approve(return_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))):
    r = db.get(Return, return_id)
    if not r:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Return not found"})
    if r.status != ReturnStatus.REQUESTED:
        raise HTTPException(409, {"code": "INVALID_RETURN_STATUS", "message": f"Return status '{r.status.value}' cannot be approved"})
    r.status = ReturnStatus.APPROVED
    notify(db, r.customer_id, "RETURN_APPROVED", "Return Approved", f"Return #{r.id} has been approved.")
    audit(db, user.id, "RETURN_APPROVED", "return", r.id)
    db.commit()
    return serialize_return(r, db)

@router.post("/{return_id}/reject")
def reject(return_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))):
    r = db.get(Return, return_id)
    if not r:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Return not found"})
    if r.status != ReturnStatus.REQUESTED:
        raise HTTPException(409, {"code": "INVALID_RETURN_STATUS", "message": f"Return status '{r.status.value}' cannot be rejected"})
    r.status = ReturnStatus.REJECTED
    notify(db, r.customer_id, "RETURN_REJECTED", "Return Rejected", f"Return #{r.id} was rejected.")
    audit(db, user.id, "RETURN_REJECTED", "return", r.id)
    db.commit()
    return serialize_return(r, db)

@router.post("/{return_id}/receive")
def receive_returned_goods(return_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT))):
    r = db.get(Return, return_id)
    if not r:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Return not found"})
    if r.status != ReturnStatus.APPROVED:
        raise HTTPException(409, {"code": "INVALID_RETURN_STATUS", "message": f"Return status '{r.status.value}' cannot be received"})
        
    order = db.get(Order, r.order_id)
    return_items = db.query(ReturnItem).filter_by(return_id=r.id).all()
    
    for ri in return_items:
        oi = db.get(OrderItem, ri.order_item_id)
        if oi:
            inv = get_or_create_locked_inventory(db, oi.product_id, order.warehouse_id)
            inv.available_quantity += ri.quantity
            db.add(InventoryTransaction(
                product_id=oi.product_id,
                warehouse_id=order.warehouse_id,
                transaction_type=InventoryTransactionType.RETURN,
                quantity=ri.quantity,
                reference_entity="return",
                reference_id=str(r.id),
                user_id=user.id
            ))
            
    r.status = ReturnStatus.RECEIVED
    audit(db, user.id, "RETURN_RECEIVED", "return", r.id)
    db.commit()
    return serialize_return(r, db)

@router.post("/{return_id}/refund")
def process_refund(return_id: int, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))):
    r = db.get(Return, return_id)
    if not r:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Return not found"})
    if r.status not in {ReturnStatus.RECEIVED, ReturnStatus.APPROVED}:
        raise HTTPException(409, {"code": "INVALID_RETURN_STATUS", "message": f"Return status '{r.status.value}' cannot be refunded"})
        
    r.status = ReturnStatus.REFUNDED
    order = db.get(Order, r.order_id)
    if order:
        order.payment_status = PaymentStatus.REFUNDED
        order.status = OrderStatus.RETURNED
        
    notify(db, r.customer_id, "RETURN_REFUNDED", "Refund Processed", f"Refund for return #{r.id} has been processed.")
    audit(db, user.id, "RETURN_REFUNDED", "return", r.id)
    db.commit()
    return serialize_return(r, db)
