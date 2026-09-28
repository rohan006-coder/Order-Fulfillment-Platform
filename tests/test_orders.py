def setup_order_env(client):
    # Admin
    client.post("/api/auth/register", json={
        "email": "ord_admin@example.com", "full_name": "Ord Admin", "password": "password123", "role": "admin"
    })
    admin_token = client.post("/api/auth/login", json={"email": "ord_admin@example.com", "password": "password123"}).json()["access_token"]

    # Customer
    client.post("/api/auth/register", json={
        "email": "ord_cust@example.com", "full_name": "Ord Cust", "password": "password123", "role": "customer"
    })
    cust_token = client.post("/api/auth/login", json={"email": "ord_cust@example.com", "password": "password123"}).json()["access_token"]

    # Agent
    r = client.post("/api/auth/register", json={
        "email": "ord_agent@example.com", "full_name": "Ord Agent", "password": "password123", "role": "fulfillment_agent"
    })
    agent_id = r.json()["id"]
    agent_token = client.post("/api/auth/login", json={"email": "ord_agent@example.com", "password": "password123"}).json()["access_token"]

    p = client.post("/api/products", headers={"Authorization": f"Bearer {admin_token}"},
        json={"sku": "ORD-P1", "name": "Order Phone", "price": 500.00, "cost_price": 300.00}).json()

    w = client.post("/api/warehouses", headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Order WH", "location": "Chicago", "capacity": 10000}).json()

    # Assign agent to warehouse
    client.post(f"/api/warehouses/{w['id']}/users?target_user_id={agent_id}", headers={"Authorization": f"Bearer {admin_token}"})

    # Add stock
    client.post("/api/inventory/adjust", headers={"Authorization": f"Bearer {admin_token}"},
        json={"product_id": p["id"], "warehouse_id": w["id"], "quantity": 10, "reason": "Stocking"})

    return admin_token, cust_token, agent_token, agent_id, p["id"], w["id"]

def test_order_lifecycle_cancellation_and_assignment(client):
    admin_token, cust_token, agent_token, agent_id, prod_id, wh_id = setup_order_env(client)

    # Customer creates order
    r = client.post("/api/orders", headers={"Authorization": f"Bearer {cust_token}"},
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 2}]})
    assert r.status_code == 201
    order = r.json()
    order_id = order["id"]
    assert order["status"] == "pending"
    assert float(order["total_amount"]) == 1000.00

    # Verify reserved quantity
    inv = client.get(f"/api/inventory?warehouse_id={wh_id}", headers={"Authorization": f"Bearer {admin_token}"}).json()[0]
    assert inv["available_quantity"] == 8
    assert inv["reserved_quantity"] == 2

    # Admin assigns order to agent
    r = client.post(f"/api/orders/{order_id}/assign?agent_id={agent_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["assigned_agent_id"] == agent_id

    # Agent advances state machine: pending -> confirmed -> processing -> packed -> ship -> deliver
    client.post(f"/api/orders/{order_id}/confirm", headers={"Authorization": f"Bearer {agent_token}"})
    client.post(f"/api/orders/{order_id}/processing", headers={"Authorization": f"Bearer {agent_token}"})
    client.post(f"/api/orders/{order_id}/packed", headers={"Authorization": f"Bearer {agent_token}"})
    client.post(f"/api/orders/{order_id}/ship", headers={"Authorization": f"Bearer {agent_token}"})
    r = client.post(f"/api/orders/{order_id}/deliver", headers={"Authorization": f"Bearer {agent_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "delivered"

    # Test invalid backward state transition: delivered -> processing MUST FAIL
    r = client.post(f"/api/orders/{order_id}/processing", headers={"Authorization": f"Bearer {agent_token}"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_ORDER_STATUS"

def test_order_cancellation_releases_inventory(client):
    admin_token, cust_token, agent_token, agent_id, prod_id, wh_id = setup_order_env(client)

    # Customer places order for 3 items
    r = client.post("/api/orders", headers={"Authorization": f"Bearer {cust_token}"},
        json={"warehouse_id": wh_id, "items": [{"product_id": prod_id, "quantity": 3}]})
    order_id = r.json()["id"]

    # Customer cancels order
    r = client.post(f"/api/orders/{order_id}/cancel", headers={"Authorization": f"Bearer {cust_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Verify inventory released back to available stock (10 total stock restored)
    inv = client.get(f"/api/inventory?warehouse_id={wh_id}", headers={"Authorization": f"Bearer {admin_token}"}).json()[0]
    assert inv["available_quantity"] == 10
    assert inv["reserved_quantity"] == 0
