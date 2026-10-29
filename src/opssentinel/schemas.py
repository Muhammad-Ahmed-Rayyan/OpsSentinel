from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

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


class Hypothesis(BaseModel):
    cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class RemediationProposal(BaseModel):
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str


class HypothesisReport(BaseModel):
    """Validated shape of the LLM's answer.

    Alternatives are kept as raw items and validated one by one by the agent,
    so one bad alternative is dropped instead of invalidating the whole answer.
    """

    hypotheses: list[Hypothesis] = Field(min_length=1)
    proposed_action: RemediationProposal
    alternatives: list[Any] = Field(default_factory=list)