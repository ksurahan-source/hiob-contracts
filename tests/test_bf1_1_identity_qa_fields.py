from hiob_contracts.identity_qa_fields import attach_identity_qa, IdentityQaFields


def test_identity_qa_roundtrip():
    raw = attach_identity_qa({"id": "p1"}, refs=["r2/key/a", "r2/key/b"], score=0.71)
    m = IdentityQaFields.model_validate(raw)
    assert m.ref_storage_keys == ["r2/key/a", "r2/key/b"]
    assert abs(m.identity_qa_score - 0.71) < 1e-9
