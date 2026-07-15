"""BF3-1: claim provenance schema — claim → {source_url, quote_span, observed_at}.

Used by Janus BFA-13 / BF3-2 brief assembly. Pure pydantic + helpers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ClaimProvenance(BaseModel):
    """Provenance attached to one claim / evidence item."""

    model_config = {"extra": "forbid"}

    source_url: str = Field(default="", description="Grounded page URL for the claim")
    quote_span: str = Field(default="", description="Exact quote span supporting the claim")
    observed_at: str = Field(
        default="",
        description="ISO-8601 observation timestamp (UTC recommended)",
    )


class ProvenancedClaim(BaseModel):
    """A claim string plus optional provenance (missing ⇒ unverified)."""

    model_config = {"extra": "forbid"}

    claim: str = Field(min_length=0, description="Claim text")
    provenance: Optional[ClaimProvenance] = None

    def is_verified(self) -> bool:
        if self.provenance is None:
            return False
        return bool(str(self.provenance.source_url or "").strip())


def provenance_from_dict(raw: Any) -> ClaimProvenance | None:
    """Normalize raw dict/None → ClaimProvenance | None."""
    if raw is None:
        return None
    if isinstance(raw, ClaimProvenance):
        return raw
    if not isinstance(raw, dict):
        return None
    return ClaimProvenance(
        source_url=str(raw.get("source_url") or raw.get("url") or "").strip(),
        quote_span=str(raw.get("quote_span") or raw.get("quote") or raw.get("span") or "").strip()[:2000],
        observed_at=str(raw.get("observed_at") or raw.get("observed") or "").strip(),
    )


def claim_with_provenance(
    claim: str,
    *,
    source_url: str = "",
    quote_span: str = "",
    observed_at: str = "",
    provenance: Any = None,
) -> ProvenancedClaim:
    """Build ProvenancedClaim from parts or nested provenance dict."""
    prov = provenance_from_dict(provenance)
    if prov is None and (source_url or quote_span or observed_at):
        prov = ClaimProvenance(
            source_url=str(source_url or "").strip(),
            quote_span=str(quote_span or "").strip()[:2000],
            observed_at=str(observed_at or "").strip(),
        )
    return ProvenancedClaim(claim=str(claim or "").strip(), provenance=prov)


def now_observed_at() -> str:
    """UTC ISO-8601 timestamp helper for producers."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def provenance_to_dict(p: ClaimProvenance | ProvenancedClaim | None) -> dict[str, Any]:
    if p is None:
        return {}
    if isinstance(p, ProvenancedClaim):
        d: dict[str, Any] = {"claim": p.claim}
        if p.provenance is not None:
            d["provenance"] = p.provenance.model_dump()
        return d
    return p.model_dump()
