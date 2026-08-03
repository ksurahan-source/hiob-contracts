"""Story OS maps are strict, immutable, and digest-linked."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ExperimentHypothesisV1,
    StoryMapV1,
    VariantSetV1,
    derive_experiment_hypothesis_digest_v1,
    derive_story_map_digest_v1,
    derive_variant_set_digest_v1,
    sha256_digest,
)


PROOF_A_DIGEST = sha256_digest(
    {"source": "ugc-before-after-01", "fact": "사용자 7일 기록"}
)
PROOF_B_DIGEST = sha256_digest(
    {"source": "ingredient-panel-01", "fact": "전성분 공개"}
)
STORY_POLICY_DIGEST = sha256_digest({"policy": "viewok-story-v1"})


def _story_map_payload() -> dict:
    body = {
        "contract_version": "StoryMap.v1",
        "customer_scene": "퇴근 뒤 10분, 거울 앞에서 급하게 피부를 확인한다.",
        "bad_alternative_tension": (
            "또 다른 자극적인 제품으로 가리고 싶지만, 반복되는 붉음이 두렵다."
        ),
        "urgent_moment": "내일 중요한 약속 전 오늘 밤",
        "emotional_stake": "민낯을 숨기지 않고 싶다",
        "proof_references": [
            {
                "proof_ref_id": "ugc-before-after-01",
                "proof_fact_digest": PROOF_A_DIGEST,
            },
            {
                "proof_ref_id": "ingredient-panel-01",
                "proof_fact_digest": PROOF_B_DIGEST,
            },
        ],
        "objection": "민감 피부에도 자극적이지 않을까?",
        "offer": "7일 안심 체험 키트",
        "cta": "지금 체험 키트 보기",
        "target_metric": "landing_click_through_rate",
        "content_mode": "ugc",
        "story_policy_digest": STORY_POLICY_DIGEST,
    }
    return {
        **body,
        "story_map_digest": derive_story_map_digest_v1(body),
    }


def _hypothesis_payload(story_map_digest: str) -> dict:
    body = {
        "contract_version": "ExperimentHypothesis.v1",
        "story_map_digest": story_map_digest,
        "hypothesis": "고객 장면을 첫 2초에 보여주면 랜딩 클릭률이 오른다.",
    }
    return {
        **body,
        "experiment_hypothesis_digest": derive_experiment_hypothesis_digest_v1(
            body
        ),
    }


def _variant_set_payload() -> dict:
    story_map = _story_map_payload()
    hypothesis = _hypothesis_payload(story_map["story_map_digest"])
    body = {
        "contract_version": "VariantSet.v1",
        "story_map": story_map,
        "story_map_digest": story_map["story_map_digest"],
        "experiment_hypothesis": hypothesis,
        "variants": [
            {
                "variant_id": "scene-first",
                "story_map_digest": story_map["story_map_digest"],
                "hook": "퇴근 후 거울을 피하게 되나요?",
                "proof_order": ["ugc-before-after-01", "ingredient-panel-01"],
                "framing": "공감 장면에서 시작한다.",
                "cta": "7일 체험 키트 보기",
            },
            {
                "variant_id": "proof-first",
                "story_map_digest": story_map["story_map_digest"],
                "hook": "7일 기록을 먼저 보여드릴게요.",
                "proof_order": ["ingredient-panel-01", "ugc-before-after-01"],
                "framing": "증거를 먼저 보여준다.",
                "cta": "성분과 체험 키트 보기",
            },
        ],
    }
    return {
        **body,
        "variant_set_digest": derive_variant_set_digest_v1(body),
    }


def _rebind_variant_set(value: dict) -> None:
    value["variant_set_digest"] = derive_variant_set_digest_v1(value)


def test_story_os_fixed_cross_language_digest_vectors() -> None:
    story_payload = _story_map_payload()
    story_map = StoryMapV1.model_validate(story_payload)
    hypothesis = ExperimentHypothesisV1.model_validate(
        _hypothesis_payload(story_map.story_map_digest)
    )
    variant_set = VariantSetV1.model_validate(_variant_set_payload())

    assert story_map.story_map_digest == (
        "sha256:c83833bf1f9cb1ff95501ba66c6f3feeb9b71dc80361051a06841b82701fa583"
    )
    assert hypothesis.experiment_hypothesis_digest == (
        "sha256:677dd8405c093fd7368c148c195ebde09a492022eb9c39ec232b6f9b37bb8bb6"
    )
    assert variant_set.variant_set_digest == (
        "sha256:b9cccc2369498f6a2cf78e37fe49b8bb617b85bd38552253b0bee8004daef1c4"
    )
    assert variant_set.story_map_digest == story_map.story_map_digest
    assert variant_set.experiment_hypothesis.story_map_digest == story_map.story_map_digest
    assert isinstance(story_map.proof_references, tuple)
    assert set(story_map.model_dump(mode="json")) == {
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
        "story_map_digest",
    }


def test_story_map_preserves_nonblank_whitespace_in_its_digest() -> None:
    value = _story_map_payload()
    value["cta"] = "  지금 체험 키트 보기  "
    value["story_map_digest"] = derive_story_map_digest_v1(value)

    parsed = StoryMapV1.model_validate(value)

    assert parsed.cta == "  지금 체험 키트 보기  "
    assert parsed.story_map_digest == (
        "sha256:9c92117b637ea5e17262311a8fba436473c433f0f4da55c85aa7e577c50cfcbf"
    )


@pytest.mark.parametrize(
    ("customer_scene", "accepted"),
    [
        ("\u0085", False),
        ("\u001c", False),
        ("\ufeff", True),
    ],
)
def test_story_map_uses_python_nonblank_whitespace_rules(
    customer_scene: str,
    accepted: bool,
) -> None:
    value = _story_map_payload()
    value["customer_scene"] = customer_scene
    value["story_map_digest"] = derive_story_map_digest_v1(value)

    if accepted:
        assert StoryMapV1.model_validate(value).customer_scene == customer_scene
    else:
        with pytest.raises(ValidationError, match="customer_scene"):
            StoryMapV1.model_validate(value)


def test_story_map_uses_unicode_scalars_for_bounds_and_hashing() -> None:
    boundary = _story_map_payload()
    boundary["customer_scene"] = "😀" * 1_200
    boundary["story_map_digest"] = derive_story_map_digest_v1(boundary)
    assert StoryMapV1.model_validate(boundary).customer_scene == "😀" * 1_200

    malformed = _story_map_payload()
    malformed["customer_scene"] = "\ud800"
    with pytest.raises(ValueError, match="unpaired Unicode surrogate"):
        derive_story_map_digest_v1(malformed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("identity_lock_digest", "sha256:" + "1" * 64),
        ("product_truth_digest", "sha256:" + "2" * 64),
        ("proof_fact", "invented proof"),
    ],
)
def test_story_map_forbids_extra_identity_product_and_proof_fact_fields(
    field: str,
    value: str,
) -> None:
    payload = _story_map_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        StoryMapV1.model_validate(payload)


def test_story_os_rejects_stale_digests_and_is_immutable() -> None:
    story_payload = _story_map_payload()
    stale_story = deepcopy(story_payload)
    stale_story["cta"] = "바뀐 CTA"
    with pytest.raises(ValidationError, match="story_map_digest"):
        StoryMapV1.model_validate(stale_story)

    hypothesis = _hypothesis_payload(story_payload["story_map_digest"])
    hypothesis["hypothesis"] = "바뀐 가설"
    with pytest.raises(ValidationError, match="experiment_hypothesis_digest"):
        ExperimentHypothesisV1.model_validate(hypothesis)

    variants = _variant_set_payload()
    variants["variants"][0]["hook"] = "바뀐 훅"
    with pytest.raises(ValidationError, match="variant_set_digest"):
        VariantSetV1.model_validate(variants)

    parsed = StoryMapV1.model_validate(story_payload)
    with pytest.raises(ValidationError):
        parsed.customer_scene = "mutated"
    with pytest.raises(ValidationError):
        parsed.proof_references[0].proof_ref_id = "mutated"


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "identity_lock_digest",
        "product_truth_digest",
        "proof_fact_digest",
        "proof_references",
    ],
)
def test_variants_can_carry_only_hook_proof_order_framing_and_cta(
    forbidden_field: str,
) -> None:
    value = _variant_set_payload()
    value["variants"][0][forbidden_field] = "not allowed"
    _rebind_variant_set(value)

    with pytest.raises(ValidationError):
        VariantSetV1.model_validate(value)


def test_variant_set_rejects_story_map_and_proof_order_drift_after_rehash() -> None:
    wrong_map = _variant_set_payload()
    wrong_map["variants"][0]["story_map_digest"] = "sha256:" + "9" * 64
    _rebind_variant_set(wrong_map)
    with pytest.raises(ValidationError, match="story_map_digest"):
        VariantSetV1.model_validate(wrong_map)

    wrong_proof_order = _variant_set_payload()
    wrong_proof_order["variants"][0]["proof_order"] = [
        "ugc-before-after-01",
        "ugc-before-after-01",
    ]
    _rebind_variant_set(wrong_proof_order)
    with pytest.raises(ValidationError, match="proof_order"):
        VariantSetV1.model_validate(wrong_proof_order)

    wrong_hypothesis = _variant_set_payload()
    wrong_hypothesis["story_map"]["customer_scene"] = "다른 장면"
    wrong_hypothesis["story_map"]["story_map_digest"] = derive_story_map_digest_v1(
        wrong_hypothesis["story_map"]
    )
    wrong_hypothesis["story_map_digest"] = wrong_hypothesis["story_map"][
        "story_map_digest"
    ]
    for variant in wrong_hypothesis["variants"]:
        variant["story_map_digest"] = wrong_hypothesis["story_map_digest"]
    _rebind_variant_set(wrong_hypothesis)
    with pytest.raises(ValidationError, match="experiment_hypothesis"):
        VariantSetV1.model_validate(wrong_hypothesis)
