import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.audit_log import AuditLog


router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get("")
def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "session_id": log.session_id,
            "action": log.action,
            "tool_name": log.tool_name,
            "arguments": (
                json.loads(log.arguments)
                if log.arguments
                else None
            ),
            "result": (
                json.loads(log.result)
                if log.result
                else None
            ),
            "approval_required": log.approval_required,
            "approved": log.approved,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]