# System Architecture & Concurrency Control

## Core Layers
1. **API Router Layer (`app/api/`)**: FastAPI path handlers validating payloads, handling HTTP status codes, and inspecting headers (e.g. `Idempotency-Key`, `Authorization`).
2. **Security & Authorization (`app/api/deps.py`)**: JWT authentication, Role-Based Access Control (RBAC), and Warehouse-Level Access Control.
3. **Domain Service Layer (`app/services/`)**: Enforces business logic, order state machine transitions, inventory calculations, notification generation, and audit logging.
4. **Data Access & ORM (`app/models/entities.py`, `app/db.py`)**: Declarative SQLAlchemy 2.0 ORM models with strict constraints, indexes, and relationships.

---

## Concurrency & Data Integrity Strategy

### 1. Row-Level Locking (`SELECT FOR UPDATE`)
To prevent over-selling and race conditions when multiple customers order the same item simultaneously:
- Inventory rows are queried using `.with_for_update()` inside database transactions.
- Prevents concurrent transactions from reading stale `available_quantity` values before reservation.
- Ensures `reserved_quantity <= available_quantity` invariant is enforced atomically.

### 2. Deadlock Avoidance in Transfers
During inter-warehouse inventory transfers (`POST /api/inventory/transfer`):
- Locks on source and destination inventory rows are acquired in **sorted warehouse ID order** (e.g., `min(w1, w2)` locked first, then `max(w1, w2)`).
- This deterministic locking sequence eliminates circular wait deadlock conditions.

### 3. Idempotency Mechanisms
- Critical write operations (`POST /api/orders`, `POST /api/inventory/adjust`, `POST /api/inventory/transfer`) accept an `Idempotency-Key` header.
- The system computes a request hash and checks the `idempotency_keys` table.
- Retried duplicate requests immediately return the cached status code and response payload without re-executing inventory movements or creating duplicate order records.

---

## Database Transactions & State Machine
- Order creation, reservation, status changes, and returns operate inside explicit database transactions.
- Invalid state transitions (e.g. `DELIVERED` -> `PROCESSING`) are caught by domain validation rules and raise HTTP 409 errors.
- Unhandled exceptions trigger an automatic transaction rollback (`db.rollback()`).
