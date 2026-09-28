def get_admin_token(client):
    client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "full_name": "Admin User",
        "password": "password123",
        "role": "admin"
    })
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "password123"})
    return r.json()["access_token"]

def get_customer_token(client):
    client.post("/api/auth/register", json={
        "email": "cust_prod@example.com",
        "full_name": "Cust User",
        "password": "password123",
        "role": "customer"
    })
    r = client.post("/api/auth/login", json={"email": "cust_prod@example.com", "password": "password123"})
    return r.json()["access_token"]

def test_product_crud_and_permissions(client):
    admin_token = get_admin_token(client)
    cust_token = get_customer_token(client)

    # Non-admin cannot create product
    r = client.post("/api/products",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"sku": "PROD-100", "name": "Test Laptop", "price": 999.99, "cost_price": 700.00}
    )
    assert r.status_code == 403

    # Admin creates product
    r = client.post("/api/products",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sku": "PROD-100", "name": "Test Laptop", "price": 999.99, "cost_price": 700.00}
    )
    assert r.status_code == 201
    prod_id = r.json()["id"]
    assert r.json()["sku"] == "PROD-100"

    # Duplicate SKU fails
    r = client.post("/api/products",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sku": "PROD-100", "name": "Duplicate Laptop", "price": 888.00, "cost_price": 500.00}
    )
    assert r.status_code == 409

    # List products
    r = client.get("/api/products", headers={"Authorization": f"Bearer {cust_token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Deactivate product
    r = client.post(f"/api/products/{prod_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200

    # Get deactivated product
    r = client.get(f"/api/products/{prod_id}", headers={"Authorization": f"Bearer {cust_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"
