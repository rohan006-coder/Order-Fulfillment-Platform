# Order Fulfillment & Inventory Management Platform

A production-grade REST API built with **FastAPI**, **PostgreSQL / SQLite**, **SQLAlchemy 2.0**, **Alembic**, and **Pydantic**. 

Designed to handle real-world backend engineering requirements: **inventory reservations**, **concurrency & deadlock-free row locking**, **idempotent write operations**, **order state machine transitions**, **warehouse-level authorization (RBAC)**, **returns workflow**, and **immutable audit logging**.

---

## Technical Stack & Features

- **Framework**: Python 3.11+ / FastAPI
- **Database**: PostgreSQL (Production) / SQLite (Local & Fast Testing)
- **ORM & Migrations**: SQLAlchemy 2.0 & Alembic
- **Authentication**: JWT Access & Refresh Tokens (with Token Rotation & Revocation)
- **Authorization**: Role-Based (`Admin`, `Warehouse Manager`, `Fulfillment Agent`, `Customer`) & Warehouse-Level Access Control
- **Concurrency Strategy**: Row-Level Locking (`SELECT FOR UPDATE`), Deterministic Lock Ordering on Inter-warehouse Transfers, Database Constraints
- **Idempotency**: Middleware/Service layer supporting `Idempotency-Key` header on write endpoints (`POST /api/orders`, `/api/inventory/adjust`, `/api/inventory/transfer`)
- **Testing**: Complete Pytest test suite with 100% passing rate across all modules.

---

## Quick Setup & Execution

### 1. Environment Setup
Create a virtual environment and install dependencies:
```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Default `.env` configuration:
```env
APP_NAME=Order Fulfillment Platform
ENVIRONMENT=development
DATABASE_URL=sqlite:///./order_fulfillment.db
SECRET_KEY=dev-secret-key-12345
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## Running the Platform

### A. Run Database Seeder
Seed initial roles, admin users, warehouses, products, and inventory:
```bash
python scripts/seed_db.py
```

### B. Run End-to-End Live Workflow Demo
Execute the comprehensive workflow demonstration script:
```bash
python scripts/demo_runner.py
```

### C. Start FastAPI Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive OpenAPI / Swagger documentation will be available at:
👉 **`http://127.0.0.1:8000/docs`**

---

## Running Automated Tests

Run the complete Pytest suite (15 tests passing across authentication, products, warehouses, inventory locking, orders, returns, idempotency, and dashboards):

```bash
python -m pytest -v
```

---

## Key Domain Concepts & Rules

### 1. Concurrency & Inventory Reservation
- When an order is created, inventory is locked (`SELECT FOR UPDATE`) and reserved (`available_quantity` decreases, `reserved_quantity` increases).
- Negative inventory is strictly prevented via DB check constraints and application checks.
- Inter-warehouse transfers acquire locks on both warehouses in sorted warehouse ID order, preventing circular-wait deadlocks.

### 2. Order State Machine
Allowed transitions:
```
PENDING ──► CONFIRMED ──► PROCESSING ──► PACKED ──► SHIPPED ──► DELIVERED ──► RETURNED
   │           │               │
   ▼           ▼               ▼
CANCELLED   CANCELLED       CANCELLED
```
- Invalid transitions (e.g., `DELIVERED` -> `PROCESSING`) are rejected with `409 INVALID_ORDER_STATUS`.
- Order cancellation automatically releases reserved inventory back to available stock.

### 3. Idempotency Handling
- Clients can send an `Idempotency-Key` header with write requests.
- Retrying with the same key returns the exact cached HTTP status code and response payload without re-executing inventory movements.

---

## Project Structure
```
order_fulfillment_platform/
├── app/
│   ├── api/             # FastAPI routers (auth, products, warehouses, inventory, orders, returns, notifications, dashboard)
│   ├── core/            # Configuration & security (JWT, Password hashing)
│   ├── db.py            # SQLAlchemy database engine & session maker
│   ├── main.py          # FastAPI application & exception handlers
│   ├── models/          # Declarative SQLAlchemy models (entities.py)
│   ├── schemas/         # Pydantic validation schemas
│   └── services/        # Business logic, inventory reservation, idempotency, audit logging
├── docs/                # Architecture, API Markdown, ER Diagrams
├── postman/             # Postman Collection JSON
├── scripts/             # Database seeder (seed_db.py) and Demo Runner (demo_runner.py)
├── tests/               # Pytest suite
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```
