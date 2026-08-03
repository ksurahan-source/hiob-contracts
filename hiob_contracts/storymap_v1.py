"""Strict, immutable Story OS maps and bounded experiment treatments.

Python is authoritative. A StoryMap holds customer and evidence truth; one
hypothesis and every treatment bind to its digest. Treatments deliberately have
no identity, product, or proof-fact fields: only hook, proof order, framing,
and CTA may vary.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)


MAX_PROOF_REFERENCES_V1 = 12
MAX_VARIANTS_V1 = 12

_STORY_MAP_DIGEST_FIELDS = (
    "contract_version",
    "customer_scene",
    "bad_alternative_tension",
    "urgent_moment",
    "emotional_stake",
    "proof_references",
    "objection",
    "offer",
    "cta",
    "target_metric",
    "content_mode",
    "story_policy_digest",
)
_EXPERIMENT_HYPOTHESIS_DIGEST_FIELDS = (
    "contract_version",
    "story_map_digest",
    "hypothesis",
)
_VARIANT_SET_DIGEST_FIELDS = (
    "contract_version",
    "story_map",
    "story_map_digest",
    "experiment_hypothesis",
    "variants",
)


def _data(value: Mapping[str, Any] | BaseModel) -> Mapping[str, Any]:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def _payload(
    value: Mapping[str, Any] | BaseModel,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    data = _data(value)
    return {field: data[field] for field in fields}


def derive_story_map_digest_v1(value: Mapping[str, Any] | BaseModel) -> str:
    """Derive the content digest for one immutable customer story map."""

    return canonical_contract_digest_v1(_payload(value, _STORY_MAP_DIGEST_FIELDS))


def derive_experiment_hypothesis_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Derive a hypothesis digest bound to exactly one StoryMap digest."""

    return canonical_contract_digest_v1(
        _payload(value, _EXPERIMENT_HYPOTHESIS_DIGEST_FIELDS)
    )


def derive_variant_set_digest_v1(value: Mapping[str, Any] | BaseModel) -> str:
    """Derive the complete set digest, including every bounded treatment."""

    return canonical_contract_digest_v1(_payload(value, _VARIANT_SET_DIGEST_FIELDS))


class ProofReferenceV1(BaseModel):
    """A stable reference ID and its locked proof-fact digest."""

    model_config = _FROZEN_STRICT

    proof_ref_id: Annotated[NonBlankStr, Field(max_length=160)]
    proof_fact_digest: DigestStr


class StoryMapV1(BaseModel):
    """The complete customer-and-evidence truth for a Story OS experiment."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryMap.v1"]
    customer_scene: Annotated[NonBlankStr, Field(max_length=1_200)]
    bad_alternative_tension: Annotated[NonBlankStr, Field(max_length=1_200)]
    urgent_moment: Annotated[NonBlankStr, Field(max_length=600)]
    emotional_stake: Annotated[NonBlankStr, Field(max_length=600)]
    proof_references: tuple[ProofReferenceV1, ...] = Field(
        min_length=1,
        max_length=MAX_PROOF_REFERENCES_V1,
    )
    objection: Annotated[NonBlankStr, Field(max_length=600)]
    offer: Annotated[NonBlankStr, Field(max_length=600)]
    cta: Annotated[NonBlankStr, Field(max_length=300)]
    target_metric: Annotated[NonBlankStr, Field(max_length=160)]
    content_mode: Literal["ugc", "information"]
    story_policy_digest: DigestStr
    story_map_digest: DigestStr

    @field_validator("proof_references", mode="before")
    @classmethod
    def _proof_references_are_immutable_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _story_map_is_complete_and_bound(self) -> "StoryMapV1":
        proof_ref_ids = [reference.proof_ref_id for reference in self.proof_references]
        if len(set(proof_ref_ids)) != len(proof_ref_ids):
            raise ValueError("proof_references contains duplicate proof_ref_id")
        if self.story_map_digest != derive_story_map_digest_v1(self):
            raise ValueError("story_map_digest does not match StoryMap content")
        return self


class ExperimentHypothesisV1(BaseModel):
    """One measurable claim about a StoryMap; no truth fields are copied here."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ExperimentHypothesis.v1"]
    story_map_digest: DigestStr
    hypothesis: Annotated[NonBlankStr, Field(max_length=1_200)]
    experiment_hypothesis_digest: DigestStr

    @model_validator(mode="after")
    def _hypothesis_is_bound(self) -> "ExperimentHypothesisV1":
        if self.experiment_hypothesis_digest != derive_experiment_hypothesis_digest_v1(
            self
        ):
            raise ValueError(
                "experiment_hypothesis_digest does not match ExperimentHypothesis content"
            )
        return self


class _StoryVariantV1(BaseModel):
    """A treatment deliberately restricted to the four allowed axes."""

    model_config = _FROZEN_STRICT

    variant_id: Annotated[NonBlankStr, Field(max_length=160)]
    story_map_digest: DigestStr
    hook: Annotated[NonBlankStr, Field(max_length=600)]
    proof_order: tuple[Annotated[NonBlankStr, Field(max_length=160)], ...] = Field(
        min_length=1,
        max_length=MAX_PROOF_REFERENCES_V1,
    )
    framing: Annotated[NonBlankStr, Field(max_length=1_200)]
    cta: Annotated[NonBlankStr, Field(max_length=300)]

    @field_validator("proof_order", mode="before")
    @classmethod
    def _proof_order_is_immutable_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class VariantSetV1(BaseModel):
    """A StoryMap-bound set of treatments with no fact-drift surface."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["VariantSet.v1"]
    story_map: StoryMapV1
    story_map_digest: DigestStr
    experiment_hypothesis: ExperimentHypothesisV1
    variants: tuple[_StoryVariantV1, ...] = Field(
        min_length=1,
        max_length=MAX_VARIANTS_V1,
    )
    variant_set_digest: DigestStr

    @field_validator("variants", mode="before")
    @classmethod
    def _variants_are_immutable_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _variant_set_is_story_map_bound(self) -> "VariantSetV1":
        if self.story_map_digest != self.story_map.story_map_digest:
            raise ValueError("story_map_digest does not match embedded StoryMap")
        if (
            self.experiment_hypothesis.story_map_digest
            != self.story_map.story_map_digest
        ):
            raise ValueError("experiment_hypothesis is bound to a different story_map_digest")

        variant_ids = [variant.variant_id for variant in self.variants]
        if len(set(variant_ids)) != len(variant_ids):
            raise ValueError("variants contains duplicate variant_id")

        expected_proof_ids = tuple(
            reference.proof_ref_id for reference in self.story_map.proof_references
        )
        for variant in self.variants:
            if variant.story_map_digest != self.story_map.story_map_digest:
                raise ValueError("variant story_map_digest does not match VariantSet")
            if (
                len(variant.proof_order) != len(expected_proof_ids)
                or set(variant.proof_order) != set(expected_proof_ids)
            ):
                raise ValueError(
                    "variant proof_order must be an exact ordering of StoryMap proof_ref_id values"
                )

        if self.variant_set_digest != derive_variant_set_digest_v1(self):
            raise ValueError("variant_set_digest does not match VariantSet content")
        return self


__all__ = [
    "ExperimentHypothesisV1",
    "MAX_PROOF_REFERENCES_V1",
    "MAX_VARIANTS_V1",
    "ProofReferenceV1",
    "StoryMapV1",
    "VariantSetV1",
    "derive_experiment_hypothesis_digest_v1",
    "derive_story_map_digest_v1",
    "derive_variant_set_digest_v1",
]
