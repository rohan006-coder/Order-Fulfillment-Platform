from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.entities import User, RefreshToken
from app.schemas.auth import RegisterRequest, LoginRequest, ChangePasswordRequest, UserResponse
from app.schemas.common import TokenResponse, MessageResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.api.deps import get_current_user
from app.services.audit import audit

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, req: Request, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(409, {"code": "DUPLICATE_EMAIL", "message": "Email already registered"})
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, user.id, "USER_REGISTERED", "user", user.id, ip_address=req.client.host if req.client else None)
    db.commit()
    return user

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, req: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email).first()
    ip = req.client.host if req.client else None
    
    if not user or not verify_password(payload.password, user.password_hash):
        audit(db, None, "LOGIN_FAILED", "user", None, ip_address=ip, metadata={"email": payload.email})
        db.commit()
        raise HTTPException(401, {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"})
        
    if not user.is_active:
        audit(db, user.id, "LOGIN_INACTIVE_ATTEMPT", "user", user.id, ip_address=ip)
        db.commit()
        raise HTTPException(401, {"code": "INACTIVE_USER", "message": "User is inactive"})
        
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_password(refresh),
        expires_at=datetime.now(timezone.utc)
    ))
    audit(db, user.id, "LOGIN_SUCCESS", "user", user.id, ip_address=ip)
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("refresh_token")
    if not token:
        raise HTTPException(400, {"code": "INVALID_REFRESH_TOKEN", "message": "refresh_token is required"})
    try:
        data = decode_token(token)
        if data.get("type") != "refresh":
            raise ValueError
        user = db.get(User, int(data["sub"]))
    except Exception:
        raise HTTPException(401, {"code": "INVALID_REFRESH_TOKEN", "message": "Invalid refresh token"})
        
    if not user or not user.is_active:
        raise HTTPException(401, {"code": "INACTIVE_USER", "message": "User is inactive"})
        
    tokens = {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer"
    }
    for row in db.query(RefreshToken).filter_by(user_id=user.id, revoked_at=None).all():
        row.revoked_at = datetime.now(timezone.utc)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_password(tokens["refresh_token"]), expires_at=datetime.now(timezone.utc)))
    db.commit()
    return tokens

@router.post("/logout", response_model=MessageResponse)
def logout(user=Depends(get_current_user), db: Session = Depends(get_db)):
    for row in db.query(RefreshToken).filter_by(user_id=user.id, revoked_at=None).all():
        row.revoked_at = datetime.now(timezone.utc)
    audit(db, user.id, "LOGOUT", "user", user.id)
    db.commit()
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    return user

@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, {"code": "INVALID_PASSWORD", "message": "Current password is incorrect"})
    user.password_hash = hash_password(payload.new_password)
    audit(db, user.id, "CHANGE_PASSWORD", "user", user.id)
    db.commit()
    return {"success": True, "message": "Password changed successfully"}
