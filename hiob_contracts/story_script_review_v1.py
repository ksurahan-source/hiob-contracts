"""Minimal functional contract for an existing 13Q to script-review handoff.

This slice intentionally ends before storyboard or media materialization.  The
only paid operation it can authorize is one script generation call.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)


_MIN_VOICE_CHARS_PER_SECOND = 3
_MAX_VOICE_CHARS_PER_SECOND = 12
_MAX_VOICE_UTF8_BYTES_PER_SECOND = 32


def voice_text_metrics_v1(value: str) -> tuple[int, int]:
    """Return deterministic Unicode-codepoint and UTF-8 byte counts."""

    return len(value), len(value.encode("utf-8"))


def story_voice_limits_v1(duration_ms: int) -> tuple[int, int, int]:
    """Return inclusive character bounds and UTF-8 ceiling for one timed beat."""

    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
        raise TypeError("duration_ms must be an integer")
    if duration_ms < 1 or duration_ms > 55_000:
        raise ValueError("duration_ms must be between 1 and 55000")
    minimum_chars = (duration_ms * _MIN_VOICE_CHARS_PER_SECOND + 999) // 1_000
    maximum_chars = duration_ms * _MAX_VOICE_CHARS_PER_SECOND // 1_000
    maximum_utf8_bytes = duration_ms * _MAX_VOICE_UTF8_BYTES_PER_SECOND // 1_000
    return minimum_chars, maximum_chars, maximum_utf8_bytes


class StoryIntake13QV1(BaseModel):
    """The exact current Studio 13Q, with no caller-authored hook or assets."""

    model_config = _FROZEN_STRICT

    identity: NonBlankStr
    usp: NonBlankStr
    price: NonBlankStr
    voice_tone: NonBlankStr
    benefit: NonBlankStr
    proof: NonBlankStr
    audience: NonBlankStr
    pain: NonBlankStr
    jtbd: NonBlankStr
    channel: NonBlankStr
    price_sensitivity: NonBlankStr
    objection: NonBlankStr
    blocker: NonBlankStr


class StoryScriptPaidCallsV1(BaseModel):
    """The complete paid surface of Step 1: one script and zero media calls."""

    model_config = _FROZEN_STRICT

    script: Literal[1] = 1
    image: Literal[0] = 0
    video: Literal[0] = 0
    voice: Literal[0] = 0
    render: Literal[0] = 0


class StoryScriptRequestV1(BaseModel):
    """Server policy wrapped around the user's existing 13Q."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryScriptRequest.v1"]
    intake: StoryIntake13QV1
    target_duration_sec: int = Field(default=48, ge=45, le=55, strict=True)
    paid_calls: StoryScriptPaidCallsV1 = Field(default_factory=StoryScriptPaidCallsV1)
    intake_digest: DigestStr

    @classmethod
    def from_intake(
        cls,
        intake: StoryIntake13QV1 | Mapping[str, Any],
        *,
        target_duration_sec: int = 48,
    ) -> "StoryScriptRequestV1":
        validated = (
            intake
            if isinstance(intake, StoryIntake13QV1)
            else StoryIntake13QV1.model_validate(intake)
        )
        return cls(
            contract_version="StoryScriptRequest.v1",
            intake=validated,
            target_duration_sec=target_duration_sec,
            paid_calls=StoryScriptPaidCallsV1(),
            intake_digest=canonical_contract_digest_v1(validated),
        )

    @model_validator(mode="after")
    def _bind_intake(self) -> "StoryScriptRequestV1":
        if self.intake_digest != canonical_contract_digest_v1(self.intake):
            raise ValueError("intake_digest does not match the exact 13Q")
        if self.paid_calls != StoryScriptPaidCallsV1():
            raise ValueError("Step 1 paid_calls must authorize script only")
        return self


