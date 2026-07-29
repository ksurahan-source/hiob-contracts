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
TYPECAST_VOICE_ID = "tc_62baac538f06bd484ee976bd"
TYPECAST_CUSTOM_VOICE_ID = "uc_6837dec48fc46637a9272b88"


def _voice_receipt(
    *,
    source_text: str = SOURCE_TEXT,
    voice_id: str = TYPECAST_VOICE_ID,
) -> dict:
    body = {
        "contract_version": "OrpheusVoiceReceipt.v1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "subject_id": "mom",
        "voice_id": voice_id,
        "beat_index": 0,
        "source": "sealed",
        "beat_plan_revision_digest": sha256_digest({"plan": 1}),
        "identity_binding_digest": sha256_digest({"identity": 1}),
        "voice_spec_digest": sha256_digest({"voice_spec": 1}),
        "voice_envelope_digest": sha256_digest({"voice_envelope": 1}),
        "source_text_digest": sha256_digest({"source_text": source_text}),
    }
    return {**body, "receipt_digest": sha256_digest(body)}


def _payload(
    *,
    source_text: str = SOURCE_TEXT,
    voice_id: str = TYPECAST_VOICE_ID,
) -> dict:
    receipt = _voice_receipt(source_text=source_text, voice_id=voice_id)
    body = {
        "contract_version": "OrpheusVoiceMaterializationInput.v1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "beat_index": 0,
        "source_text": source_text,
        "source_text_digest": sha256_digest({"source_text": source_text}),
        "voice_id": voice_id,
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


@pytest.mark.parametrize("voice_id", ["female1", "tc_", "tc_female1"])
def test_voice_materialization_input_rejects_non_provider_voice_ids(
    voice_id: str,
) -> None:
    payload = _payload(voice_id=voice_id)

    with pytest.raises(ValidationError, match="provider identity"):
        OrpheusVoiceMaterializationInputV1.model_validate(payload)


@pytest.mark.parametrize(
    "voice_id",
    [TYPECAST_VOICE_ID, TYPECAST_CUSTOM_VOICE_ID],
)
def test_voice_materialization_input_accepts_real_typecast_id_form(
    voice_id: str,
) -> None:
    model = OrpheusVoiceMaterializationInputV1.model_validate(
        _payload(voice_id=voice_id)
    )

    assert model.voice_id == voice_id


@pytest.mark.parametrize(
    "source_text",
    [
        "a" * 48,
        "가" * 48,
    ],
)
def test_voice_materialization_input_accepts_five_second_text_boundaries(
    source_text: str,
) -> None:
    model = OrpheusVoiceMaterializationInputV1.model_validate(
        _payload(source_text=source_text)
    )

    assert model.source_text == source_text
    assert len(model.source_text) <= 48
    assert len(model.source_text.encode("utf-8")) <= 144


def test_voice_materialization_input_rejects_over_character_limit() -> None:
    with pytest.raises(ValidationError, match="48 Unicode characters"):
        OrpheusVoiceMaterializationInputV1.model_validate(
            _payload(source_text="a" * 49)
        )


def test_voice_materialization_input_rejects_over_utf8_byte_limit() -> None:
    source_text = "😀" * 37
    assert len(source_text) <= 48
    assert len(source_text.encode("utf-8")) == 148

    with pytest.raises(ValidationError, match="144 UTF-8 bytes"):
        OrpheusVoiceMaterializationInputV1.model_validate(
            _payload(source_text=source_text)
        )


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
