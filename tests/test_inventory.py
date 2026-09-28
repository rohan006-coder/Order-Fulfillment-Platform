def setup_inventory_env(client):
    client.post("/api/auth/register", json={
        "email": "inv_admin@example.com",
        "full_name": "Inv Admin",
        "password": "password123",
        "role": "admin"
    })
    r = client.post("/api/auth/login", json={"email": "inv_admin@example.com", "password": "password123"})
    token = r.json()["access_token"]

    p = client.post("/api/products",
        headers={"Authorization": f"Bearer {token}"},
        json={"sku": "INV-100", "name": "Inventory Widget", "price": 50.00, "cost_price": 20.00}
    ).json()

    w1 = client.post("/api/warehouses",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "WH Alpha", "location": "NYC", "capacity": 10000}
    ).json()

    w2 = client.post("/api/warehouses",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "WH Beta", "location": "LA", "capacity": 10000}
    ).json()

    return token, p["id"], w1["id"], w2["id"]

def test_inventory_adjust_transfer_transactions(client):
    token, prod_id, w1_id, w2_id = setup_inventory_env(client)

    # Adjust stock in W1 to 100
    r = client.post("/api/inventory/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": prod_id, "warehouse_id": w1_id, "quantity": 100, "reason": "Initial Purchase"}
    )
    assert r.status_code == 200
    assert r.json()["available_quantity"] == 100

    # Negative stock adjustment prevention
    r = client.post("/api/inventory/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": prod_id, "warehouse_id": w1_id, "quantity": -150, "reason": "Damage Overflow"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"

    # Transfer 30 units from W1 to W2
    r = client.post("/api/inventory/transfer",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "product_id": prod_id,
            "from_warehouse_id": w1_id,
            "to_warehouse_id": w2_id,
            "quantity": 30,
            "reason": "Rebalance stock"
        }
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Check inventory balances
    inv1 = client.get(f"/api/inventory?warehouse_id={w1_id}", headers={"Authorization": f"Bearer {token}"}).json()[0]
    inv2 = client.get(f"/api/inventory?warehouse_id={w2_id}", headers={"Authorization": f"Bearer {token}"}).json()[0]

    assert inv1["available_quantity"] == 70
    assert inv2["available_quantity"] == 30

    # List immutable transaction records
    r = client.get("/api/inventory/transactions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    txs = r.json()
    assert len(txs) >= 3 # 1 adjust + 2 transfer (OUT & IN)
