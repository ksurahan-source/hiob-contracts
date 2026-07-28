from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresSpeakerSlotV2,
    CharacterLock,
    ElementLocks,
    derive_character_identity_binding_digest_v1,
    derive_voice_spec_digest_v1,
)


SUBJECT_ID = "mom"
FACE_ID = "face-mom-1"
VOICE_ID = "tc_voice_mom_1"
EXPECTED_DIGEST = (
    "sha256:04f2d67ea56831625cad4295b63cbf0f8995b458390a25cf7f2ad5a7439b02e3"
)


def _binding_digest() -> str:
    return derive_character_identity_binding_digest_v1(
        subject_id=SUBJECT_ID,
        face_id=FACE_ID,
        voice_id=VOICE_ID,
    )


def _voice_spec(subject_id: str = SUBJECT_ID) -> dict:
    body = {
        "contract_version": "VoiceSpec.v1",
        "subject_id": subject_id,
        "rhythm": "짧게 끊고 마지막에 한 박자 쉰다",
        "vocabulary": ["솔직히", "딱", "은근"],
        "forbidden_phrases": ["혁신적인", "여러분 안녕하세요"],
        "approved_examples": [
            "솔직히 이건 좀 놀랐어.",
            "딱 한 번만 해보면 감이 와.",
            "은근 이런 데서 차이가 나더라.",
        ],
    }
    return {
        **body,
        "voice_spec_digest": derive_voice_spec_digest_v1(body),
    }


def test_character_identity_digest_has_cross_language_vector() -> None:
    assert _binding_digest() == EXPECTED_DIGEST


def test_character_lock_roundtrip_binds_face_and_voice_in_one_digest() -> None:
    locks = ElementLocks.from_dict(
        {
            "characters": {
                SUBJECT_ID: {
                    "face_id": FACE_ID,
                    "voice_id": VOICE_ID,
                    "identity_binding_digest": _binding_digest(),
                }
            }
        }
    )

    character = locks.character(SUBJECT_ID)

    assert character == CharacterLock(
        persona_id=SUBJECT_ID,
        face_id=FACE_ID,
        voice_id=VOICE_ID,
        identity_binding_digest=_binding_digest(),
    )
    assert character.validate() == []
    assert locks.to_dict()["characters"][SUBJECT_ID] == {
        "hero_cut": None,
        "voice_persona": None,
        "face_id": FACE_ID,
        "voice_id": VOICE_ID,
        "identity_binding_digest": _binding_digest(),
        "sheet": {},
        "wardrobe": {},
    }


@pytest.mark.parametrize(
    ("face_id", "voice_id", "digest"),
    [
        (FACE_ID, None, None),
        (None, VOICE_ID, None),
        (FACE_ID, VOICE_ID, None),
        (FACE_ID, VOICE_ID, "sha256:" + "0" * 64),
    ],
)
def test_character_lock_rejects_partial_or_unbound_identity(
    face_id: str | None,
    voice_id: str | None,
    digest: str | None,
) -> None:
    lock = CharacterLock(
        persona_id=SUBJECT_ID,
        face_id=face_id,
        voice_id=voice_id,
        identity_binding_digest=digest,
    )

    assert lock.validate()


def test_ares_speaker_consumes_the_same_atomic_binding() -> None:
    speaker = AresSpeakerSlotV2.model_validate(
        {
            "role": "lead",
            "subject_id": SUBJECT_ID,
            "display_name": "수영하는 엄마",
            "face_id": FACE_ID,
            "voice_id": VOICE_ID,
            "identity_binding_digest": _binding_digest(),
            "voice_spec": _voice_spec(),
        }
    )

    assert speaker.identity_binding_digest == _binding_digest()


@pytest.mark.parametrize(
    "updates",
    [
        {},
        {"face_id": FACE_ID},
        {"voice_id": VOICE_ID},
        {"face_id": FACE_ID, "voice_id": VOICE_ID},
        {
            "face_id": FACE_ID,
            "voice_id": VOICE_ID,
            "identity_binding_digest": "sha256:" + "0" * 64,
        },
    ],
)
def test_ares_speaker_fails_closed_on_partial_or_changed_binding(
    updates: dict,
) -> None:
    with pytest.raises(ValidationError):
        AresSpeakerSlotV2.model_validate(
            {
                "role": "lead",
                "subject_id": SUBJECT_ID,
                "display_name": "수영하는 엄마",
                "voice_spec": _voice_spec(),
                **updates,
            }
        )


def test_ares_speaker_rejects_voice_spec_for_another_subject() -> None:
    with pytest.raises(ValidationError, match="voice_spec.subject_id"):
        AresSpeakerSlotV2.model_validate(
            {
                "role": "lead",
                "subject_id": SUBJECT_ID,
                "display_name": "수영하는 엄마",
                "voice_spec": _voice_spec("someone-else"),
            }
        )
