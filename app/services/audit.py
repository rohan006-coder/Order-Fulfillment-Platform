from sqlalchemy.orm import Session
from app.models.entities import AuditLog

def audit(db: Session, user_id, action, entity, entity_id=None, ip_address=None, metadata=None):
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=str(entity_id) if entity_id else None,
                    ip_address=ip_address, metadata_json=metadata or {}))
