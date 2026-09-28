from sqlalchemy.orm import Session
from app.models.entities import Notification

def notify(db: Session, user_id: int, type_: str, title: str, message: str, metadata=None):
    db.add(Notification(user_id=user_id, type=type_, title=title, message=message, metadata_json=metadata or {}))
