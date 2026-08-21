"""Functional 13Q -> script review contract, without downstream media authority."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    StoryCharacterCardV1,
    StoryIntake13QV1,
    StoryProductCardV1,
    StoryScriptBeatV1,
    StoryScriptPaidCallsV1,
    StoryScriptRequestV1,
    StoryScriptReviewBundleV1,
    story_voice_limits_v1,
    voice_text_metrics_v1,
)


INTAKE = {
    "identity": "뷰오케이 아이세이프",
    "usp": "수경 렌즈에 고르게 쓰는 김서림 방지 코팅",
    "price": "40ml 2+1",
    "voice_tone": "친근하고 단정한 설명",
    "benefit": "수영 중 렌즈 김서림을 줄임",
    "proof": "공식몰 상품 상세페이지",
    "audience": "수영을 배우는 아이의 보호자",
    "pain": "수영 중 수경이 흐려져 아이가 자꾸 멈춤",
    "jtbd": "수업 전에 수경을 빠르게 준비",
    "channel": "인스타그램 릴스",
    "price_sensitivity": "낭비 없이 오래 쓰고 싶음",
    "objection": "도포 과정이 번거로울까 걱정",
    "blocker": "사용 순서를 정확히 모름",
}


def _request(duration: int = 48) -> StoryScriptRequestV1:
    return StoryScriptRequestV1.from_intake(
        INTAKE,
        target_duration_sec=duration,
    )


def _beats(duration: int = 48, hook: str = "수경이 흐려 아이가 자꾸 멈추나요?"):
    total_ms = duration * 1_000
    base, remainder = divmod(total_ms, 16)
    values = []
    for index in range(16):
        beat_ms = base + (1 if index < remainder else 0)
        text = hook if index == 0 else f"13Q 근거 대본 {index}"
        voice_char_count, voice_utf8_bytes = voice_text_metrics_v1(text)
        values.append(
            StoryScriptBeatV1(
                beat_index=index,
                script_text=text,
                voice_text=text,
                caption_text=text,
                duration_ms=beat_ms,
                voice_char_count=voice_char_count,
                voice_utf8_bytes=voice_utf8_bytes,
            )
        )
    return values


def _bundle(duration: int = 48) -> StoryScriptReviewBundleV1:
    request = _request(duration)
    hook = "수경이 흐려 아이가 자꾸 멈추나요?"
    return StoryScriptReviewBundleV1.build(
        request=request,
        hook=hook,
        product_card=StoryProductCardV1.from_intake(request.intake),
        character_cards=(
            StoryCharacterCardV1.from_intake(
                request.intake,
                card_id="lead",
                role="lead",
                name="지우 엄마 서연",
                age_range="30대 후반",
                appearance="단정한 단발과 차분한 인상",
                wardrobe="네이비 집업과 밝은 운동복",
                visual_traits=("둥근 안경", "은색 수영 가방"),
            ),
        ),
        beats=_beats(duration, hook),
    )


def test_existing_intake_is_exactly_the_current_thirteen_questions() -> None:
    intake = StoryIntake13QV1.model_validate(INTAKE)

    assert tuple(StoryIntake13QV1.model_fields) == tuple(INTAKE)
    assert intake.model_dump(mode="json") == INTAKE
    with pytest.raises(ValidationError):
        StoryIntake13QV1.model_validate(
            {key: value for key, value in INTAKE.items() if key != "benefit"}
        )
    with pytest.raises(ValidationError):
        StoryIntake13QV1.model_validate({**INTAKE, "fixed_hook": "caller-owned hook"})


def test_request_defaults_to_48_seconds_and_exactly_one_script_call() -> None:
    request = StoryScriptRequestV1.from_intake(INTAKE)

    assert request.target_duration_sec == 48
    assert request.paid_calls == StoryScriptPaidCallsV1()
    assert request.paid_calls.model_dump(mode="json") == {
        "script": 1,
        "image": 0,
        "video": 0,
        "voice": 0,
        "render": 0,
    }


@pytest.mark.parametrize("duration", [45, 48, 55])
def test_review_bundle_is_hook_led_exactly_sixteen_beats_and_in_range(
    duration: int,
) -> None:
    bundle = _bundle(duration)

    assert len(bundle.beats) == 16
    assert bundle.beats[0].script_text == bundle.hook
    assert bundle.beats[0].voice_text == bundle.hook
    assert sum(beat.duration_ms for beat in bundle.beats) == duration * 1_000
    assert bundle.target_duration_sec == duration
    assert bundle.product_card.identity == INTAKE["identity"]
    assert bundle.character_cards[0].audience == INTAKE["audience"]
    assert bundle.character_cards[0].name == "지우 엄마 서연"
    assert bundle.character_cards[0].visual_traits == (
        "둥근 안경",
        "은색 수영 가방",
    )
    assert bundle.source_intake_digest == _request(duration).intake_digest
    assert bundle.total_voice_char_count == sum(
        beat.voice_char_count for beat in bundle.beats
    )
    assert bundle.total_voice_utf8_bytes == sum(
        beat.voice_utf8_bytes for beat in bundle.beats
    )


@pytest.mark.parametrize("duration", [44, 56])
def test_request_rejects_duration_outside_45_to_55_seconds(duration: int) -> None:
    with pytest.raises(ValidationError):
        _request(duration)


def test_bundle_rejects_timing_hook_card_and_paid_call_drift() -> None:
    bundle = _bundle()
    body = bundle.model_dump(mode="json")

    wrong_hook = {**body, "hook": "다른 훅"}
    with pytest.raises(ValidationError, match="first beat"):
        StoryScriptReviewBundleV1.model_validate(wrong_hook)

    wrong_timing = bundle.model_dump(mode="json")
    wrong_timing["beats"][8]["duration_ms"] += 1
    with pytest.raises(ValidationError, match="duration"):
        StoryScriptReviewBundleV1.model_validate(wrong_timing)

    wrong_card = bundle.model_dump(mode="json")
    wrong_card["character_cards"][0]["wardrobe"] = "매 beat마다 바뀌는 의상"
    with pytest.raises(ValidationError, match="card_digest"):
        StoryScriptReviewBundleV1.model_validate(wrong_card)

    wrong_calls = bundle.model_dump(mode="json")
    wrong_calls["paid_calls"]["image"] = 1
    with pytest.raises(ValidationError):
        StoryScriptReviewBundleV1.model_validate(wrong_calls)


def test_contracts_are_frozen_and_reject_extra_authority_fields() -> None:
    bundle = _bundle()

    with pytest.raises(ValidationError):
        StoryScriptRequestV1.model_validate(
            {
                **_request().model_dump(mode="json"),
                "authority": {"unnecessary": True},
            }
        )
    with pytest.raises(ValidationError):
        bundle.hook = "mutated"


def test_voice_metrics_and_limits_are_bound_to_each_beat_and_bundle_total() -> None:
    bundle = _bundle()
    beat = bundle.beats[1]
    minimum, maximum, utf8_maximum = story_voice_limits_v1(beat.duration_ms)

    assert minimum <= beat.voice_char_count <= maximum
    assert beat.voice_utf8_bytes <= utf8_maximum

    wrong_metrics = bundle.model_dump(mode="json")
    wrong_metrics["beats"][1]["voice_char_count"] += 1
    with pytest.raises(ValidationError, match="voice_char_count"):
        StoryScriptReviewBundleV1.model_validate(wrong_metrics)

    wrong_utf8_metrics = bundle.model_dump(mode="json")
    wrong_utf8_metrics["beats"][1]["voice_utf8_bytes"] += 1
    with pytest.raises(ValidationError, match="voice_utf8_bytes"):
        StoryScriptReviewBundleV1.model_validate(wrong_utf8_metrics)

    too_short = bundle.model_dump(mode="json")
    too_short["beats"][1]["voice_text"] = "짧음"
    too_short["beats"][1]["voice_char_count"] = len("짧음")
    too_short["beats"][1]["voice_utf8_bytes"] = len("짧음".encode("utf-8"))
    with pytest.raises(ValidationError, match="voice text|speech"):
        StoryScriptReviewBundleV1.model_validate(too_short)

    wrong_total = bundle.model_dump(mode="json")
    wrong_total["total_voice_utf8_bytes"] += 1
    with pytest.raises(ValidationError, match="total_voice_utf8_bytes"):
        StoryScriptReviewBundleV1.model_validate(wrong_total)


def test_voice_limit_argument_guards() -> None:
    with pytest.raises(TypeError, match="integer"):
        story_voice_limits_v1(True)
    with pytest.raises(ValueError, match="between 1 and 55000"):
        story_voice_limits_v1(0)


def test_request_and_card_late_digest_and_uniqueness_guards() -> None:
    request = _request()
    with pytest.raises(ValueError, match="intake_digest"):
        request.model_copy(
            update={"intake_digest": "sha256:" + "0" * 64}
        )._bind_intake()
    invalid_calls = StoryScriptPaidCallsV1.model_construct(
        script=1, image=1, video=0, voice=0, render=0
    )
    with pytest.raises(ValueError, match="script only"):
        request.model_copy(update={"paid_calls": invalid_calls})._bind_intake()

    product = StoryProductCardV1.from_intake(request.intake)
    with pytest.raises(ValueError, match="card_digest"):
        product.model_copy(
            update={"card_digest": "sha256:" + "0" * 64}
        )._bind_card()
    with pytest.raises(ValueError, match="visual_traits must be unique"):
        StoryCharacterCardV1._unique_traits(("same", "same"))


def test_beat_utf8_ceiling_guard_is_independent() -> None:
    beat = _beats()[0]
    text = "😀" * 9
    with pytest.raises(ValueError, match="UTF-8 limit"):
        beat.model_copy(
            update={
                "duration_ms": 1_000,
                "voice_text": text,
                "voice_char_count": len(text),
                "voice_utf8_bytes": len(text.encode("utf-8")),
            }
        )._bind_speech_rate()


def test_review_bundle_all_late_shape_rate_and_digest_guards() -> None:
    bundle = _bundle()
    with pytest.raises(ValueError, match="exactly 16 beats"):
        bundle.model_copy(update={"beats": bundle.beats[:-1]})._bind_review()
    with pytest.raises(ValueError, match="beat indices"):
        bundle.model_copy(
            update={
                "beats": (
                    bundle.beats[0].model_copy(update={"beat_index": 1}),
                    *bundle.beats[1:],
                )
            }
        )._bind_review()
    with pytest.raises(ValueError, match="total_voice_char_count"):
        bundle.model_copy(
            update={"total_voice_char_count": bundle.total_voice_char_count + 1}
        )._bind_review()

    huge_chars = bundle.beats[0].model_copy(update={"voice_char_count": 1_000})
    beats = (huge_chars, *bundle.beats[1:])
    with pytest.raises(ValueError, match="character limits"):
        bundle.model_copy(
            update={
                "beats": beats,
                "total_voice_char_count": sum(beat.voice_char_count for beat in beats),
            }
        )._bind_review()
    huge_utf8 = bundle.beats[0].model_copy(update={"voice_utf8_bytes": 2_000})
    beats = (huge_utf8, *bundle.beats[1:])
    with pytest.raises(ValueError, match="UTF-8 limit"):
        bundle.model_copy(
            update={
                "beats": beats,
                "total_voice_utf8_bytes": sum(beat.voice_utf8_bytes for beat in beats),
            }
        )._bind_review()

    card = bundle.character_cards[0]
    with pytest.raises(ValueError, match="card_id values"):
        bundle.model_copy(update={"character_cards": (card, card)})._bind_review()
    with pytest.raises(ValueError, match="exactly one lead"):
        bundle.model_copy(
            update={"character_cards": (card.model_copy(update={"role": "support"}),)}
        )._bind_review()
    invalid_calls = StoryScriptPaidCallsV1.model_construct(
        script=1, image=1, video=0, voice=0, render=0
    )
    with pytest.raises(ValueError, match="exclude every media call"):
        bundle.model_copy(update={"paid_calls": invalid_calls})._bind_review()
    with pytest.raises(ValueError, match="bundle_digest"):
        bundle.model_copy(
            update={"bundle_digest": "sha256:" + "0" * 64}
        )._bind_review()
