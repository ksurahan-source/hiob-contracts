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
        values.append(
            StoryScriptBeatV1(
                beat_index=index,
                script_text=text,
                voice_text=text,
                caption_text=text,
                duration_ms=beat_ms,
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
            ),
        ),
        beats=_beats(duration, hook),
    )


def test_existing_intake_is_exactly_the_current_thirteen_questions() -> None:
    intake = StoryIntake13QV1.model_validate(INTAKE)

    assert tuple(intake.model_fields) == tuple(INTAKE)
    assert intake.model_dump(mode="json") == INTAKE
    with pytest.raises(ValidationError):
        StoryIntake13QV1.model_validate({key: value for key, value in INTAKE.items() if key != "benefit"})
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
    assert bundle.source_intake_digest == _request(duration).intake_digest


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
    wrong_card["product_card"]["usp"] = "승인되지 않은 표현"
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
