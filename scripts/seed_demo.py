import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models.entities import *
from app.core.security import hash_password

db=SessionLocal()
try:
    admin=User(email="admin@example.com",full_name="System Admin",password_hash=hash_password("Admin@12345"),role=UserRole.ADMIN)
    customer=User(email="customer@example.com",full_name="Demo Customer",password_hash=hash_password("Customer@12345"),role=UserRole.CUSTOMER)
    agent=User(email="agent@example.com",full_name="Fulfillment Agent",password_hash=hash_password("Agent@12345"),role=UserRole.FULFILLMENT_AGENT)
    warehouse=Warehouse(name="Hyderabad Central",location="Hyderabad",capacity=10000)
    product=Product(sku="SKU-1001",name="Demo Product",description="Demo item",price=499,cost_price=250)
    db.add_all([admin,customer,agent,warehouse,product]); db.commit()
    db.add(WarehouseUser(warehouse_id=warehouse.id,user_id=agent.id))
    db.add(Inventory(product_id=product.id,warehouse_id=warehouse.id,available_quantity=100,reserved_quantity=0,damaged_quantity=0,reorder_level=10))
    db.commit()
    print("Seed complete.")
finally:
    db.close()
