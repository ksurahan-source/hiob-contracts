from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import VoiceSpecV1, derive_voice_spec_digest_v1


def _payload() -> dict:
    return {
        "contract_version": "VoiceSpec.v1",
        "subject_id": "mom",
        "rhythm": "짧게 끊고 마지막에 한 박자 쉰다",
        "vocabulary": ["솔직히", "딱", "은근"],
        "forbidden_phrases": ["혁신적인", "여러분 안녕하세요"],
        "approved_examples": [
            "솔직히 이건 좀 놀랐어.",
            "딱 한 번만 해보면 감이 와.",
            "은근 이런 데서 차이가 나더라.",
        ],
    }


def test_voice_spec_has_one_canonical_digest_and_is_immutable() -> None:
    payload = _payload()
    spec = VoiceSpecV1.model_validate(
        {
            **payload,
            "voice_spec_digest": derive_voice_spec_digest_v1(payload),
        }
    )

    assert spec.voice_spec_digest == derive_voice_spec_digest_v1(payload)
    assert spec.model_dump(mode="json")["approved_examples"] == payload[
        "approved_examples"
    ]
    with pytest.raises(ValidationError):
        spec.subject_id = "other"


@pytest.mark.parametrize("example_count", [2, 6])
def test_voice_spec_requires_three_to_five_approved_examples(
    example_count: int,
) -> None:
    payload = _payload()
    payload["approved_examples"] = [
        f"승인 예시 {index}" for index in range(example_count)
    ]

    with pytest.raises(ValidationError):
        VoiceSpecV1.model_validate(
            {
                **payload,
                "voice_spec_digest": derive_voice_spec_digest_v1(payload),
            }
        )


def test_voice_spec_rejects_changed_content_under_old_digest() -> None:
    payload = _payload()
    digest = derive_voice_spec_digest_v1(payload)
    payload["rhythm"] = "광고처럼 길게 설명한다"

    with pytest.raises(ValidationError, match="voice_spec_digest"):
        VoiceSpecV1.model_validate({**payload, "voice_spec_digest": digest})


def test_voice_spec_rejects_unbounded_example_text() -> None:
    payload = _payload()
    payload["approved_examples"][0] = "가" * 501

    with pytest.raises(ValidationError):
        VoiceSpecV1.model_validate(
            {
                **payload,
                "voice_spec_digest": derive_voice_spec_digest_v1(payload),
            }
        )
