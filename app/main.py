import os
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api import auth, products, warehouses, inventory, orders, returns, notifications, dashboard

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Production-oriented order fulfillment and inventory management API"
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        message = detail.get("message", "An error occurred")
    else:
        code = "HTTP_ERROR"
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": code, "message": message}}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_err = errors[0] if errors else {}
    msg = f"{first_err.get('loc', [])}: {first_err.get('msg', 'Validation error')}"
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": msg}}
    )

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": str(exc)}}
    )

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(warehouses.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(returns.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
def index():
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "Welcome to Order Fulfillment Platform API. Visit /docs for OpenAPI documentation."}

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
