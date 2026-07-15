"""BF3-1: provenance schema claim→{source_url, quote_span, observed_at}."""
from hiob_contracts.provenance import (
    ClaimProvenance,
    ProvenancedClaim,
    claim_with_provenance,
    provenance_from_dict,
    provenance_to_dict,
)


def test_claim_provenance_fields():
    p = ClaimProvenance(
        source_url="https://example.com/r/1",
        quote_span="김서림 없이 한 시간",
        observed_at="2026-07-15T00:00:00Z",
    )
    d = p.model_dump()
    assert set(d.keys()) == {"source_url", "quote_span", "observed_at"}
    assert d["source_url"].startswith("http")


def test_provenanced_claim_verified():
    c = claim_with_provenance(
        "김서림 방지 잘 됨",
        source_url="https://shop.example/p",
        quote_span="김서림 방지 잘 됨",
        observed_at="2026-07-15T00:00:00Z",
    )
    assert c.is_verified() is True
    assert c.provenance is not None
    assert c.provenance.quote_span


def test_missing_provenance_unverified_roundtrip():
    c = ProvenancedClaim(claim="근거 없는 주장")
    assert c.is_verified() is False
    assert provenance_from_dict(None) is None
    d = provenance_to_dict(c)
    assert d["claim"] == "근거 없는 주장"
    assert "provenance" not in d
