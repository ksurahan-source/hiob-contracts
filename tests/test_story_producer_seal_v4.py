"""V4 producer candidates are staged material; Star DB resolves authority.

User journey: a producer can stage one frozen artifact plus its causal inputs,
but only Star's durable resolver can return an accepted authority projection
for Ares.  A staged candidate is never an Ares authority reference.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    INFO_SHORT_SLOT_SEQUENCE_V4,
    STORY_PRODUCER_ARTIFACT_PAIRS_V4,
    STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4,
    StoryProducerSealCandidateV4,
    canonical_story_producer_payload_digest_v4,
    sha256_digest,
    story_producer_accepted_authority_projection_v4_schema_descriptor,
    story_producer_seal_payload_digest_v4,
    story_producer_staged_ref_digest_v4,
)


WORKSPACE_ID = "ws-story-seal-v4"
RUN_ID = "run-story-seal-v4"


def _story_beats() -> list[dict]:
    return [
        {
            "beat_index": index,
            "arc_stage": stage,
            "story_function": stage,
            "scene_intent": f"{stage}를 고객 장면으로 보여준다",
            "used_claim_ids": ["claim-fast"] if stage == "proof" else [],
            "addresses_anchor_ids": (
                ["evidence-fast"]
                if stage == "proof"
                else ["objection-price"]
                if stage == "objection"
                else []
            ),
        }
        for index, stage in enumerate(INFO_SHORT_SLOT_SEQUENCE_V4)
    ]


def _artifact_payload(producer: str, artifact_type: str) -> tuple[dict, str]:
    if (producer, artifact_type) == ("karma", "story_brief"):
        unsigned = {
            "contract_version": "AresStoryNarrativeBrief.v4",
            "mode": "info_short",
            "beats": _story_beats(),
            "karma_objection_anchors": [
                {"anchor_id": "objection-price", "objection": "가격이 부담스럽다"}
            ],
        }
        payload = {**unsigned, "story_brief_digest": sha256_digest(unsigned)}
        return payload, payload["story_brief_digest"]
    if (producer, artifact_type) == ("artemis", "evidence_bundle"):
        payload = {
            "contract_version": "AresStoryEvidenceBundle.v4",
            "evidence_bundle_digest": sha256_digest({"artifact": "evidence"}),
            "anchors": [
                {
                    "anchor_id": "evidence-fast",
                    "claim_id": "claim-fast",
                    "statement": "검증된 제품 사실",
                }
            ],
        }
        return payload, payload["evidence_bundle_digest"]
    if (producer, artifact_type) == ("metis", "hook_directive"):
        unsigned = {
            "contract_version": "AresStoryHookDirective.v4",
            "hook_line": "피부가 급할 때, 이 순서부터 바꿨어요.",
        }
        payload = {**unsigned, "directive_digest": sha256_digest(unsigned)}
        return payload, payload["directive_digest"]
    if (producer, artifact_type) == ("janus", "product_truth"):
        payload = {
            "contract_version": "JanusProductTruth.v4",
            "product_name": "진정 세럼",
            "facts": ["흡수가 빠른 제형"],
        }
        return payload, sha256_digest({"artifact": "janus-product-truth"})
    if (producer, artifact_type) == ("parzifal", "identity_lock"):
        payload = {
            "contract_version": "ParzifalIdentityLock.v4",
            "persona_id": "lead-expert",
            "voice_id": "voice-lead-v1",
        }
        return payload, sha256_digest({"artifact": "parzifal-identity-lock"})
    raise AssertionError(f"unexpected V4 producer pair: {(producer, artifact_type)!r}")


def _staged_upstream_digests(producer: str) -> list[str]:
    if producer == "janus":
        return []
    if producer == "karma":
        return [sha256_digest({"janus": "output"})]
    if producer == "parzifal":
        return [sha256_digest({"karma": "output"})]
    if producer in {"artemis", "metis"}:
        return []
    raise AssertionError(f"unexpected producer: {producer}")


def _rebind_candidate(data: dict) -> None:
    payload = data["payload"]
    payload["canonical_payload_digest"] = canonical_story_producer_payload_digest_v4(
        payload["canonical_payload"]
    )
    unsigned_payload = {
        key: value for key, value in payload.items() if key != "payload_digest"
    }
    payload["payload_digest"] = story_producer_seal_payload_digest_v4(unsigned_payload)

    ref = data["staged_ref"]
    for field in (
        "scope",
        "producer",
        "artifact_type",
        "artifact_digest",
        "source_output_digest",
        "upstream_output_digests",
        "canonical_payload_digest",
        "payload_digest",
    ):
        ref[field] = deepcopy(payload[field])
    unsigned_ref = {key: value for key, value in ref.items() if key != "candidate_digest"}
    ref["candidate_digest"] = story_producer_staged_ref_digest_v4(unsigned_ref)


def staged_candidate_data(producer: str, artifact_type: str) -> dict:
    canonical_payload, artifact_digest = _artifact_payload(producer, artifact_type)
    payload = {
        "contract_version": "StoryProducerSealPayload.v4",
        "scope": {"workspace_id": WORKSPACE_ID, "run_id": RUN_ID},
        "producer": producer,
        "artifact_type": artifact_type,
        "artifact_digest": artifact_digest,
        "source_output_digest": sha256_digest(
            {"producer": producer, "artifact_type": artifact_type, "output": 1}
        ),
        "upstream_output_digests": _staged_upstream_digests(producer),
        "canonical_payload": canonical_payload,
        "canonical_payload_digest": "sha256:" + "0" * 64,
        "payload_digest": "sha256:" + "0" * 64,
    }
    data = {
        "contract_version": "StoryProducerSealCandidate.v4",
        "payload": payload,
        "staged_ref": {
            "contract_version": "StoryProducerStagedRef.v4",
            "scope": deepcopy(payload["scope"]),
            "producer": producer,
            "artifact_type": artifact_type,
            "issuer": producer,
            "status": "sealed",
            "artifact_digest": artifact_digest,
            "source_output_digest": payload["source_output_digest"],
            "upstream_output_digests": deepcopy(payload["upstream_output_digests"]),
            "canonical_payload_digest": "sha256:" + "0" * 64,
            "payload_digest": "sha256:" + "0" * 64,
            "candidate_id": f"{producer}-{artifact_type}-candidate-v4",
            "candidate_digest": "sha256:" + "0" * 64,
        },
    }
    _rebind_candidate(data)
    return data


@pytest.mark.parametrize(("producer", "artifact_type"), STORY_PRODUCER_ARTIFACT_PAIRS_V4)
def test_each_allowed_producer_can_only_stage_frozen_candidate_material(
    producer: str, artifact_type: str
):
    candidate = StoryProducerSealCandidateV4.model_validate(
        staged_candidate_data(producer, artifact_type)
    )

    assert candidate.staged_ref.issuer == producer
    assert candidate.staged_ref.status == "sealed"
    assert list(candidate.payload.upstream_output_digests) == _staged_upstream_digests(
        producer
    )
    with pytest.raises(ValidationError):
        candidate.staged_ref.status = "accepted"
    with pytest.raises(TypeError):
        candidate.payload.canonical_payload["tampered"] = True


@pytest.mark.parametrize(
    ("producer", "artifact_type", "upstream_output_digests", "match"),
    [
        ("janus", "product_truth", [sha256_digest({"unexpected": 1})], "Janus"),
        ("karma", "story_brief", [], "Karma"),
        ("parzifal", "identity_lock", [], "Parzifal"),
        ("artemis", "evidence_bundle", [sha256_digest({"trusted": 1})], "DB"),
        ("metis", "hook_directive", [sha256_digest({"trusted": 1})], "DB"),
    ],
)
def test_staged_candidate_has_exact_pre_db_lineage_cardinality(
    producer: str,
    artifact_type: str,
    upstream_output_digests: list[str],
    match: str,
):
    data = staged_candidate_data(producer, artifact_type)
    data["payload"]["upstream_output_digests"] = upstream_output_digests
    _rebind_candidate(data)

    with pytest.raises(ValidationError, match=match):
        StoryProducerSealCandidateV4.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda data: data["payload"].update({"artifact_type": "story_brief"}),
            id="wrong-producer-type-pair",
        ),
        pytest.param(
            lambda data: data["staged_ref"].update({"issuer": "karma"}),
            id="wrong-issuer",
        ),
        pytest.param(
            lambda data: data.update({"verified": True}),
            id="caller-verified-flag",
        ),
        pytest.param(
            lambda data: data["payload"]["canonical_payload"].update(
                {"verified": True}
            ),
            id="nested-caller-verified-flag",
        ),
        pytest.param(
            lambda data: data["payload"].update(
                {"trusted_run_output_digest": sha256_digest({"trusted": True})}
            ),
            id="trusted-run-digest-is-not-a-producer-input",
        ),
        pytest.param(
            lambda data: data["payload"].update(
                {"source_output_digest": "sha256:BAD"}
            ),
            id="malformed-digest",
        ),
        pytest.param(
            lambda data: data["payload"].update(
                {
                    "upstream_output_digests": [
                        data["payload"]["source_output_digest"]
                    ]
                }
            ),
            id="self-referential-lineage",
        ),
    ],
)
def test_staged_candidate_rejects_wrong_issuer_trust_flags_bad_digests_and_lineage(
    mutation,
):
    data = staged_candidate_data("karma", "story_brief")
    mutation(data)
    _rebind_candidate(data)

    with pytest.raises(ValidationError):
        StoryProducerSealCandidateV4.model_validate(data)


def test_staged_candidate_rejects_raw_13q_and_raw_or_one_beat_story_shortcuts():
    raw_13q = staged_candidate_data("janus", "product_truth")
    raw_13q["payload"]["canonical_payload"]["thirteen_questions"] = {
        "q1": "원문 13Q는 producer seal로 넘길 수 없다"
    }
    _rebind_candidate(raw_13q)
    with pytest.raises(ValidationError, match="raw 13Q"):
        StoryProducerSealCandidateV4.model_validate(raw_13q)

    raw_story = staged_candidate_data("janus", "product_truth")
    raw_story["payload"]["canonical_payload"]["beats"] = [{"beat_index": 0}]
    _rebind_candidate(raw_story)
    with pytest.raises(ValidationError, match="raw story"):
        StoryProducerSealCandidateV4.model_validate(raw_story)

    one_beat = staged_candidate_data("karma", "story_brief")
    brief = one_beat["payload"]["canonical_payload"]
    brief["beats"] = brief["beats"][:1]
    unsigned = {
        key: value for key, value in brief.items() if key != "story_brief_digest"
    }
    brief["story_brief_digest"] = sha256_digest(unsigned)
    _rebind_candidate(one_beat)
    with pytest.raises(ValidationError, match="requires exactly"):
        StoryProducerSealCandidateV4.model_validate(one_beat)


def test_staged_candidate_cannot_yield_or_masquerade_as_accepted_ares_authority():
    candidate = StoryProducerSealCandidateV4.model_validate(
        staged_candidate_data("janus", "product_truth")
    )

    assert not hasattr(hiob_contracts, "story_producer_seal_to_ares_authority_ref_v4")
    assert not hasattr(hiob_contracts, "StoryProducerSealLedgerRecordV4")
    assert not hasattr(hiob_contracts, "StoryProducerAcceptedAuthorityProjectionV4")
    assert candidate.model_dump(mode="json")["staged_ref"]["status"] == "sealed"


def test_star_db_accepted_authority_is_only_a_nonconstructible_exact_field_descriptor():
    descriptor = story_producer_accepted_authority_projection_v4_schema_descriptor()

    assert STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4 == (
        "authority_ref",
        "sealed_payload",
        "issuer",
        "status",
        "upstream_output_digests",
    )
    assert descriptor == {
        "owner": "star_db_rpc",
        "accepted_authority": "external_only",
        "fields": list(STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4),
        "issuer": "<producer>.authority",
        "status": "accepted",
        "consumer": "ares_strict_request_parser",
    }
