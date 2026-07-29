from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from hiob_contracts.factory.digest import sha256_digest
from hiob_contracts.orpheus_voice_materialization_v1 import (
    OrpheusVoiceMaterializationInputV1,
    derive_orpheus_voice_materialization_input_digest_v1,
)


SOURCE_TEXT = "  이 목소리 그대로 갑니다.  "
SOURCE_TEXT_DIGEST = sha256_digest({"source_text": SOURCE_TEXT})


def _voice_receipt() -> dict:
    body = {
        "contract_version": "OrpheusVoiceReceipt.v1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "subject_id": "mom",
        "voice_id": "tc_sealed_character_voice",
        "beat_index": 0,
        "source": "sealed",
        "beat_plan_revision_digest": sha256_digest({"plan": 1}),
        "identity_binding_digest": sha256_digest({"identity": 1}),
        "voice_spec_digest": sha256_digest({"voice_spec": 1}),
        "voice_envelope_digest": sha256_digest({"voice_envelope": 1}),
        "source_text_digest": SOURCE_TEXT_DIGEST,
    }
    return {**body, "receipt_digest": sha256_digest(body)}


def _payload() -> dict:
    receipt = _voice_receipt()
    body = {
        "contract_version": "OrpheusVoiceMaterializationInput.v1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "beat_index": 0,
        "source_text": SOURCE_TEXT,
        "source_text_digest": SOURCE_TEXT_DIGEST,
        "voice_id": "tc_sealed_character_voice",
        "voice_receipt": receipt,
        "voice_receipt_digest": receipt["receipt_digest"],
    }
    return {
        **body,
        "input_digest": derive_orpheus_voice_materialization_input_digest_v1(
            body
        ),
    }


def test_voice_materialization_input_seals_exact_text_voice_and_receipt() -> None:
    payload = _payload()

    model = OrpheusVoiceMaterializationInputV1.model_validate(payload)

    assert model.source_text == SOURCE_TEXT
    assert model.source_text_digest == sha256_digest(
        {"source_text": SOURCE_TEXT}
    )
    assert model.voice_receipt.model_dump(mode="json") == _voice_receipt()
    assert model.voice_receipt_digest == _voice_receipt()["receipt_digest"]
    assert model.input_digest == (
        derive_orpheus_voice_materialization_input_digest_v1(payload)
    )


@pytest.mark.parametrize("source_text", ["", " ", "\n\t"])
def test_voice_materialization_input_rejects_missing_source_text(
    source_text: str,
) -> None:
    payload = _payload()
    payload["source_text"] = source_text

    with pytest.raises(ValidationError, match="blank"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


def test_voice_materialization_input_rejects_source_text_digest_drift() -> None:
    payload = _payload()
    payload["source_text"] = "다른 대본"
    payload["input_digest"] = derive_orpheus_voice_materialization_input_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="source_text_digest"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


def test_voice_materialization_input_rejects_voice_drift() -> None:
    payload = _payload()
    payload["voice_id"] = "tc_other_voice"
    payload["input_digest"] = derive_orpheus_voice_materialization_input_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="voice_id"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


def test_voice_materialization_input_rejects_persona_slot_as_voice_id() -> None:
    payload = _payload()
    receipt = payload["voice_receipt"]
    receipt["voice_id"] = "female1"
    unsigned_receipt = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_digest"
    }
    receipt["receipt_digest"] = sha256_digest(unsigned_receipt)
    payload["voice_id"] = "female1"
    payload["voice_receipt_digest"] = receipt["receipt_digest"]
    payload["input_digest"] = derive_orpheus_voice_materialization_input_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="provider identity"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


def test_voice_materialization_input_rejects_tampered_receipt() -> None:
    payload = _payload()
    payload["voice_receipt"]["beat_index"] = 1
    payload["input_digest"] = derive_orpheus_voice_materialization_input_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="receipt_digest"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


def test_voice_materialization_input_is_one_beat_and_frozen() -> None:
    payload = _payload()
    payload["beat_indices"] = [0, 1]

    with pytest.raises(ValidationError, match="extra"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)

    model = OrpheusVoiceMaterializationInputV1.model_validate(_payload())
    with pytest.raises(ValidationError):
        model.beat_index = 1
    with pytest.raises(ValidationError):
        model.voice_receipt.voice_id = "tc_other_voice"


def test_existing_voice_receipt_shape_is_not_rewritten() -> None:
    receipt = _voice_receipt()
    before = copy.deepcopy(receipt)

    model = OrpheusVoiceMaterializationInputV1.model_validate(_payload())

    assert receipt == before
    assert model.voice_receipt.model_dump(mode="json") == before
