def test_idempotency_key_header(client):
    # Customer setup
    client.post("/api/auth/register", json={
        "email": "idemp_cust@example.com", "full_name": "Idemp Cust", "password": "password123", "role": "customer"
    })
    cust_token = client.post("/api/auth/login", json={"email": "idemp_cust@example.com", "password": "password123"}).json()["access_token"]

    # Admin setup
    client.post("/api/auth/register", json={
        "email": "idemp_admin@example.com", "full_name": "Idemp Admin", "password": "password123", "role": "admin"
    })
    admin_token = client.post("/api/auth/login", json={"email": "idemp_admin@example.com", "password": "password123"}).json()["access_token"]

    p = client.post("/api/products", headers={"Authorization": f"Bearer {admin_token}"},
        json={"sku": "IDEMP-1", "name": "Idempotent Item", "price": 100.00, "cost_price": 50.00}).json()

    w = client.post("/api/warehouses", headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Idemp WH", "location": "Miami", "capacity": 5000}).json()

    client.post("/api/inventory/adjust", headers={"Authorization": f"Bearer {admin_token}"},
        json={"product_id": p["id"], "warehouse_id": w["id"], "quantity": 100, "reason": "Stock"})

    key = "unique-idempotency-key-xyz-123"

    # First order creation request with Idempotency-Key
    r1 = client.post("/api/orders",
        headers={"Authorization": f"Bearer {cust_token}", "Idempotency-Key": key},
        json={"warehouse_id": w["id"], "items": [{"product_id": p["id"], "quantity": 5}]}
    )
    assert r1.status_code == 201
    order1 = r1.json()

    # Retry exact same request with SAME Idempotency-Key
    r2 = client.post("/api/orders",
        headers={"Authorization": f"Bearer {cust_token}", "Idempotency-Key": key},
        json={"warehouse_id": w["id"], "items": [{"product_id": p["id"], "quantity": 5}]}
    )
    assert r2.status_code == 201
    order2 = r2.json()

    # Must return exact same order number without duplicating inventory reservation
    assert order1["id"] == order2["id"]
    assert order1["order_number"] == order2["order_number"]

    # Verify inventory was reserved ONLY ONCE (95 remaining available, not 90)
    inv = client.get(f"/api/inventory?warehouse_id={w['id']}", headers={"Authorization": f"Bearer {admin_token}"}).json()[0]
    assert inv["available_quantity"] == 95
    assert inv["reserved_quantity"] == 5
