import json

from app.db.database import SessionLocal
from app.models.audit_log import AuditLog


def log_action(
    session_id: str,
    action: str,
    tool_name: str | None = None,
    arguments: dict | None = None,
    result=None,
    approval_required: bool = False,
    approved: bool = False,
):
    db = SessionLocal()

    try:
        log = AuditLog(
            session_id=session_id,
            action=action,
            tool_name=tool_name,
            arguments=json.dumps(arguments) if arguments else None,
            result=json.dumps(result, default=str) if result is not None else None,
            approval_required=approval_required,
            approved=approved,
        )

        db.add(log)
        db.commit()

    finally:
        db.close()