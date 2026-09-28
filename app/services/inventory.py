from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.entities import Inventory, InventoryTransaction, InventoryTransactionType, WarehouseUser, UserRole
from app.services.notifications import notify

def get_or_create_locked_inventory(db: Session, product_id: int, warehouse_id: int):
    # Lock row to prevent race condition
    row = db.query(Inventory).filter_by(product_id=product_id, warehouse_id=warehouse_id).with_for_update().first()
    if not row:
        row = Inventory(
            product_id=product_id,
            warehouse_id=warehouse_id,
            available_quantity=0,
            reserved_quantity=0,
            damaged_quantity=0,
            reorder_level=10
        )
        db.add(row)
        db.flush()
        # Re-lock
        row = db.query(Inventory).filter_by(product_id=product_id, warehouse_id=warehouse_id).with_for_update().first()
    return row

def check_low_stock_and_notify(db: Session, inv: Inventory):
    if inv.available_quantity <= inv.reorder_level:
        managers = db.query(WarehouseUser).filter_by(warehouse_id=inv.warehouse_id).all()
        for m in managers:
            notify(
                db, m.user_id, "LOW_STOCK", "Low Stock Alert",
                f"Product ID {inv.product_id} in warehouse {inv.warehouse_id} is low on stock ({inv.available_quantity} available, reorder level is {inv.reorder_level}).",
                metadata={"product_id": inv.product_id, "warehouse_id": inv.warehouse_id, "available": inv.available_quantity}
            )

def reserve(db: Session, product_id: int, warehouse_id: int, quantity: int, user_id: int, reference_id: str):
    inv = get_or_create_locked_inventory(db, product_id, warehouse_id)
    if inv.available_quantity < quantity:
        raise HTTPException(
            409,
            {"code": "INSUFFICIENT_INVENTORY", "message": f"Insufficient inventory for product {product_id}. Requested: {quantity}, Available: {inv.available_quantity}"}
        )
    inv.available_quantity -= quantity
    inv.reserved_quantity += quantity
    
    db.add(InventoryTransaction(
        product_id=product_id,
        warehouse_id=warehouse_id,
        transaction_type=InventoryTransactionType.RESERVATION,
        quantity=quantity,
        reference_entity="order",
        reference_id=reference_id,
        user_id=user_id,
        metadata_json={"available_after": inv.available_quantity, "reserved_after": inv.reserved_quantity}
    ))
    check_low_stock_and_notify(db, inv)
    return inv

def release(db: Session, product_id: int, warehouse_id: int, quantity: int, user_id: int, reference_id: str):
    inv = get_or_create_locked_inventory(db, product_id, warehouse_id)
    if inv.reserved_quantity < quantity:
        raise HTTPException(
            409,
            {"code": "INVALID_RESERVATION", "message": f"Reserved quantity ({inv.reserved_quantity}) is lower than release quantity ({quantity})"}
        )
    inv.reserved_quantity -= quantity
    inv.available_quantity += quantity
    
    db.add(InventoryTransaction(
        product_id=product_id,
        warehouse_id=warehouse_id,
        transaction_type=InventoryTransactionType.RELEASE,
        quantity=quantity,
        reference_entity="order",
        reference_id=reference_id,
        user_id=user_id,
        metadata_json={"available_after": inv.available_quantity, "reserved_after": inv.reserved_quantity}
    ))
    return inv

def adjust_stock(db: Session, product_id: int, warehouse_id: int, quantity: int, reason: str, user_id: int):
    inv = get_or_create_locked_inventory(db, product_id, warehouse_id)
    new_qty = inv.available_quantity + quantity
    if new_qty < 0:
        raise HTTPException(
            409,
            {"code": "INSUFFICIENT_INVENTORY", "message": f"Adjustment of {quantity} would result in negative inventory ({new_qty})"}
        )
    prev_qty = inv.available_quantity
    inv.available_quantity = new_qty
    
    db.add(InventoryTransaction(
        product_id=product_id,
        warehouse_id=warehouse_id,
        transaction_type=InventoryTransactionType.ADJUSTMENT,
        quantity=quantity,
        reference_entity="inventory_adjustment",
        reference_id=None,
        user_id=user_id,
        metadata_json={"reason": reason, "previous_quantity": prev_qty, "new_quantity": new_qty}
    ))
    check_low_stock_and_notify(db, inv)
    return inv

def transfer_stock(db: Session, product_id: int, from_warehouse_id: int, to_warehouse_id: int, quantity: int, reason: str, user_id: int):
    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(400, {"code": "INVALID_INVENTORY_TRANSFER", "message": "Source and destination warehouses must differ"})
        
    # Lock in deterministic order to prevent deadlocks
    w1, w2 = sorted([from_warehouse_id, to_warehouse_id])
    inv1 = get_or_create_locked_inventory(db, product_id, w1)
    inv2 = get_or_create_locked_inventory(db, product_id, w2)
    
    src = inv1 if inv1.warehouse_id == from_warehouse_id else inv2
    dst = inv2 if src is inv1 else inv1
    
    if src.available_quantity < quantity:
        raise HTTPException(
            409,
            {"code": "INSUFFICIENT_INVENTORY", "message": f"Source warehouse has insufficient inventory. Requested: {quantity}, Available: {src.available_quantity}"}
        )
        
    src.available_quantity -= quantity
    dst.available_quantity += quantity
    ref = f"TRF-{from_warehouse_id}-TO-{to_warehouse_id}-{product_id}"
    
    db.add_all([
        InventoryTransaction(
            product_id=product_id, warehouse_id=from_warehouse_id,
            transaction_type=InventoryTransactionType.TRANSFER_OUT, quantity=quantity,
            reference_entity="inventory_transfer", reference_id=ref, user_id=user_id,
            metadata_json={"reason": reason, "destination_warehouse_id": to_warehouse_id}
        ),
        InventoryTransaction(
            product_id=product_id, warehouse_id=to_warehouse_id,
            transaction_type=InventoryTransactionType.TRANSFER_IN, quantity=quantity,
            reference_entity="inventory_transfer", reference_id=ref, user_id=user_id,
            metadata_json={"reason": reason, "source_warehouse_id": from_warehouse_id}
        )
    ])
    check_low_stock_and_notify(db, src)
    return ref
