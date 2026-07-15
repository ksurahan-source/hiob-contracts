"""BF1-1: additive GenTask/SheetPanel identity QA fields (non-breaking)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class IdentityQaFields(BaseModel):
    model_config = {"extra": "allow"}
    ref_storage_keys: list[str] = Field(default_factory=list)
    identity_qa_score: Optional[float] = None


def attach_identity_qa(
    payload: dict[str, Any] | None,
    *,
    refs: list[str] | None = None,
    score: float | None = None,
) -> dict[str, Any]:
    out = dict(payload or {})
    if refs is not None:
        out["ref_storage_keys"] = [str(x) for x in refs]
    if score is not None:
        out["identity_qa_score"] = float(score)
    return out


def panel_with_identity_qa(panel: dict[str, Any], *, score: float | None = None) -> dict[str, Any]:
    return attach_identity_qa(panel, refs=[panel.get("storage_key")] if panel.get("storage_key") else [], score=score)
