from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import CharacterLockV1, derive_character_lock_digest_v1


def _payload() -> dict:
    lock_payload = {
        "contract_version": "CharacterLock.v1",
        "workspace_id": "3c8102c6-ec84-4530-9606-1c977b090edc",
        "brand_slug": "viewok",
        "subject_id": "lead",
        "version": 1,
        "face_id": "face-1",
        "voice_id": "voice-1",
        "source_receipt_ref": "parzifal-receipt-1",
        "source_record_version": 1,
        "source_receipt_digest": "sha256:" + "1" * 64,
    }
    return {
        **lock_payload,
        "digest": derive_character_lock_digest_v1(lock_payload),
    }


def test_character_lock_v1_accepts_one_atomic_identity_version() -> None:
    lock = CharacterLockV1.model_validate(_payload())

    assert lock.face_id == "face-1"
    assert lock.voice_id == "voice-1"
    assert lock.version == 1
    assert lock.source_record_version == 1
    assert lock.digest == (
        "sha256:6c12c8a75d6321a70a628303958484454841c4cb5a1fbe3ec83d7b66ce46bfbb"
    )


@pytest.mark.parametrize("missing", ["face_id", "voice_id", "digest"])
def test_character_lock_v1_rejects_partial_identity(missing: str) -> None:
    value = _payload()
    del value[missing]

    with pytest.raises(ValidationError):
        CharacterLockV1.model_validate(value)


@pytest.mark.parametrize(
    "field",
    ["workspace_id", "brand_slug", "face_id", "voice_id"],
)
def test_character_lock_v1_rejects_scope_or_identity_digest_drift(
    field: str,
) -> None:
    value = _payload()
    value[field] = (
        "1cc18cfb-147d-4ad7-a4a1-f28e36ac2704"
        if field == "workspace_id"
        else "changed"
    )

    with pytest.raises(ValidationError, match="digest does not match"):
        CharacterLockV1.model_validate(value)


def test_character_lock_v1_rejects_source_record_version_digest_drift() -> None:
    value = _payload()
    value["source_record_version"] = 2

    with pytest.raises(ValidationError, match="digest does not match"):
        CharacterLockV1.model_validate(value)


def test_character_lock_v1_rejects_blank_scope_unsafe_version_and_extras() -> None:
    value = _payload()
    value["brand_slug"] = " "
    value["version"] = 9_007_199_254_740_992
    value["provider"] = "seedream"

    with pytest.raises(ValidationError) as exc_info:
        CharacterLockV1.model_validate(value)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("brand_slug",) for error in errors)
    assert any(error["loc"] == ("version",) for error in errors)
    assert any(error["loc"] == ("provider",) for error in errors)


def test_character_lock_v1_accepts_canonical_text_brand_scope() -> None:
    value = _payload()
    value["brand_slug"] = "히옵-마케팅"
    value["digest"] = derive_character_lock_digest_v1(value)

    parsed = CharacterLockV1.model_validate(value)

    assert parsed.brand_slug == "히옵-마케팅"


def test_character_lock_v1_forbids_brand_id_alias() -> None:
    value = _payload()
    value["brand_id"] = "2a86daca-f5f2-4a3d-a868-f283a0a57d84"

    with pytest.raises(ValidationError) as exc_info:
        CharacterLockV1.model_validate(value)

    assert any(error["loc"] == ("brand_id",) for error in exc_info.value.errors())


def test_character_lock_v1_rejects_non_positive_version() -> None:
    value = _payload()
    value["version"] = 0

    with pytest.raises(ValidationError):
        CharacterLockV1.model_validate(value)


def test_character_lock_v1_rejects_unpaired_unicode_before_hashing() -> None:
    value = _payload()
    value["subject_id"] = "\ud800"

    with pytest.raises(ValidationError, match="valid Unicode scalar"):
        CharacterLockV1.model_validate(value)


def test_character_lock_v1_normalizes_valid_surrogate_pair_for_digest_parity() -> None:
    value = _payload()
    value.pop("digest")
    value["subject_id"] = "lead-\ud83d\ude00"

    assert derive_character_lock_digest_v1(value) == (
        "sha256:2c0083809021f8297fde1b58010d0830bd71b0e5d4ac195e73f6334a25a097be"
    )
