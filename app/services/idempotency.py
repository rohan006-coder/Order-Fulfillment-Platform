import hashlib
import json
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.entities import IdempotencyKey

def process_idempotency(db: Session, request_key: str, user_id: int, endpoint: str, request_data: dict, handler):
    req_hash = hashlib.sha256(json.dumps(request_data, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    
    existing = db.query(IdempotencyKey).filter_by(key=request_key, user_id=user_id).first()
    if existing:
        return JSONResponse(status_code=existing.response_status, content=existing.response_body)

    # Execute the actual logic
    response_data, status_code = handler()
    
    # Ensure response_data is fully JSON serializable (convert Decimals, datetimes, Enums to primitives)
    serializable_body = json.loads(json.dumps(response_data, default=str))

    # Store idempotency record
    idemp_record = IdempotencyKey(
        key=request_key,
        user_id=user_id,
        endpoint=endpoint,
        request_hash=req_hash,
        response_status=status_code,
        response_body=serializable_body
    )
    db.add(idemp_record)
    db.commit()
    
    return JSONResponse(status_code=status_code, content=serializable_body)
