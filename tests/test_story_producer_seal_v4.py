"""V4 producer seals: five typed producer handoffs before Ares consumes them.

User journey: each of Janus, Karma, Parzifal, Artemis, and Metis can submit
one immutable, scope-bound artifact to Star's future ledger.  Star can then
reconstruct the existing Ares V4 authority reference without treating a
caller-provided flag as proof.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    INFO_SHORT_SLOT_SEQUENCE_V4,
    STORY_PRODUCER_ARTIFACT_PAIRS_V4,
    StoryProducerSealInputV4,
    StoryProducerSealLedgerRecordV4,
    canonical_story_producer_payload_digest_v4,
    sha256_digest,
    story_producer_seal_payload_digest_v4,
    story_producer_seal_receipt_digest_v4,
    story_producer_seal_to_ares_authority_ref_v4,
    story_producer_seal_to_ledger_record_v4,
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


def _rebind(data: dict) -> None:
    payload = data["payload"]
    payload["canonical_payload_digest"] = canonical_story_producer_payload_digest_v4(
        payload["canonical_payload"]
    )
    unsigned_payload = {
        key: value for key, value in payload.items() if key != "payload_digest"
    }
    payload["payload_digest"] = story_producer_seal_payload_digest_v4(unsigned_payload)

    ref = data["ref"]
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
    unsigned_ref = {key: value for key, value in ref.items() if key != "receipt_digest"}
    ref["receipt_digest"] = story_producer_seal_receipt_digest_v4(unsigned_ref)


def seal_input_data(producer: str, artifact_type: str) -> dict:
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
        "upstream_output_digests": [
            sha256_digest(
                {"producer": producer, "artifact_type": artifact_type, "input": 1}
            )
        ],
        "canonical_payload": canonical_payload,
        "canonical_payload_digest": "sha256:" + "0" * 64,
        "payload_digest": "sha256:" + "0" * 64,
    }
    data = {
        "contract_version": "StoryProducerSealInput.v4",
        "payload": payload,
        "ref": {
            "contract_version": "StoryProducerSealRef.v4",
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
            "receipt_id": f"{producer}-{artifact_type}-receipt-v4",
            "receipt_digest": "sha256:" + "0" * 64,
        },
    }
    _rebind(data)
    return data


@pytest.mark.parametrize(
    ("producer", "artifact_type"), STORY_PRODUCER_ARTIFACT_PAIRS_V4
)
def test_each_allowed_producer_seal_is_frozen_receipt_bound_and_ares_compatible(
    producer: str, artifact_type: str
):
    seal = StoryProducerSealInputV4.model_validate(
        seal_input_data(producer, artifact_type)
    )

    assert seal.ref.issuer == producer
    assert seal.ref.status == "sealed"
    assert isinstance(seal.payload.canonical_payload, dict) is False
    assert tuple(seal.payload.upstream_output_digests)
    with pytest.raises(ValidationError):
        seal.ref.status = "verified"
    with pytest.raises(TypeError):
        seal.payload.canonical_payload["tampered"] = True

    ares_ref = story_producer_seal_to_ares_authority_ref_v4(seal)
    assert ares_ref.producer == producer
    assert ares_ref.artifact_type == artifact_type
    assert ares_ref.payload_digest == seal.payload.canonical_payload_digest


def test_seal_record_is_flat_canonical_and_round_trips_without_a_trusted_run_digest():
    seal = StoryProducerSealInputV4.model_validate(
        seal_input_data("karma", "story_brief")
    )
    record = story_producer_seal_to_ledger_record_v4(seal)

    assert isinstance(record, StoryProducerSealLedgerRecordV4)
    assert record.seal_id == seal.ref.receipt_id
    assert record.to_input() == seal
    assert record.model_dump(mode="json") == {
        "contract_version": "StoryProducerSealLedgerRecord.v4",
        "seal_id": "karma-story_brief-receipt-v4",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "producer": "karma",
        "artifact_type": "story_brief",
        "issuer": "karma",
        "status": "sealed",
        "artifact_digest": seal.payload.artifact_digest,
        "source_output_digest": seal.payload.source_output_digest,
        "upstream_output_digests": list(seal.payload.upstream_output_digests),
        "canonical_payload": seal.payload.model_dump(mode="json")["canonical_payload"],
        "canonical_payload_digest": seal.payload.canonical_payload_digest,
        "payload_digest": seal.payload.payload_digest,
        "receipt_digest": seal.ref.receipt_digest,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda data: data["payload"].update({"artifact_type": "story_brief"}),
            id="wrong-producer-type-pair",
        ),
        pytest.param(
            lambda data: data["ref"].update({"issuer": "karma"}),
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
            lambda data: data["payload"].update({"source_output_digest": "sha256:BAD"}),
            id="malformed-digest",
        ),
        pytest.param(
            lambda data: data["payload"].update(
                {"upstream_output_digests": [data["payload"]["source_output_digest"]]}
            ),
            id="self-referential-lineage",
        ),
    ],
)
def test_seal_rejects_wrong_issuer_trust_flags_bad_digests_and_bad_lineage(mutation):
    data = seal_input_data("janus", "product_truth")
    mutation(data)
    _rebind(data)

    assert StoryProducerSealInputV4.model_validate is not None
    with pytest.raises(ValidationError):
        StoryProducerSealInputV4.model_validate(data)


def test_seal_rejects_raw_13q_and_raw_or_one_beat_story_shortcuts():
    raw_13q = seal_input_data("janus", "product_truth")
    raw_13q["payload"]["canonical_payload"]["thirteen_questions"] = {
        "q1": "원문 13Q는 producer seal로 넘길 수 없다"
    }
    _rebind(raw_13q)
    with pytest.raises(ValidationError, match="raw 13Q"):
        StoryProducerSealInputV4.model_validate(raw_13q)

    raw_story = seal_input_data("janus", "product_truth")
    raw_story["payload"]["canonical_payload"]["beats"] = [{"beat_index": 0}]
    _rebind(raw_story)
    with pytest.raises(ValidationError, match="raw story"):
        StoryProducerSealInputV4.model_validate(raw_story)

    one_beat = seal_input_data("karma", "story_brief")
    brief = one_beat["payload"]["canonical_payload"]
    brief["beats"] = brief["beats"][:1]
    unsigned = {
        key: value for key, value in brief.items() if key != "story_brief_digest"
    }
    brief["story_brief_digest"] = sha256_digest(unsigned)
    _rebind(one_beat)
    with pytest.raises(ValidationError, match="requires exactly"):
        StoryProducerSealInputV4.model_validate(one_beat)


def test_payload_and_receipt_digests_reject_tampering_even_when_fields_are_frozen():
    changed_payload = seal_input_data("metis", "hook_directive")
    changed_payload["ref"]["canonical_payload_digest"] = sha256_digest({"forged": True})
    changed_payload["ref"]["receipt_digest"] = story_producer_seal_receipt_digest_v4(
        {
            key: value
            for key, value in changed_payload["ref"].items()
            if key != "receipt_digest"
        }
    )
    with pytest.raises(ValidationError, match="canonical_payload_digest"):
        StoryProducerSealInputV4.model_validate(changed_payload)

    changed_receipt = seal_input_data("metis", "hook_directive")
    changed_receipt["ref"]["receipt_digest"] = sha256_digest({"forged": True})
    with pytest.raises(ValidationError, match="receipt_digest"):
        StoryProducerSealInputV4.model_validate(changed_receipt)
