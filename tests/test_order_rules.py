from app.models.entities import *
from app.core.security import hash_password
from app.services.orders import create_order, change_status
from app.schemas.orders import OrderCreate, OrderItemCreate
import pytest

def seed(db):
    u=User(email="c@example.com",full_name="C",password_hash=hash_password("password123"),role=UserRole.CUSTOMER)
    w=Warehouse(name="WH1",location="Hyderabad",capacity=1000)
    p=Product(sku="SKU1",name="P",price=100,cost_price=50,status=Status.ACTIVE)
    db.add_all([u,w,p]); db.commit()
    i=Inventory(product_id=p.id,warehouse_id=w.id,available_quantity=1,reserved_quantity=0,damaged_quantity=0,reorder_level=1)
    db.add(i); db.commit()
    return u,w,p

def test_reservation_and_insufficient(db):
    u,w,p=seed(db)
    o=create_order(db,u,OrderCreate(warehouse_id=w.id,items=[OrderItemCreate(product_id=p.id,quantity=1)]))
    db.commit()
    inv=db.query(Inventory).first()
    assert inv.available_quantity==0 and inv.reserved_quantity==1
    with pytest.raises(Exception):
        create_order(db,u,OrderCreate(warehouse_id=w.id,items=[OrderItemCreate(product_id=p.id,quantity=1)]))

def test_invalid_transition(db):
    u,w,p=seed(db)
    o=create_order(db,u,OrderCreate(warehouse_id=w.id,items=[OrderItemCreate(product_id=p.id,quantity=1)]))
    db.commit()
    with pytest.raises(Exception):
        change_status(db,o,OrderStatus.DELIVERED,u)
