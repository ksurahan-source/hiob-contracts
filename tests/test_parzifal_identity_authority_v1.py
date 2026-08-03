"""Typed durable Parzifal identity authority boundary for the JKPA chain."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ParzifalIdentityAuthorityMaterialV1,
    ParzifalIdentityAuthorityRecordV1,
    ParzifalIdentityRecordRefV1,
    derive_character_identity_binding_digest_v1,
    derive_parzifal_identity_authority_material_payload_digest_v1,
    derive_parzifal_identity_authority_record_digest_v1,
    sha256_digest,
)


def _record_body() -> dict:
    return {
        "id": "parzifal-identity-1",
        "version": 4,
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "status": "sealed",
        "emitted_at": "2026-07-26T01:02:03+00:00",
        "identity_lock": {
            "identity_source": "parzifal",
            "cast_status": "sealed",
        },
        "master_sheet": {
            "identity": {"name": "수영하는 엄마"},
            "characters": {
                "mom": {
                    "persona_id": "mom",
                    "display_name": "수영하는 엄마",
                    "face_id": "face-mom-1",
                }
            },
        },
        "cast_sheets": {
            "status": "sealed",
            "by_id": {
                "mom": {
                    "kind": "lead_link",
                    "links_to": "parzifal_master_sheet",
                    "persona_id": "mom",
                    "role": "lead",
                    "on_screen": True,
                    "voice_id": "voice-mom-1",
                }
            },
        },
    }


def _record() -> dict:
    body = _record_body()
    return {
        **body,
        "digest": derive_parzifal_identity_authority_record_digest_v1(body),
    }


def _sealed_payload() -> dict:
    return {
        "identity_lock_digest": sha256_digest({"identity_lock": "mom"}),
        "cast_sheet_digest": sha256_digest({"cast_sheet": "mom"}),
        "speakers": [
            {
                "role": "lead",
                "subject_id": "mom",
                "display_name": "수영하는 엄마",
                "face_id": "face-mom-1",
                "voice_id": "voice-mom-1",
                "identity_binding_digest": (
                    derive_character_identity_binding_digest_v1(
                        subject_id="mom",
                        face_id="face-mom-1",
                        voice_id="voice-mom-1",
                    )
                ),
            }
        ],
    }


def _material() -> dict:
    sealed_payload = _sealed_payload()
    return {
        "artifact_type": "identity_lock",
        "artifact_digest": sealed_payload["identity_lock_digest"],
        "payload_digest": (
            derive_parzifal_identity_authority_material_payload_digest_v1(
                sealed_payload
            )
        ),
        "receipt_id": "parzifal:identity_lock:receipt-1",
        "sealed_payload": sealed_payload,
    }


def test_identity_record_ref_is_exact_immutable_and_python_ts_digest_stable() -> None:
    record = _record()
    ref = ParzifalIdentityRecordRefV1.model_validate(
        {key: record[key] for key in ("id", "version", "digest")}
    )
    parsed = ParzifalIdentityAuthorityRecordV1.model_validate(record)

    assert ref.model_dump(mode="json") == {
        "id": "parzifal-identity-1",
        "version": 4,
        "digest": "sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3",
    }
    assert parsed.digest == ref.digest
    assert parsed.digest == (
        "sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3"
    )
    with pytest.raises(TypeError):
        parsed.identity_lock["cast_status"] = "draft"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"version": True}),
        lambda value: value.update({"digest": "sha256:" + "A" * 64}),
        lambda value: value.update({"record_id": "alias-is-forbidden"}),
        lambda value: value["master_sheet"].update({"provider": float("inf")}),
    ],
)
def test_identity_record_ref_and_record_reject_malformed_or_extra_authority(
    mutate,
) -> None:
    value = _record()
    mutate(value)

    with pytest.raises((ValidationError, ValueError)):
        ParzifalIdentityAuthorityRecordV1.model_validate(value)


def test_identity_record_rejects_document_or_scope_drift_under_old_digest() -> None:
    value = _record()
    value["cast_sheets"]["by_id"]["mom"]["voice_id"] = "voice-mom-2"

    with pytest.raises(ValidationError, match="digest"):
        ParzifalIdentityAuthorityRecordV1.model_validate(value)


def test_identity_record_rejects_noncanonical_utc_offset_timestamp() -> None:
    value = _record()
    value["emitted_at"] = "2026-07-26T01:02:03+0000"

    with pytest.raises(ValidationError, match="ISO-8601 UTC"):
        ParzifalIdentityAuthorityRecordV1.model_validate(value)


def test_identity_record_preserves_python_canonical_bom_text_for_ts_parity() -> None:
    body = _record_body()
    body["id"] = "\ufeffparzifal-identity-1"
    record = {
        **body,
        "digest": derive_parzifal_identity_authority_record_digest_v1(body),
    }

    parsed = ParzifalIdentityAuthorityRecordV1.model_validate(record)

    assert parsed.id == "\ufeffparzifal-identity-1"
    assert parsed.digest == (
        "sha256:4c1f4cb807f8228105dbccab90a87af9742f2b26eb7f5d9d37d92c5245b1aa06"
    )


def test_identity_record_digest_rejects_year_zero_before_hashing() -> None:
    value = _record_body()
    value["emitted_at"] = "0000-01-01T00:00:00+00:00"

    with pytest.raises(ValueError, match="ISO-8601 UTC"):
        derive_parzifal_identity_authority_record_digest_v1(value)


@pytest.mark.parametrize(
    ("fraction", "canonical_timestamp", "digest"),
    [
        (
            ".0",
            "2026-07-26T01:02:03+00:00",
            "sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3",
        ),
        (
            ".00",
            "2026-07-26T01:02:03+00:00",
            "sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3",
        ),
        (
            ".000000",
            "2026-07-26T01:02:03+00:00",
            "sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3",
        ),
        (
            ".1",
            "2026-07-26T01:02:03.100000+00:00",
            "sha256:10315ed874540d33dd3ab64998c480658a5e13d5e07e751aeef25de053c9224a",
        ),
        (
            ".12",
            "2026-07-26T01:02:03.120000+00:00",
            "sha256:112cbb6371b10a700db45ffbffa6944372dd8e8395ddf5e200e76b55ea037766",
        ),
        (
            ".123",
            "2026-07-26T01:02:03.123000+00:00",
            "sha256:082d7d04483c4566832e0678c77fcb8aba6190f95da9ea26d7c9bd0103938703",
        ),
        (
            ".1234",
            "2026-07-26T01:02:03.123400+00:00",
            "sha256:eae1e99ea7f84294a72482bc5c78c0f887c6414e2ee6da2f2e4acd0f487e0161",
        ),
        (
            ".12345",
            "2026-07-26T01:02:03.123450+00:00",
            "sha256:78b7987c6fccb205dd787008f9d88dcf05211eca4c3ed63da436cb2706a49e6c",
        ),
        (
            ".123456",
            "2026-07-26T01:02:03.123456+00:00",
            "sha256:7336fb5886675c0257428efdaf677356f2d94ac857018f6df9484a6cfc318a93",
        ),
    ],
)
@pytest.mark.parametrize("utc_suffix", ["Z", "+00:00"])
def test_identity_record_fractional_timestamps_have_one_python_ts_form(
    fraction: str,
    canonical_timestamp: str,
    digest: str,
    utc_suffix: str,
) -> None:
    body = _record_body()
    body["emitted_at"] = f"2026-07-26T01:02:03{fraction}{utc_suffix}"
    record = {
        **body,
        "digest": derive_parzifal_identity_authority_record_digest_v1(body),
    }

    parsed = ParzifalIdentityAuthorityRecordV1.model_validate(record)

    assert parsed.emitted_at == canonical_timestamp
    assert parsed.digest == digest


def test_identity_authority_material_is_the_exact_fully_sealed_wrapper() -> None:
    material = ParzifalIdentityAuthorityMaterialV1.model_validate(_material())

    assert set(material.model_dump(mode="json")) == {
        "artifact_type",
        "artifact_digest",
        "payload_digest",
        "receipt_id",
        "sealed_payload",
    }
    assert material.artifact_digest == material.sealed_payload.identity_lock_digest
    assert material.payload_digest == (
        "sha256:461b3934f5abcf907d65424121b431a67a36cfdad0c3916da22a5d13cd3a4571"
    )
    assert material.sealed_payload.voice_spec is None
    assert material.sealed_payload.locale == "ko"
    assert material.sealed_payload.audience_lock is None


def test_identity_authority_payload_digest_rejects_an_unsealed_speaker() -> None:
    sealed_payload = _sealed_payload()
    sealed_payload["speakers"][0].pop("face_id")
    sealed_payload["speakers"][0].pop("voice_id")
    sealed_payload["speakers"][0].pop("identity_binding_digest")

    with pytest.raises(ValueError, match="sealed_payload speakers"):
        derive_parzifal_identity_authority_material_payload_digest_v1(sealed_payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"artifact_type": "product_truth"}),
        lambda value: value.update({"artifact_digest": sha256_digest({"other": 1})}),
        lambda value: value.update({"payload_digest": sha256_digest({"other": 2})}),
        lambda value: value.update({"record_ref": {"id": "must-not-leak"}}),
        lambda value: value["sealed_payload"]["speakers"][0].pop("voice_id"),
        lambda value: value["sealed_payload"]["speakers"][0].update(
            {"identity_binding_digest": sha256_digest({"wrong": True})}
        ),
    ],
)
def test_identity_authority_material_rejects_wrapper_or_speaker_drift(mutate) -> None:
    value = deepcopy(_material())
    mutate(value)

    with pytest.raises(ValidationError):
        ParzifalIdentityAuthorityMaterialV1.model_validate(value)
