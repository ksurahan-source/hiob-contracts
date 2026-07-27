from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresSpeakerSlotV2,
    CharacterLock,
    ElementLocks,
    derive_character_identity_binding_digest_v1,
)


SUBJECT_ID = "mom"
FACE_ID = "face-mom-1"
VOICE_ID = "tc_voice_mom_1"


def _binding_digest() -> str:
    return derive_character_identity_binding_digest_v1(
        subject_id=SUBJECT_ID,
        face_id=FACE_ID,
        voice_id=VOICE_ID,
    )


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
        }
    )

    assert speaker.identity_binding_digest == _binding_digest()


@pytest.mark.parametrize(
    "updates",
    [
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
def test_ares_speaker_fails_closed_on_partial_or_changed_binding(updates: dict) -> None:
    with pytest.raises(ValidationError):
        AresSpeakerSlotV2.model_validate(
            {
                "role": "lead",
                "subject_id": SUBJECT_ID,
                "display_name": "수영하는 엄마",
                **updates,
            }
        )
