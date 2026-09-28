from fastapi import APIRouter, Depends
from app.db import get_db
from app.api.deps import get_current_user
from app.models.entities import Notification

router=APIRouter(prefix="/api/notifications",tags=["Notifications"])

@router.get("")
def list_(db=Depends(get_db),user=Depends(get_current_user)):
    return db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()

@router.patch("/{notification_id}/read")
def read(notification_id:int,db=Depends(get_db),user=Depends(get_current_user)):
    n=db.query(Notification).filter_by(id=notification_id,user_id=user.id).first()
    if n: n.is_read=True; db.commit()
    return {"message":"Notification marked as read"}

@router.patch("/read-all")
def read_all(db=Depends(get_db),user=Depends(get_current_user)):
    db.query(Notification).filter_by(user_id=user.id,is_read=False).update({"is_read":True})
    db.commit(); return {"message":"All notifications marked as read"}
