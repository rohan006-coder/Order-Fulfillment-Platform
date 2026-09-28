from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.entities import Order, OrderItem, OrderStatus, Status, UserRole, Warehouse, Product, OrderStatusHistory, PaymentStatus
from app.services.inventory import reserve, release
from app.services.audit import audit
from app.services.notifications import notify

ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.PACKED, OrderStatus.CANCELLED},
    OrderStatus.PACKED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.RETURNED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.FAILED: set(),
    OrderStatus.RETURNED: set(),
}

def change_status(db: Session, order: Order, new_status: OrderStatus, user):
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise HTTPException(
            409,
            {"code": "INVALID_ORDER_STATUS", "message": f"Transition from {order.status.value} to {new_status.value} is invalid"}
        )
    old = order.status
    order.status = new_status
    db.add(OrderStatusHistory(
        order_id=order.id,
        from_status=old.value if old else None,
        to_status=new_status.value,
        changed_by=user.id
    ))
    audit(db, user.id, "ORDER_STATUS_CHANGED", "order", order.id, metadata={"from": old.value, "to": new_status.value})
    return order

def create_order(db: Session, user, payload):
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if not warehouse or warehouse.status != Status.ACTIVE:
        raise HTTPException(400, {"code": "INVALID_WAREHOUSE", "message": "Warehouse is inactive or does not exist"})
        
    order_number = f"ORD-{uuid4().hex[:12].upper()}"
    order = Order(
        order_number=order_number,
        customer_id=user.id,
        warehouse_id=warehouse.id,
        total_amount=Decimal("0"),
        status=OrderStatus.PENDING,
        payment_status=PaymentStatus.PENDING
    )
    db.add(order)
    db.flush()

    total = Decimal("0")
    items_created = []

    for item_payload in payload.items:
        product = db.get(Product, item_payload.product_id)
        if not product or product.status != Status.ACTIVE:
            raise HTTPException(
                400,
                {"code": "PRODUCT_INACTIVE", "message": f"Product ID {item_payload.product_id} is inactive or does not exist"}
            )
        unit_price = Decimal(str(product.price))
        line_total = unit_price * item_payload.quantity
        total += line_total
        
        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_payload.quantity,
            unit_price=unit_price,
            discount=Decimal("0"),
            tax=Decimal("0"),
            total=line_total
        )
        db.add(oi)
        items_created.append(oi)
        
        # Reserve inventory safely under lock
        reserve(db, product.id, warehouse.id, item_payload.quantity, user.id, order.order_number)

    order.total_amount = total
    db.add(OrderStatusHistory(
        order_id=order.id,
        from_status=None,
        to_status=order.status.value,
        changed_by=user.id
    ))
    audit(db, user.id, "ORDER_CREATED", "order", order.id, metadata={"order_number": order.order_number, "total": str(total)})
    notify(db, user.id, "ORDER_CREATED", "Order Placed Successfully", f"Your order {order.order_number} has been created.")
    return order

def cancel_order(db: Session, order: Order, user):
    if order.customer_id != user.id and user.role not in {UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.FULFILLMENT_AGENT}:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "You are not authorized to cancel this order"})
        
    if order.status not in {OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING}:
        raise HTTPException(
            409,
            {"code": "INVALID_ORDER_STATUS", "message": f"Order in state '{order.status.value}' cannot be cancelled"}
        )
        
    items = db.query(OrderItem).filter_by(order_id=order.id).all()
    for item in items:
        release(db, item.product_id, order.warehouse_id, item.quantity, user.id, order.order_number)
        
    change_status(db, order, OrderStatus.CANCELLED, user)
    notify(db, order.customer_id, "ORDER_CANCELLED", "Order Cancelled", f"Order {order.order_number} was cancelled.")
    audit(db, user.id, "ORDER_CANCELLED", "order", order.id)
    return order
