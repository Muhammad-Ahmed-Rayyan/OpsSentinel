from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Severity = Literal["low", "medium", "high", "critical"]


class NormalizedAlert(BaseModel):
    """Common alert format every downstream agent relies on."""

    source: str
    name: str
    summary: str
    severity: Severity
    service: Optional[str] = None
    host: Optional[str] = None
    environment: Optional[str] = None
    triggered_at: datetime