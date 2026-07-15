from hiob_contracts.provenance import attach_provenance, ClaimWithProvenance


def test_provenance_schema():
    d = attach_provenance("김서림 없음", source_url="https://ex.com/r", quote_span="한 시간", observed_at="2026-07-15T00:00:00Z")
    c = ClaimWithProvenance.model_validate(d)
    assert c.is_grounded()
    assert c.provenance.source_url.startswith("https://")
