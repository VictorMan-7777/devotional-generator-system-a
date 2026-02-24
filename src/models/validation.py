from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ValidatorAssessment(BaseModel):
    check_id: str
    result: str          # "pass" | "fail"
    reason_code: str     # Empty string on pass; specific code on fail
    explanation: str     # Plain-language explanation; empty on pass
    evidence: Optional[str] = None  # Specific text triggering the failure


class RewriteSignal(str, Enum):
    AUTO_REWRITE = "auto_rewrite"
    HUMAN_REVIEW = "human_review"


class RewriteDecision(BaseModel):
    signal: RewriteSignal
    failed_assessments: List[ValidatorAssessment]
