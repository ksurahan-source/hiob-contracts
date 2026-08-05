"""Ares V4 story input: upstream authority in, exact narrative arc out.

User journey: a creative operator selects UGC or information short form and
receives a complete, evidence-grounded narrative arc.  Ares must reject a
one-beat or raw-13Q shortcut before any model/provider work can begin.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresCreateStoryRequestV4,
    UGC_STORY_SLOT_SEQUENCE_V4,
    INFO_SHORT_SLOT_SEQUENCE_V4,
    ares_create_story_request_v4_schema_descriptor,
    ares_create_story_request_v4_schema_digest,
    request_content_digest_v4,
    sha256_digest,
    story_authority_ref_receipt_digest_v4,
)


WORKSPACE_ID = "ws-story-v4"
RUN_ID = "run-story-v4"
JANUS_DIGEST = sha256_digest({"janus": "product-truth"})
PARZIFAL_DIGEST = sha256_digest({"parzifal": "identity-lock"})
ARTEMIS_DIGEST = sha256_digest({"artemis": "evidence-bundle"})
METIS_DIGEST = sha256_digest({"metis": "hook-directive"})


def _story_beats(stages: tuple[str, ...]) -> list[dict]:
    beats: list[dict] = []
    for index, stage in enumerate(stages):
        beats.append(
            {
                "beat_index": index,
                "arc_stage": stage,
                "story_function": stage,
                "scene_intent": f"{stage}를 고객의 실제 장면으로 보여준다",
                "used_claim_ids": ["claim-fast-absorption"] if stage == "proof" else [],
                "addresses_anchor_ids": (
                    ["evidence-fast-absorption"]
                    if stage == "proof"
                    else ["objection-price"]
                    if stage == "objection"
                    else []
                ),
            }
        )
    return beats


def _evidence_bundle() -> dict:
    return {
        "contract_version": "AresStoryEvidenceBundle.v4",
        "evidence_bundle_digest": ARTEMIS_DIGEST,
        "anchors": [
            {
                "anchor_id": "evidence-fast-absorption",
                "claim_id": "claim-fast-absorption",
                "statement": "흡수가 빠르다는 검증된 제품 사실",
            }
        ],
    }


def _narrative_brief(mode: str, stages: tuple[str, ...]) -> dict:
    unsigned = {
        "contract_version": "AresStoryNarrativeBrief.v4",
        "mode": mode,
        "beats": _story_beats(stages),
        "karma_objection_anchors": [
            {
                "anchor_id": "objection-price",
                "objection": "가격이 부담스럽다는 망설임",
            }
        ],
    }
    return {**unsigned, "story_brief_digest": sha256_digest(unsigned)}


def _authority_ref(
    *,
    producer: str,
    artifact_type: str,
    artifact_digest: str,
    payload_digest: str,
) -> dict:
    body = {
        "producer": producer,
        "artifact_type": artifact_type,
        "artifact_digest": artifact_digest,
        "source_output_digest": sha256_digest(
            {"producer": producer, "artifact_type": artifact_type, "run": RUN_ID}
        ),
        "payload_digest": payload_digest,
        "receipt_id": f"{producer}-{artifact_type}-receipt-v4",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
    }
    return {
        **body,
        "receipt_digest": story_authority_ref_receipt_digest_v4(**body),
    }


def story_request_data(
    *,
    mode: str = "ugc_story",
    stages: tuple[str, ...] | None = None,
) -> dict:
    if stages is None:
        stages = (
            UGC_STORY_SLOT_SEQUENCE_V4
            if mode == "ugc_story"
            else INFO_SHORT_SLOT_SEQUENCE_V4
        )
    evidence = _evidence_bundle()
    narrative = _narrative_brief(mode, stages)
    return {
        "contract_version": "AresCreateStoryRequest.v4",
        "scope": {
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "operation_id": "op-story-v4",
            "idempotency_key": "ares-story-v4:ws-story-v4:run-story-v4:op-story-v4",
        },
        "authority": {
            "janus_product_truth_ref": _authority_ref(
                producer="janus",
                artifact_type="product_truth",
                artifact_digest=JANUS_DIGEST,
                payload_digest=sha256_digest({"janus": "product-truth-projection"}),
            ),
            "karma_story_brief_ref": _authority_ref(
                producer="karma",
                artifact_type="story_brief",
                artifact_digest=narrative["story_brief_digest"],
                payload_digest=sha256_digest(narrative),
            ),
            "parzifal_identity_lock_ref": _authority_ref(
                producer="parzifal",
                artifact_type="identity_lock",
                artifact_digest=PARZIFAL_DIGEST,
                payload_digest=sha256_digest({"parzifal": "identity-lock-projection"}),
            ),
            "artemis_evidence_bundle_ref": _authority_ref(
                producer="artemis",
                artifact_type="evidence_bundle",
                artifact_digest=ARTEMIS_DIGEST,
                payload_digest=sha256_digest(evidence),
            ),
            "metis_hook_directive_ref": _authority_ref(
                producer="metis",
                artifact_type="hook_directive",
                artifact_digest=METIS_DIGEST,
                payload_digest=sha256_digest({"metis": "hook-directive-projection"}),
            ),
        },
        "evidence_bundle": evidence,
        "narrative_brief": narrative,
    }


def _rebind_narrative(body: dict) -> None:
    narrative = body["narrative_brief"]
    unsigned = {key: value for key, value in narrative.items() if key != "story_brief_digest"}
    narrative["story_brief_digest"] = sha256_digest(unsigned)
    ref = body["authority"]["karma_story_brief_ref"]
    ref["artifact_digest"] = narrative["story_brief_digest"]
    ref["payload_digest"] = sha256_digest(narrative)
    unsigned_ref = {key: value for key, value in ref.items() if key != "receipt_digest"}
    ref["receipt_digest"] = story_authority_ref_receipt_digest_v4(**unsigned_ref)


def test_ugc_story_accepts_exact_16_slot_arc_and_all_five_authorities():
    request = AresCreateStoryRequestV4.model_validate(story_request_data())

    assert tuple(beat.story_function for beat in request.narrative_brief.beats) == UGC_STORY_SLOT_SEQUENCE_V4
    assert request.authority.janus_product_truth_ref.producer == "janus"
    assert request.authority.karma_story_brief_ref.producer == "karma"
    assert request.authority.parzifal_identity_lock_ref.producer == "parzifal"
    assert request.authority.artemis_evidence_bundle_ref.producer == "artemis"
    assert request.authority.metis_hook_directive_ref.producer == "metis"


def test_information_short_accepts_exact_12_slot_arc():
    request = AresCreateStoryRequestV4.model_validate(
        story_request_data(mode="info_short")
    )

    assert tuple(beat.arc_stage for beat in request.narrative_brief.beats) == INFO_SHORT_SLOT_SEQUENCE_V4


@pytest.mark.parametrize(
    ("mode", "stages"),
    [
        ("ugc_story", ("scene",)),
        ("info_short", UGC_STORY_SLOT_SEQUENCE_V4),
    ],
)
def test_story_contract_rejects_one_beat_and_wrong_mode_cardinality(
    mode: str, stages: tuple[str, ...]
):
    with pytest.raises(ValidationError):
        AresCreateStoryRequestV4.model_validate(
            story_request_data(mode=mode, stages=stages)
        )


def test_story_contract_rejects_out_of_order_slot_even_with_16_beats():
    body = story_request_data()
    body["narrative_brief"]["beats"][1]["arc_stage"] = "tension"
    body["narrative_brief"]["beats"][1]["story_function"] = "tension"
    _rebind_narrative(body)

    with pytest.raises(ValidationError, match="arc_stage must be scene"):
        AresCreateStoryRequestV4.model_validate(body)


def test_proof_stage_requires_artemis_evidence_anchor_and_claim():
    body = story_request_data()
    proof = next(
        beat for beat in body["narrative_brief"]["beats"] if beat["story_function"] == "proof"
    )
    proof["addresses_anchor_ids"] = ["objection-price"]
    _rebind_narrative(body)

    with pytest.raises(ValidationError, match="Artemis evidence anchor"):
        AresCreateStoryRequestV4.model_validate(body)

    missing_claim = story_request_data()
    proof = next(
        beat
        for beat in missing_claim["narrative_brief"]["beats"]
        if beat["story_function"] == "proof"
    )
    proof["used_claim_ids"] = []
    _rebind_narrative(missing_claim)

    with pytest.raises(ValidationError, match="used_claim_id"):
        AresCreateStoryRequestV4.model_validate(missing_claim)


def test_objection_stage_requires_karma_objection_anchor():
    body = story_request_data()
    objection = next(
        beat for beat in body["narrative_brief"]["beats"] if beat["story_function"] == "objection"
    )
    objection["addresses_anchor_ids"] = ["evidence-fast-absorption"]
    _rebind_narrative(body)

    with pytest.raises(ValidationError, match="Karma objection anchor"):
        AresCreateStoryRequestV4.model_validate(body)


def test_story_contract_rejects_raw_13q_and_wrong_upstream_owner():
    raw_13q = story_request_data()
    raw_13q["thirteen_questions"] = {"q1": "원문 13Q는 여기로 전달하면 안 된다"}

    with pytest.raises(ValidationError):
        AresCreateStoryRequestV4.model_validate(raw_13q)

    wrong_owner = story_request_data()
    ref = wrong_owner["authority"]["artemis_evidence_bundle_ref"]
    ref["producer"] = "janus"
    unsigned_ref = {key: value for key, value in ref.items() if key != "receipt_digest"}
    ref["receipt_digest"] = story_authority_ref_receipt_digest_v4(**unsigned_ref)

    with pytest.raises(ValidationError, match="artemis"):
        AresCreateStoryRequestV4.model_validate(wrong_owner)


def test_story_contract_rejects_raw_beat_count_and_evidence_payload_drift():
    raw_count = story_request_data()
    raw_count["n_beats"] = 1

    with pytest.raises(ValidationError):
        AresCreateStoryRequestV4.model_validate(raw_count)

    evidence_drift = story_request_data()
    evidence_drift["evidence_bundle"]["anchors"][0]["statement"] = "변조된 증거"

    with pytest.raises(ValidationError, match="payload_digest"):
        AresCreateStoryRequestV4.model_validate(evidence_drift)


def test_story_contract_freezes_nested_authority_and_narrative_models():
    request = AresCreateStoryRequestV4.model_validate(story_request_data())

    with pytest.raises(ValidationError):
        request.authority.janus_product_truth_ref.artifact_digest = JANUS_DIGEST
    with pytest.raises(ValidationError):
        request.narrative_brief.beats[0].scene_intent = "변조"


def test_schema_descriptor_and_request_digest_publish_v4_shape():
    request = AresCreateStoryRequestV4.model_validate(story_request_data())
    descriptor = ares_create_story_request_v4_schema_descriptor()

    assert descriptor["modes"]["ugc_story"] == list(UGC_STORY_SLOT_SEQUENCE_V4)
    assert descriptor["modes"]["info_short"] == list(INFO_SHORT_SLOT_SEQUENCE_V4)
    assert "raw_13q=forbidden" in descriptor["invariants"]
    assert ares_create_story_request_v4_schema_digest().startswith("sha256:")
    assert request_content_digest_v4(request).startswith("sha256:")
