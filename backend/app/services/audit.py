import uuid
from typing import Any

from sqlmodel import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> None:
    """Add an audit entry to the current transaction. The caller commits.
    Never pass passwords, tokens, or personal data that is not needed."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
        )
    )
