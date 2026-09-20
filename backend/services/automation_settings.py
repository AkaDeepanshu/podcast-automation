"""Load / ensure singleton AutomationSettings row."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import AutomationSettings


def get_or_create_settings(db: Session) -> AutomationSettings:
    row = db.get(AutomationSettings, 1)
    if row is None:
        row = AutomationSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row
