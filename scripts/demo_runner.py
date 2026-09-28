import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from app.main import app
from scripts.seed_db import seed

def run_demo():
    print("==================================================================")
    print("     ORDER FULFILLMENT & INVENTORY MANAGEMENT PLATFORM DEMO      ")
    print("==================================================================")
    
    # 1. Clean Seed Database Schema and Initial Data
    seed()
    
    client = TestClient(app)
    
    print("\n[STEP 1] Authenticating Users & Retrieving JWT Tokens")
    # Customer Login
    res = client.post("/api/auth/login", json={"email": "customer@platform.com", "password": "Customer@123"})
    assert res.status_code == 200, f"Customer login failed: {res.text}"
    cust_token = res.json()["access_token"]
    print(f" -> Customer Authenticated. JWT Access Token: {cust_token[:25]}...")
    
    # Admin Login
    res = client.post("/api/auth/login", json={"email": "admin@platform.com", "password": "Admin@123"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    admin_token = res.json()["access_token"]
    print(f" -> Admin Authenticated. JWT Access Token: {admin_token[:25]}...")
    
    # Agent Login & Fetch Profile
    res = client.post("/api/auth/login", json={"email": "agent@platform.com", "password": "Agent@123"})
    assert res.status_code == 200, f"Agent login failed: {res.text}"
    agent_token = res.json()["access_token"]
    
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_me.status_code == 200
    agent_me = res_me.json()
    agent_id = agent_me["id"]
    print(f" -> Agent Authenticated. User ID: {agent_id} | Name: {agent_me['full_name']}")

    print("\n[STEP 2] Inspecting Initial Inventory Balances")
    res = client.get("/api/inventory", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    inv_list = res.json()
    print(" -> Current Inventory Balances Across Warehouses:")
    for inv in inv_list:
        print(f"    Product ID {inv['product_id']} | WH ID {inv['warehouse_id']} | Available: {inv['available_quantity']} | Reserved: {inv['reserved_quantity']}")

    print("\n[STEP 3] Customer Places New Order with Idempotency-Key Header")
    idemp_key = f"IDEMP-DEMO-ORD-{int(time.time())}"
    order_payload = {
        "warehouse_id": 1,
        "items": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 3}
        ]
    }
    
    res1 = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {cust_token}", "Idempotency-Key": idemp_key},
        json=order_payload
    )
    assert res1.status_code == 201, f"Order placement failed: {res1.text}"
    order1 = res1.json()
    print(f" -> Order Placed Successfully!")
    print(f"    Order ID: {order1['id']} | Number: {order1['order_number']} | Total Amount: ${order1['total_amount']} | Status: {order1['status']}")
    
    print("\n[STEP 4] Testing API Idempotency (Retrying Exact Same Request with Same Key)")
    res2 = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {cust_token}", "Idempotency-Key": idemp_key},
        json=order_payload
    )
    assert res2.status_code == 201
    order2 = res2.json()
    assert order1["id"] == order2["id"]
    assert order1["order_number"] == order2["order_number"]
    print(f" -> Retried Request Handled Idempotently!")
    print(f"    Returned Same Order Number: {order2['order_number']} | Duplicate Record Created: False (Order IDs match: True)")

    print("\n[STEP 5] Verifying Inventory Reservation under Lock")
    res = client.get("/api/inventory", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    for inv in res.json():
        if inv["warehouse_id"] == 1:
            print(f"    Product ID {inv['product_id']} | Available: {inv['available_quantity']} | Reserved: {inv['reserved_quantity']}")

    print("\n[STEP 6] Admin Assigns Order to Fulfillment Agent")
    res = client.post(f"/api/orders/{order1['id']}/assign?agent_id={agent_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    print(f" -> Order Assigned to Fulfillment Agent ID: {res.json()['assigned_agent_id']}")

    print("\n[STEP 7] Fulfillment Agent Advances State Machine Lifecycle")
    steps = [
        ("/confirm", "CONFIRMED"),
        ("/processing", "PROCESSING"),
        ("/packed", "PACKED"),
        ("/ship", "SHIPPED"),
        ("/deliver", "DELIVERED")
    ]
    for endpoint, target_state in steps:
        res = client.post(f"/api/orders/{order1['id']}{endpoint}", headers={"Authorization": f"Bearer {agent_token}"})
        assert res.status_code == 200, f"Failed state transition {endpoint}: {res.text}"
        data = res.json()
        print(f" -> Transitioned Order Status -> {data['status']}")

    print("\n[STEP 8] Attempting Invalid State Transition (Delivered -> Processing)")
    res = client.post(f"/api/orders/{order1['id']}/processing", headers={"Authorization": f"Bearer {agent_token}"})
    assert res.status_code == 409
    print(f" -> Correctly Rejected! HTTP Status: {res.status_code} | Error Code: {res.json()['error']['code']} | Message: {res.json()['error']['message']}")

    print("\n[STEP 9] Customer Initiates Return Request for Delivered Order")
    order_item_id = order1["items"][0]["id"]
    ret_payload = {
        "order_id": order1["id"],
        "reason": "Slight defect on item packaging",
        "items": [{"order_item_id": order_item_id, "quantity": 1}]
    }
    res = client.post("/api/returns", headers={"Authorization": f"Bearer {cust_token}"}, json=ret_payload)
    assert res.status_code == 201
    ret_id = res.json()["id"]
    print(f" -> Return Request Created. Return ID: {ret_id} | Status: {res.json()['status']}")

    print("\n[STEP 10] Admin Approves Return, Receives Returned Item & Issues Refund")
    r_app = client.post(f"/api/returns/{ret_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_app.status_code == 200
    
    res_rec = client.post(f"/api/returns/{ret_id}/receive", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_rec.status_code == 200
    print(f" -> Return Item Received into Warehouse Stock. Status: {res_rec.json()['status']}")
    
    res_ref = client.post(f"/api/returns/{ret_id}/refund", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_ref.status_code == 200
    print(f" -> Refund Processed to Customer. Final Return Status: {res_ref.json()['status']}")

    print("\n[STEP 11] Performing Inter-Warehouse Inventory Transfer")
    trf_res = client.post("/api/inventory/transfer", headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "product_id": 1,
            "from_warehouse_id": 1,
            "to_warehouse_id": 2,
            "quantity": 10,
            "reason": "Rebalancing regional inventory"
        }
    )
    assert trf_res.status_code == 200
    print(f" -> Inter-Warehouse Stock Transfer Succeeded! Reference ID: {trf_res.json()['reference_id']}")

    print("\n[STEP 12] Fetching Role Dashboards & Audit Log Trail")
    admin_dash = client.get("/api/dashboard/admin", headers={"Authorization": f"Bearer {admin_token}"}).json()
    print(" -> Admin Dashboard Summary Metrics:")
    print(f"    Total Orders: {admin_dash['total_orders']} | Low Stock Products: {admin_dash['low_stock_products']} | Out of Stock: {admin_dash['out_of_stock_products']}")

    audit_logs = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {admin_token}"}).json()
    print(f" -> Immutable Audit Log Recorded Actions (Total: {len(audit_logs)} entries):")
    for log in audit_logs[:5]:
        print(f"    - Action: {log['action']} | Entity: {log['entity']} | User ID: {log['user_id']} | Created At: {log['created_at']}")

    print("\n==================================================================")
    print("        ALL CHECKS PASSED: DEMO COMPLETED WITH ZERO ERRORS!       ")
    print("==================================================================")

if __name__ == "__main__":
    run_demo()
