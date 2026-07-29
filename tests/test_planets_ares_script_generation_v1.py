from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    AresScriptGenerationInputV1,
    derive_ares_script_generation_input_digest_v1,
    derive_character_identity_binding_digest_v1,
    derive_voice_spec_digest_v1,
)


def _payload() -> dict:
    identity_digest = derive_character_identity_binding_digest_v1(
        subject_id="lead",
        face_id="face-lead-v1",
        voice_id="voice-lead-v1",
    )
    voice = {
        "contract_version": "VoiceSpec.v1",
        "subject_id": "lead",
        "rhythm": "짧고 단정하게",
        "vocabulary": ["진짜"],
        "forbidden_phrases": ["무조건"],
        "approved_examples": [
            "먼저 확인해 보세요.",
            "필요한 것만 담았습니다.",
            "지금 비교해 보세요.",
        ],
    }
    voice["voice_spec_digest"] = derive_voice_spec_digest_v1(voice)
    body = {
        "contract_version": "AresScriptGenerationInput.v1",
        "workspace_id": "00000000-0000-4000-8000-000000000001",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "script_revision_id": "00000000-0000-4000-8000-000000000003",
        "plan_revision_id": "00000000-0000-4000-8000-000000000004",
        "factory_revision": 7,
        "character_lock": {
            "persona_id": "lead",
            "face_id": "face-lead-v1",
            "voice_id": "voice-lead-v1",
            "identity_binding_digest": identity_digest,
        },
        "voice_spec": voice,
        "current_character": "차분하고 정확한 전문가",
        "conflict": "과장 없이 차이를 증명한다",
        "adjacent_beat_summaries": ["문제를 짧게 제시"],
        "memories": [
            {
                "text": "과장된 말투를 싫어함",
                "provenance": "approved_edit:rev-1",
            }
        ],
    }
    return {
        **body,
        "generation_input_digest": (
            derive_ares_script_generation_input_digest_v1(body)
        ),
    }


def test_ares_generation_output_has_one_planet_owned_namespace_and_public_export() -> None:
    assert AresScriptGenerationInputV1.__module__ == (
        "hiob_contracts.planets.ares.script_generation_v1"
    )
    assert (
        hiob_contracts.AresScriptGenerationInputV1
        is AresScriptGenerationInputV1
    )
    assert (
        "AresScriptGenerationInputV1"
        in hiob_contracts.__all__
    )


def test_ares_generation_output_is_exact_immutable_provider_input() -> None:
    parsed = AresScriptGenerationInputV1.model_validate(_payload(), strict=True)

    assert parsed.contract_version == "AresScriptGenerationInput.v1"
    assert parsed.character_lock.face_id == "face-lead-v1"
    assert parsed.voice_spec.subject_id == parsed.character_lock.persona_id
    assert parsed.adjacent_beat_summaries == ("문제를 짧게 제시",)
    assert parsed.memories[0].provenance == "approved_edit:rev-1"
    with pytest.raises(ValidationError):
        parsed.conflict = "mutated"


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("character_lock", "face_id"), "face-tampered"),
        (("voice_spec", "subject_id"), "other-subject"),
        (("current_character",), "changed"),
    ],
)
def test_ares_generation_output_rejects_authority_drift(
    path: tuple[str, ...],
    replacement: str,
) -> None:
    value = deepcopy(_payload())
    target = value
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = replacement

    with pytest.raises(ValidationError):
        AresScriptGenerationInputV1.model_validate(value, strict=True)


def test_ares_generation_output_rejects_extra_or_unbounded_context() -> None:
    extra = _payload() | {"production_plan": {"unsealed": True}}
    with pytest.raises(ValidationError):
        AresScriptGenerationInputV1.model_validate(extra, strict=True)

    too_many = _payload()
    too_many["memories"] = [
        {"text": str(index), "provenance": f"approved_edit:{index}"}
        for index in range(4)
    ]
    unsigned = dict(too_many)
    unsigned.pop("generation_input_digest")
    too_many["generation_input_digest"] = (
        derive_ares_script_generation_input_digest_v1(unsigned)
    )
    with pytest.raises(ValidationError):
        AresScriptGenerationInputV1.model_validate(too_many, strict=True)


