def get_admin_token(client):
    client.post("/api/auth/register", json={
        "email": "wh_admin@example.com",
        "full_name": "Admin WH",
        "password": "password123",
        "role": "admin"
    })
    r = client.post("/api/auth/login", json={"email": "wh_admin@example.com", "password": "password123"})
    return r.json()["access_token"]

def test_warehouse_management_and_assignment(client):
    admin_token = get_admin_token(client)

    # Register manager user
    r = client.post("/api/auth/register", json={
        "email": "mgr1@example.com",
        "full_name": "Manager One",
        "password": "password123",
        "role": "warehouse_manager"
    })
    mgr_id = r.json()["id"]

    # Create warehouse
    r = client.post("/api/warehouses",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Central Hub", "location": "Dallas, TX", "capacity": 50000}
    )
    assert r.status_code == 201
    wh_id = r.json()["id"]

    # Assign manager to warehouse
    r = client.post(f"/api/warehouses/{wh_id}/users?target_user_id={mgr_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200

    # List warehouse users
    r = client.get(f"/api/warehouses/{wh_id}/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == mgr_id
