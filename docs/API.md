# Order Fulfillment Platform - REST API Documentation

## Authentication & Authorization
All protected endpoints require an `Authorization: Bearer <access_token>` header.

### Endpoints:
- `POST /api/auth/register` - Register a new user (`admin`, `warehouse_manager`, `fulfillment_agent`, `customer`).
- `POST /api/auth/login` - Authenticate user credentials and return access + refresh tokens.
- `POST /api/auth/refresh` - Refresh access token using valid refresh token (Rotates refresh token).
- `POST /api/auth/logout` - Revoke active user sessions.
- `GET /api/auth/me` - Retrieve current user profile.
- `POST /api/auth/change-password` - Change account password.

---

## Products Management
- `POST /api/products` - [Admin] Create a new product (Unique SKU enforced).
- `GET /api/products` - List products with server-side pagination (`page`, `page_size`) and filters (`status`, `category_id`, `search`).
- `GET /api/products/{id}` - Get product details.
- `PATCH /api/products/{id}` - [Admin] Update product fields.
- `POST /api/products/{id}/activate` - [Admin] Activate product.
- `POST /api/products/{id}/deactivate` - [Admin] Deactivate product.

---

## Warehouse Management
- `POST /api/warehouses` - [Admin] Create warehouse.
- `GET /api/warehouses` - List warehouses (Filtered by user's assigned warehouses for non-admins).
- `GET /api/warehouses/{id}` - Get warehouse details.
- `PATCH /api/warehouses/{id}` - [Admin/Manager] Update warehouse parameters.
- `POST /api/warehouses/{id}/activate` - [Admin] Activate warehouse.
- `POST /api/warehouses/{id}/deactivate` - [Admin] Deactivate warehouse.
- `POST /api/warehouses/{id}/users` - [Admin/Manager] Assign user/agent to warehouse.
- `GET /api/warehouses/{id}/users` - List users assigned to warehouse.
- `DELETE /api/warehouses/{id}/users/{user_id}` - [Admin/Manager] Remove user from warehouse.

---

## Inventory Management
- `GET /api/inventory` - List inventory with filters (`warehouse_id`, `product_id`, `low_stock`, `out_of_stock`).
- `GET /api/inventory/low-stock` - Retrieve items where `available_quantity <= reorder_level`.
- `GET /api/inventory/transactions` - View immutable inventory transaction log history.
- `POST /api/inventory/adjust` - Adjust inventory stock. Supports `Idempotency-Key` header.
- `POST /api/inventory/transfer` - Inter-warehouse stock transfer. Transactional with deadlock-free row locking. Supports `Idempotency-Key` header.

---

## Order Processing & Fulfillment
- `POST /api/orders` - [Customer] Place order. Reserves inventory safely under row-level lock. Supports `Idempotency-Key` header.
- `GET /api/orders` - List orders with server-side pagination and filters (`status`, `warehouse_id`, `customer_id`, `payment_status`, `min_total`, `max_total`, `start_date`, `end_date`).
- `GET /api/orders/{id}` - Get order details and item breakdown.
- `GET /api/orders/{id}/history` - Retrieve state transition audit timeline.
- `POST /api/orders/{id}/cancel` - Cancel order (Releases reserved inventory & logs `RELEASE` transaction).
- `POST /api/orders/{id}/accept` - [Agent] Accept pending order for fulfillment.
- `POST /api/orders/{id}/confirm` - Advance order status to `CONFIRMED`.
- `POST /api/orders/{id}/processing` - Advance status to `PROCESSING`.
- `POST /api/orders/{id}/packed` - Advance status to `PACKED`.
- `POST /api/orders/{id}/ship` - Advance status to `SHIPPED`.
- `POST /api/orders/{id}/deliver` - Mark order as `DELIVERED`.
- `POST /api/orders/{id}/assign` - [Admin/Manager] Assign order to active fulfillment agent.

---

## Returns Workflow
- `POST /api/returns` - [Customer] Request return for delivered order items.
- `GET /api/returns` - List return requests.
- `GET /api/returns/{id}` - Get return details.
- `POST /api/returns/{id}/approve` - [Admin/Manager] Approve return request.
- `POST /api/returns/{id}/reject` - [Admin/Manager] Reject return request.
- `POST /api/returns/{id}/receive` - [Admin/Manager/Agent] Mark goods received & restore stock (`RETURN` transaction).
- `POST /api/returns/{id}/refund` - [Admin/Manager] Issue refund for return (`REFUNDED` status).

---

## Dashboards & Audit Logs
- `GET /api/dashboard/admin` - Admin overview metrics (Orders, Revenue, Low Stock, Out of Stock).
- `GET /api/dashboard/warehouse-manager` - Warehouse manager summary (Pending fulfillment, Processing, Shipments).
- `GET /api/dashboard/customer` - Customer order and spending metrics.
- `GET /api/audit-logs` - [Admin] Immutable audit log inspection.
