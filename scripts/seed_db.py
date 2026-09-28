import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.db import engine, Base, SessionLocal
from app.models.entities import *
from app.core.security import hash_password

def seed():
    print("Re-creating clean database schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Users
        print("Seeding Users...")
        admin = User(email="admin@platform.com", full_name="System Admin", password_hash=hash_password("Admin@123"), role=UserRole.ADMIN)
        manager = User(email="manager@platform.com", full_name="WH Manager Bob", password_hash=hash_password("Manager@123"), role=UserRole.WAREHOUSE_MANAGER)
        agent = User(email="agent@platform.com", full_name="Fulfillment Agent Charlie", password_hash=hash_password("Agent@123"), role=UserRole.FULFILLMENT_AGENT)
        customer = User(email="customer@platform.com", full_name="Alice Customer", password_hash=hash_password("Customer@123"), role=UserRole.CUSTOMER)
        
        db.add_all([admin, manager, agent, customer])
        db.commit()
        db.refresh(admin)
        db.refresh(manager)
        db.refresh(agent)
        db.refresh(customer)

        # 2. Warehouses
        print("Seeding Warehouses...")
        w1 = Warehouse(name="East Coast Fulfillment Center", location="Newark, NJ", capacity=100000, status=Status.ACTIVE)
        w2 = Warehouse(name="West Coast Logistics Hub", location="Oakland, CA", capacity=80000, status=Status.ACTIVE)
        db.add_all([w1, w2])
        db.commit()
        db.refresh(w1)
        db.refresh(w2)

        # 3. Warehouse Assignments
        db.add_all([
            WarehouseUser(warehouse_id=w1.id, user_id=manager.id),
            WarehouseUser(warehouse_id=w1.id, user_id=agent.id),
            WarehouseUser(warehouse_id=w2.id, user_id=manager.id)
        ])
        db.commit()

        # 4. Products
        print("Seeding Products...")
        p1 = Product(sku="PROD-LAPTOP-01", name="ProBook 15 Inch Laptop", description="High performance developer laptop", price=1299.99, cost_price=900.00, status=Status.ACTIVE)
        p2 = Product(sku="PROD-PHONE-02", name="SmartPhone Ultra X", description="Flagship 5G smartphone", price=899.99, cost_price=600.00, status=Status.ACTIVE)
        p3 = Product(sku="PROD-HEADSET-03", name="Wireless Noise Cancelling Headphones", description="Premium audio headset", price=199.99, cost_price=110.00, status=Status.ACTIVE)
        db.add_all([p1, p2, p3])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        db.refresh(p3)

        # 5. Inventory
        print("Seeding Inventory...")
        inv1 = Inventory(product_id=p1.id, warehouse_id=w1.id, available_quantity=50, reserved_quantity=0, damaged_quantity=0, reorder_level=10)
        inv2 = Inventory(product_id=p2.id, warehouse_id=w1.id, available_quantity=100, reserved_quantity=0, damaged_quantity=0, reorder_level=15)
        inv3 = Inventory(product_id=p3.id, warehouse_id=w2.id, available_quantity=30, reserved_quantity=0, damaged_quantity=0, reorder_level=5)
        db.add_all([inv1, inv2, inv3])
        db.commit()

        print("Database seeding completed successfully!")
        print("\nCreated Test Credentials:")
        print("  - Admin: admin@platform.com / Admin@123")
        print("  - Warehouse Manager: manager@platform.com / Manager@123")
        print("  - Fulfillment Agent: agent@platform.com / Agent@123")
        print("  - Customer: customer@platform.com / Customer@123")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
