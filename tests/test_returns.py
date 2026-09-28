def setup_delivered_order(client):
    client.post("/api/auth/register", json={
        "email": "ret_admin@example.com", "full_name": "Ret Admin", "password": "password123", "role": "admin"
    })
    admin_token = client.post("/api/auth/login", json={"email": "ret_admin@example.com", "password": "password123"}).json()["access_token"]

    client.post("/api/auth/register", json={
        "email": "ret_cust@example.com", "full_name": "Ret Cust", "password": "password123", "role": "customer"
    })
    cust_token = client.post("/api/auth/login", json={"email": "ret_cust@example.com", "password": "password123"}).json()["access_token"]

    p = client.post("/api/products", headers={"Authorization": f"Bearer {admin_token}"},
        json={"sku": "RET-1", "name": "Returnable Shoes", "price": 120.00, "cost_price": 60.00}).json()

    w = client.post("/api/warehouses", headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Return WH", "location": "Boston", "capacity": 5000}).json()

    client.post("/api/inventory/adjust", headers={"Authorization": f"Bearer {admin_token}"},
        json={"product_id": p["id"], "warehouse_id": w["id"], "quantity": 10, "reason": "Stock"})

    order = client.post("/api/orders", headers={"Authorization": f"Bearer {cust_token}"},
        json={"warehouse_id": w["id"], "items": [{"product_id": p["id"], "quantity": 2}]}
    ).json()
    order_id = order["id"]
    order_item_id = order["items"][0]["product_id"]

    # Process order to delivered
    client.post(f"/api/orders/{order_id}/confirm", headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/orders/{order_id}/processing", headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/orders/{order_id}/packed", headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/orders/{order_id}/ship", headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/orders/{order_id}/deliver", headers={"Authorization": f"Bearer {admin_token}"})

    return admin_token, cust_token, order_id, order["items"][0]["product_id"], w["id"]

def test_returns_lifecycle(client):
    admin_token, cust_token, order_id, prod_id, wh_id = setup_delivered_order(client)

    # Customer gets order details to get order_item_id
    order_details = client.get(f"/api/orders/{order_id}", headers={"Authorization": f"Bearer {cust_token}"}).json()
    items = client.get(f"/api/orders/{order_id}", headers={"Authorization": f"Bearer {cust_token}"}).json()["items"]
    
    # Create Return Request
    r = client.post("/api/returns", headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "order_id": order_id,
            "reason": "Wrong size received",
            "items": [{"order_item_id": 1, "quantity": 2}]
        }
    )
    assert r.status_code == 201
    ret = r.json()
    ret_id = ret["id"]
    assert ret["status"] == "requested"

    # Admin Approves Return
    r = client.post(f"/api/returns/{ret_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # Admin Receives Goods & Restores Inventory
    r = client.post(f"/api/returns/{ret_id}/receive", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "received"

    # Admin Refunds Customer
    r = client.post(f"/api/returns/{ret_id}/refund", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "refunded"