@pytest.mark.parametrize(
    "missing",
    [
        ("adjacent_beat_summaries",),
        ("memories",),
        ("voice_spec", "contract_version"),
    ],
)
def test_ares_generation_output_never_synthesizes_missing_wire_fields(
    missing: tuple[str, ...],
) -> None:
    value = _payload()
    if len(missing) == 1:
        value[missing[0]] = []
        unsigned = dict(value)
        unsigned.pop("generation_input_digest")
        value["generation_input_digest"] = (
            derive_ares_script_generation_input_digest_v1(unsigned)
        )
    target = value
    for field in missing[:-1]:
        target = target[field]
    del target[missing[-1]]

    with pytest.raises(ValidationError):
        AresScriptGenerationInputV1.model_validate(value, strict=True)


def test_ares_generation_json_schema_describes_runtime_rejections() -> None:
    schema = AresScriptGenerationInputV1.model_json_schema()
    required = set(schema["required"])
    character = schema["$defs"]["AresCharacterIdentityProjectionV1"]
    memory = schema["$defs"]["AresProvenanceMemoryV1"]
    voice = schema["$defs"]["AresVoiceSpecProjectionV1"]

    assert {"adjacent_beat_summaries", "memories"} <= required
    for field in (
        "workspace_id",
        "run_id",
        "script_revision_id",
        "plan_revision_id",
        "current_character",
        "conflict",
    ):
        assert schema["properties"][field]["minLength"] == 1
        assert schema["properties"][field]["pattern"]
    assert schema["properties"]["generation_input_digest"]["pattern"] == (
        "^sha256:[0-9a-f]{64}$"
    )
    for field in ("persona_id", "face_id", "voice_id"):
        assert character["properties"][field]["minLength"] == 1
        assert character["properties"][field]["pattern"]
    assert character["properties"]["identity_binding_digest"]["pattern"] == (
        "^sha256:[0-9a-f]{64}$"
    )
    for field in ("text", "provenance"):
        assert memory["properties"][field]["minLength"] == 1
        assert memory["properties"][field]["pattern"]
    assert voice["properties"]["voice_spec_digest"]["pattern"] == (
        "^sha256:[0-9a-f]{64}$"
    )


def test_ares_generation_unicode_length_matches_typescript_code_points() -> None:
    value = _payload()
    value["current_character"] = "😀" * 500
    unsigned = dict(value)
    unsigned.pop("generation_input_digest")
    value["generation_input_digest"] = (
        derive_ares_script_generation_input_digest_v1(unsigned)
    )

    parsed = AresScriptGenerationInputV1.model_validate(value, strict=True)
    assert len(parsed.current_character) == 500


def test_ares_generation_rejects_unpaired_unicode_before_hashing() -> None:
    value = _payload()
    value["current_character"] = "\ud800"
    value["generation_input_digest"] = "sha256:" + "0" * 64

    unsigned = dict(value)
    unsigned.pop("generation_input_digest")
    with pytest.raises(ValueError, match="Unicode scalar"):
        derive_ares_script_generation_input_digest_v1(unsigned)
    with pytest.raises(ValidationError):
        AresScriptGenerationInputV1.model_validate(value, strict=True)


def test_ares_generation_digest_has_fixed_python_typescript_vector() -> None:
    value = _payload()
    unsigned = dict(value)
    digest = unsigned.pop("generation_input_digest")

    assert digest == derive_ares_script_generation_input_digest_v1(unsigned)
    assert digest == (
        "sha256:43b376a18dbdb3fda7035ce06bd36188"
        "dff58191a2f9cdb6edf1078a6aa21f3f"
    )
