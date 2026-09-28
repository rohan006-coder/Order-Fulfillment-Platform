def test_dashboards_and_audit_logs(client):
    # Admin
    client.post("/api/auth/register", json={
        "email": "dash_admin@example.com", "full_name": "Dash Admin", "password": "password123", "role": "admin"
    })
    admin_token = client.post("/api/auth/login", json={"email": "dash_admin@example.com", "password": "password123"}).json()["access_token"]

    # Customer
    client.post("/api/auth/register", json={
        "email": "dash_cust@example.com", "full_name": "Dash Cust", "password": "password123", "role": "customer"
    })
    cust_token = client.post("/api/auth/login", json={"email": "dash_cust@example.com", "password": "password123"}).json()["access_token"]

    # Admin dashboard
    r = client.get("/api/dashboard/admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert "total_orders" in r.json()
    assert "low_stock_products" in r.json()

    # Customer dashboard
    r = client.get("/api/dashboard/customer", headers={"Authorization": f"Bearer {cust_token}"})
    assert r.status_code == 200
    assert "total_spending" in r.json()

    # Audit logs
    r = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 2