class StoryProductCardV1(BaseModel):
    """Human-readable product projection made only from product-side 13Q facts."""

    model_config = _FROZEN_STRICT

    identity: NonBlankStr
    usp: NonBlankStr
    price: NonBlankStr
    benefit: NonBlankStr
    proof: NonBlankStr
    card_digest: DigestStr

    @classmethod
    def from_intake(cls, intake: StoryIntake13QV1) -> "StoryProductCardV1":
        body = {
            "identity": intake.identity,
            "usp": intake.usp,
            "price": intake.price,
            "benefit": intake.benefit,
            "proof": intake.proof,
        }
        return cls(**body, card_digest=canonical_contract_digest_v1(body))

    @model_validator(mode="after")
    def _bind_card(self) -> "StoryProductCardV1":
        if self.card_digest != canonical_contract_digest_v1(
            self, exclude={"card_digest"}
        ):
            raise ValueError("card_digest does not match product card")
        return self


class StoryCharacterCardV1(BaseModel):
    """Human-readable character projection made only from audience-side 13Q facts."""

    model_config = _FROZEN_STRICT

    card_id: NonBlankStr
    role: Literal["lead", "support"]
    name: NonBlankStr
    age_range: NonBlankStr
    appearance: NonBlankStr
    wardrobe: NonBlankStr
    visual_traits: tuple[NonBlankStr, ...] = Field(min_length=2, max_length=6)
    audience: NonBlankStr
    pain: NonBlankStr
    jtbd: NonBlankStr
    voice_tone: NonBlankStr
    objection: NonBlankStr
    blocker: NonBlankStr
    card_digest: DigestStr

    @classmethod
    def from_intake(
        cls,
        intake: StoryIntake13QV1,
        *,
        card_id: str,
        role: Literal["lead", "support"],
        name: str,
        age_range: str,
        appearance: str,
        wardrobe: str,
        visual_traits: tuple[str, ...],
    ) -> "StoryCharacterCardV1":
        body = {
            "card_id": card_id,
            "role": role,
            "name": name,
            "age_range": age_range,
            "appearance": appearance,
            "wardrobe": wardrobe,
            "visual_traits": list(visual_traits),
            "audience": intake.audience,
            "pain": intake.pain,
            "jtbd": intake.jtbd,
            "voice_tone": intake.voice_tone,
            "objection": intake.objection,
            "blocker": intake.blocker,
        }
        return cls(**body, card_digest=canonical_contract_digest_v1(body))

    @field_validator("visual_traits", mode="before")
    @classmethod
    def _traits_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("visual_traits", mode="after")
    @classmethod
    def _unique_traits(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("visual_traits must be unique")
        return value

    @model_validator(mode="after")
    def _bind_card(self) -> "StoryCharacterCardV1":
        if self.card_digest != canonical_contract_digest_v1(
            self, exclude={"card_digest"}
        ):
            raise ValueError("card_digest does not match character card")
        return self


class StoryScriptBeatV1(BaseModel):
    """Lossless Step 1 text/time payload for later StoryboardCard promotion."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    script_text: NonBlankStr
    voice_text: NonBlankStr
    caption_text: NonBlankStr
    duration_ms: int = Field(ge=1_000, le=15_000, strict=True)
    voice_char_count: NonNegativeInt
    voice_utf8_bytes: NonNegativeInt

    @model_validator(mode="after")
    def _bind_speech_rate(self) -> "StoryScriptBeatV1":
        char_count, utf8_bytes = voice_text_metrics_v1(self.voice_text)
        if self.voice_char_count != char_count:
            raise ValueError("voice_char_count does not match voice_text")
        if self.voice_utf8_bytes != utf8_bytes:
            raise ValueError("voice_utf8_bytes does not match voice_text")
        minimum, maximum, utf8_maximum = story_voice_limits_v1(self.duration_ms)
        if char_count < minimum or char_count > maximum:
            raise ValueError("voice text exceeds timed speech character limits")
        if utf8_bytes > utf8_maximum:
            raise ValueError("voice text exceeds timed speech UTF-8 limit")
        return self


class StoryScriptReviewBundleV1(BaseModel):
    """The exact customer-visible stop after the first paid script call."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryScriptReviewBundle.v1"]
    source_intake_digest: DigestStr
    hook: NonBlankStr
    target_duration_sec: int = Field(ge=45, le=55, strict=True)
    product_card: StoryProductCardV1
    character_cards: tuple[StoryCharacterCardV1, ...] = Field(min_length=1)
    beats: tuple[StoryScriptBeatV1, ...]
    paid_calls: StoryScriptPaidCallsV1
    total_voice_char_count: NonNegativeInt
    total_voice_utf8_bytes: NonNegativeInt
    bundle_digest: DigestStr

    @field_validator("character_cards", "beats", mode="before")
    @classmethod
    def _to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @classmethod
    def build(
        cls,
        *,
        request: StoryScriptRequestV1,
        hook: str,
        product_card: StoryProductCardV1,
        character_cards: tuple[StoryCharacterCardV1, ...],
        beats: list[StoryScriptBeatV1] | tuple[StoryScriptBeatV1, ...],
    ) -> "StoryScriptReviewBundleV1":
        body = {
            "contract_version": "StoryScriptReviewBundle.v1",
            "source_intake_digest": request.intake_digest,
            "hook": hook,
            "target_duration_sec": request.target_duration_sec,
            "product_card": product_card.model_dump(mode="json"),
            "character_cards": [
                card.model_dump(mode="json") for card in character_cards
            ],
            "beats": [beat.model_dump(mode="json") for beat in beats],
            "paid_calls": request.paid_calls.model_dump(mode="json"),
            "total_voice_char_count": sum(beat.voice_char_count for beat in beats),
            "total_voice_utf8_bytes": sum(beat.voice_utf8_bytes for beat in beats),
        }
        return cls(
            **body,
            bundle_digest=canonical_contract_digest_v1(body),
        )

    @model_validator(mode="after")
    def _bind_review(self) -> "StoryScriptReviewBundleV1":
        if len(self.beats) != 16:
            raise ValueError("script review requires exactly 16 beats")
        if [beat.beat_index for beat in self.beats] != list(range(16)):
            raise ValueError("script review beat indices must be exactly 0..15")
        if (
            self.beats[0].script_text != self.hook
            or self.beats[0].voice_text != self.hook
        ):
            raise ValueError("first beat must equal the system hook")
        total_ms = sum(beat.duration_ms for beat in self.beats)
        if total_ms != self.target_duration_sec * 1_000:
            raise ValueError("beat duration must equal target_duration_sec")
        total_chars = sum(beat.voice_char_count for beat in self.beats)
        total_utf8_bytes = sum(beat.voice_utf8_bytes for beat in self.beats)
        if self.total_voice_char_count != total_chars:
            raise ValueError("total_voice_char_count does not match the timed script")
        if self.total_voice_utf8_bytes != total_utf8_bytes:
            raise ValueError("total_voice_utf8_bytes does not match the timed script")
        minimum, maximum, utf8_maximum = story_voice_limits_v1(total_ms)
        if total_chars < minimum or total_chars > maximum:
            raise ValueError("total script exceeds timed speech character limits")
        if total_utf8_bytes > utf8_maximum:
            raise ValueError("total script exceeds timed speech UTF-8 limit")
        card_ids = [card.card_id for card in self.character_cards]
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("character card_id values must be unique")
        if sum(card.role == "lead" for card in self.character_cards) != 1:
            raise ValueError("character cards require exactly one lead")
        if self.paid_calls != StoryScriptPaidCallsV1():
            raise ValueError("script review paid_calls must exclude every media call")
        if self.bundle_digest != canonical_contract_digest_v1(
            self, exclude={"bundle_digest"}
        ):
            raise ValueError("bundle_digest does not match script review bundle")
        return self


__all__ = [
    "voice_text_metrics_v1",
    "story_voice_limits_v1",
    "StoryIntake13QV1",
    "StoryScriptPaidCallsV1",
    "StoryScriptRequestV1",
    "StoryProductCardV1",
    "StoryCharacterCardV1",
    "StoryScriptBeatV1",
    "StoryScriptReviewBundleV1",
]
