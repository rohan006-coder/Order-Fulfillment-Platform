def test_register_login_me(client):
    r = client.post("/api/auth/register", json={
        "email": "customer1@example.com",
        "full_name": "Alice Customer",
        "password": "password123",
        "role": "customer"
    })
    assert r.status_code == 201
    assert r.json()["email"] == "customer1@example.com"

    r = client.post("/api/auth/login", json={
        "email": "customer1@example.com",
        "password": "password123"
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    refresh = r.json()["refresh_token"]
    assert token and refresh

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Alice Customer"

def test_duplicate_email_registration(client):
    client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "full_name": "Dup User",
        "password": "password123"
    })
    r = client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "full_name": "Dup User 2",
        "password": "password123"
    })
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_EMAIL"

def test_bad_login(client):
    client.post("/api/auth/register", json={
        "email": "b@example.com",
        "full_name": "Bob",
        "password": "password123"
    })
    r = client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrongpassword"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

def test_refresh_token_flow(client):
    client.post("/api/auth/register", json={
        "email": "ref@example.com",
        "full_name": "Refresh User",
        "password": "password123"
    })
    r = client.post("/api/auth/login", json={"email": "ref@example.com", "password": "password123"})
    refresh_token = r.json()["refresh_token"]

    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()

def test_change_password(client):
    client.post("/api/auth/register", json={
        "email": "change@example.com",
        "full_name": "Change Pass",
        "password": "oldpassword123"
    })
    r = client.post("/api/auth/login", json={"email": "change@example.com", "password": "oldpassword123"})
    token = r.json()["access_token"]

    r = client.post("/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "oldpassword123", "new_password": "newpassword123"}
    )
    assert r.status_code == 200

    r = client.post("/api/auth/login", json={"email": "change@example.com", "password": "newpassword123"})
    assert r.status_code == 200
