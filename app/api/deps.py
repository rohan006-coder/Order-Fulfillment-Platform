from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError
from app.db import get_db
from app.core.security import decode_token
from app.models.entities import User, UserRole, WarehouseUser

def get_current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code":"UNAUTHORIZED","message":"Bearer token required"})
    try:
        payload = decode_token(authorization.split(" ", 1)[1])
        if payload.get("type") != "access":
            raise ValueError
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(status_code=401, detail={"code":"INVALID_TOKEN","message":"Invalid or expired access token"})
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code":"INACTIVE_USER","message":"User is inactive"})
    return user

def require_roles(*roles: UserRole):
    def dependency(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail={"code":"FORBIDDEN","message":"Insufficient permissions"})
        return user
    return dependency

def require_warehouse_access(db: Session, user: User, warehouse_id: int):
    if user.role == UserRole.ADMIN:
        return True
    exists = db.query(WarehouseUser).filter_by(user_id=user.id, warehouse_id=warehouse_id).first()
    if not exists:
        raise HTTPException(status_code=403, detail={"code":"WAREHOUSE_ACCESS_DENIED","message":"User is not authorized for this warehouse"})
    return True
