"""BF3-1: claim provenance schema — claim → {source_url, quote_span, observed_at}."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClaimProvenance(BaseModel):
    model_config = {"extra": "forbid"}
    source_url: str = ""
    quote_span: str = ""
    observed_at: str = ""  # ISO8601 when known


class ClaimWithProvenance(BaseModel):
    model_config = {"extra": "allow"}
    claim: str
    provenance: ClaimProvenance = Field(default_factory=ClaimProvenance)

    def is_grounded(self) -> bool:
        return bool(self.provenance.source_url and self.provenance.quote_span)


def attach_provenance(claim: str, *, source_url: str = "", quote_span: str = "", observed_at: str = "") -> dict[str, Any]:
    c = ClaimWithProvenance(
        claim=claim,
        provenance=ClaimProvenance(source_url=source_url, quote_span=quote_span, observed_at=observed_at),
    )
    return c.model_dump()
