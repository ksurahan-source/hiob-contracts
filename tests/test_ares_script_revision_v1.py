"""Ares XL V1 immutable script artifact and approval seam."""

from __future__ import annotations

from copy import deepcopy
import math

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    ApprovalReceipt,
    AresApprovalBeginCommandV1,
    AresApprovalCommandV1,
    AresApprovalReceiptV1,
    AresBeatPlanRevisionV1,
    AresSceneDirectionV1,
    AresScriptRevisionV1,
    AresScriptSegmentV1,
    BeatPlanV1,
    ScriptPackageV1,
    canonical_contract_json_v1,
    canonical_contract_digest_v1,
    derive_ares_g1_subject_digest_v1,
    sha256_digest,
)


TARGET_PROFILE_DIGEST = sha256_digest({"target": "mom"})
IDENTITY_LOCK_DIGEST = sha256_digest({"identity": "lead-v3"})
WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
SCRIPT_REVISION_ID = "00000000-0000-4000-8000-000000000003"
CANDIDATE_ID = "00000000-0000-4000-8000-000000000004"
PLAN_REVISION_ID = "00000000-0000-4000-8000-000000000005"


def _with_digest(body: dict, field: str) -> dict:
    value = deepcopy(body)
    value[field] = sha256_digest(value)
    return value


def master_sales_script_data() -> dict:
    return {
        "title": "엄마를 위한 XL",
        "positioning": "한 번에 이해되는 제품",
        "hook": {"line": "엄마, 이건 꼭 보세요.", "register": "가십"},
        "cta": {"line": "지금 확인해 보세요.", "action": "확인"},
        "persona_cast": [{"role": "lead", "subject_id": "mom"}],
        "beats": [
            {
                "beat_index": 0,
                "text": "엄마, 이건 꼭 보세요.",
                "direction": {
                    "shot": "MCU",
                    "subject": "엄마",
                    "setting": "주방",
                    "overlay": "꼭 보세요",
                },
            },
            {
                "beat_index": 1,
                "text": "지금 확인해 보세요.",
                "direction": {
                    "shot": "CU",
                    "subject": "제품",
                    "setting": "테이블",
                    "overlay": "지금 확인",
                },
            },
        ],
        "meta_copy": {"headline": "HIOB XL 👩‍👧"},
    }


def voice_segments() -> list[dict]:
    return [
        {"beat_index": 0, "text": "엄마, 이건 꼭 보세요."},
        {"beat_index": 1, "text": "지금 확인해 보세요."},
    ]


def caption_segments() -> list[dict]:
    return [
        {"beat_index": 0, "text": "엄마, 이건 꼭 보세요."},
        {"beat_index": 1, "text": "지금 확인"},
    ]


def script_package_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresScriptPackage.v1",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "revision_id": SCRIPT_REVISION_ID,
            "candidate_id": CANDIDATE_ID,
            "factory_revision": 7,
            "master_sales_script": master_sales_script_data(),
            "voice_script": voice_segments(),
            "caption_script": caption_segments(),
            "pronunciation_overrides": {
                "HIOB": "하이옵",
                "XL": "엑스엘",
            },
        },
        "package_digest",
    )


def _scene(
    shot: str,
    subject: str,
    setting: str,
    overlay: str,
) -> dict:
    return {
        "shot": shot,
        "subject": subject,
        "setting": setting,
        "overlay": overlay,
    }


def beat_plan_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresBeatPlan.v1",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "revision_id": PLAN_REVISION_ID,
            "script_revision_id": SCRIPT_REVISION_ID,
            "factory_revision": 7,
            "script_package_digest": script_package_data()["package_digest"],
            "beats": [
                {
                    "beat_index": 0,
                    "text": "엄마, 이건 꼭 보세요.",
                    "caption": "엄마, 이건 꼭 보세요.",
                    "scene_direction": _scene(
                        "MCU", "엄마", "주방", "꼭 보세요"
                    ),
                },
                {
                    "beat_index": 1,
                    "text": "지금 확인해 보세요.",
                    "caption": "지금 확인",
                    "scene_direction": _scene(
                        "CU", "제품", "테이블", "지금 확인"
                    ),
                },
            ],
            "production_plan": {
                "visual": {"approved": True},
                "sound": {"music_vibe": "warm"},
            },
        },
        "plan_digest",
    )


def revision_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresScriptRevision.v1",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "revision_id": SCRIPT_REVISION_ID,
            "candidate_id": CANDIDATE_ID,
            "factory_revision": 7,
            "script_package": script_package_data(),
        },
        "revision_digest",
    )


def beat_plan_revision_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresBeatPlanRevision.v1",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "revision_id": PLAN_REVISION_ID,
            "script_revision_id": SCRIPT_REVISION_ID,
            "factory_revision": 7,
            "approved_script_package_digest": script_package_data()[
                "package_digest"
            ],
            "beat_plan": beat_plan_data(),
        },
        "revision_digest",
    )


def approval_command_data(kind: str = "script") -> dict:
    script_revision = revision_data()
    plan_revision = beat_plan_revision_data()
    script_package_digest = script_revision["script_package"]["package_digest"]
    beat_plan_digest = plan_revision["beat_plan"]["plan_digest"]
    g1_subject_digest = derive_ares_g1_subject_digest_v1(
        TARGET_PROFILE_DIGEST,
        IDENTITY_LOCK_DIGEST,
        script_package_digest,
        beat_plan_digest,
    )
    return _with_digest(
        {
            "contract_version": "AresApprovalCommand.v1",
            "command_id": f"command-{kind}",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "revision_id": (
                script_revision["revision_id"]
                if kind == "script"
                else plan_revision["revision_id"]
            ),
            "approval_kind": kind,
            "artifact_digest": (
                script_package_digest
                if kind == "script"
                else g1_subject_digest
            ),
            "target_profile_digest": TARGET_PROFILE_DIGEST,
            "identity_lock_digest": IDENTITY_LOCK_DIGEST,
            "script_package_digest": script_package_digest,
            "beat_plan_digest": None if kind == "script" else beat_plan_digest,
            "g1_subject_digest": (
                None if kind == "script" else g1_subject_digest
            ),
            "approver_account_id": "account-1",
            "policy_version": "ares-approval.v1",
            "factory_revision": 7,
            "expected_state_revision": 10,
            "issued_at_utc": "2026-07-23T01:02:03Z",
        },
        "command_digest",
    )


def approval_begin_command_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresApprovalBeginCommand.v1",
            "command_id": "command-begin-script",
            "workspace_id": WORKSPACE_ID,
            "run_id": RUN_ID,
            "candidate_id": CANDIDATE_ID,
            "requester_account_id": "account-1",
            "policy_version": "ares-approval.v1",
            "factory_revision": 7,
            "expected_state_revision": 0,
            "issued_at_utc": "2026-07-23T01:02:02Z",
        },
        "command_digest",
    )


def approval_receipt_data(kind: str = "script") -> dict:
    command = approval_command_data(kind)
    return _with_digest(
        {
            "contract_version": "AresApprovalReceipt.v1",
            "receipt_id": f"receipt-{kind}",
            "command_id": command["command_id"],
            "command_digest": command["command_digest"],
            "workspace_id": command["workspace_id"],
            "run_id": command["run_id"],
            "revision_id": command["revision_id"],
            "approval_kind": command["approval_kind"],
            "artifact_digest": command["artifact_digest"],
            "target_profile_digest": command["target_profile_digest"],
            "identity_lock_digest": command["identity_lock_digest"],
            "script_package_digest": command["script_package_digest"],
            "beat_plan_digest": command["beat_plan_digest"],
            "g1_subject_digest": command["g1_subject_digest"],
            "approver_account_id": command["approver_account_id"],
            "decision": "approved",
            "policy_version": "ares-approval.v1",
            "factory_revision": 7,
            "state_revision": 11,
            "approved_at_utc": "2026-07-23T01:02:04Z",
            "expires_at_utc": "2026-07-23T02:02:04Z",
            "revoked_at_utc": None,
            "transaction_audit_id": f"receipt-{kind}",
        },
        "receipt_digest",
    )


class Resolver:
    def __init__(self, current: bool = True):
        self.current = current
        self.calls: list[dict] = []

    def is_current_approval(self, **identity) -> bool:
        self.calls.append(identity)
        return self.current


def _rehash(data: dict, field: str) -> None:
    data[field] = sha256_digest(
        {key: value for key, value in data.items() if key != field}
    )


def test_public_contracts_roundtrip_and_generic_approval_aliases_are_absent():
    package = ScriptPackageV1.model_validate(script_package_data())
    plan = BeatPlanV1.model_validate(beat_plan_data())
    script_revision = AresScriptRevisionV1.model_validate(revision_data())
    plan_revision = AresBeatPlanRevisionV1.model_validate(
        beat_plan_revision_data()
    )
    command = AresApprovalCommandV1.model_validate(approval_command_data())
    begin_command = AresApprovalBeginCommandV1.model_validate(
        approval_begin_command_data()
    )
    receipt = AresApprovalReceiptV1.model_validate(approval_receipt_data())

    assert package.model_dump(mode="json") == script_package_data()
    assert package.voice_script == (
        AresScriptSegmentV1(beat_index=0, text="엄마, 이건 꼭 보세요."),
        AresScriptSegmentV1(beat_index=1, text="지금 확인해 보세요."),
    )
    assert plan.beats[0].scene_direction == AresSceneDirectionV1(
        shot="MCU", subject="엄마", setting="주방", overlay="꼭 보세요"
    )
    assert script_revision.script_package == package
    assert not hasattr(script_revision, "beat_plan")
    assert plan_revision.binds_script_revision(script_revision)
    assert command.binds_revision(script_revision)
    assert begin_command.candidate_id == CANDIDATE_ID
    assert receipt.structurally_binds(command, script_revision)
    assert ApprovalReceipt is not AresApprovalReceiptV1
    assert not hasattr(hiob_contracts, "ApprovalCommandV1")
    assert not hasattr(hiob_contracts, "ApprovalReceiptV1")


def test_package_digest_covers_full_master_segments_and_pronunciation():
    base = script_package_data()
    baseline = base["package_digest"]
    mutations = []

    changed_master = deepcopy(base)
    changed_master["master_sales_script"]["beats"][0]["text"] = "변조"
    mutations.append(changed_master)
    changed_voice = deepcopy(base)
    changed_voice["voice_script"][0]["text"] = "다른 음성"
    mutations.append(changed_voice)
    changed_caption = deepcopy(base)
    changed_caption["caption_script"][0]["text"] = "다른 자막"
    mutations.append(changed_caption)
    changed_pronunciation = deepcopy(base)
    changed_pronunciation["pronunciation_overrides"]["XL"] = "엑스 라지"
    mutations.append(changed_pronunciation)

    for changed in mutations:
        changed.pop("package_digest")
        assert canonical_contract_digest_v1(changed) != baseline


def test_master_sales_script_must_be_nonempty_json_and_is_deeply_frozen():
    package = ScriptPackageV1.model_validate(script_package_data())
    with pytest.raises(TypeError):
        package.master_sales_script["title"] = "변조"
    with pytest.raises(TypeError):
        package.master_sales_script["beats"][0]["text"] = "변조"
    with pytest.raises(TypeError):
        package.master_sales_script["beats"][0] |= {"text": "변조"}
    with pytest.raises(TypeError):
        package.pronunciation_overrides |= {"XL": "변조"}
    with pytest.raises(TypeError):
        dict.__setitem__(package.master_sales_script, "title", "변조")
    assert package.master_sales_script["beats"][0]["text"] == "엄마, 이건 꼭 보세요."
    assert package.pronunciation_overrides["XL"] == "엑스엘"

    for bad in ({}, {"bad": {1, 2}}, {"bad": math.nan}):
        data = script_package_data()
        data["master_sales_script"] = bad
        with pytest.raises((ValidationError, ValueError, TypeError)):
            ScriptPackageV1.model_validate(data)


def test_pronunciation_keys_reject_trim_collisions():
    data = script_package_data()
    data["pronunciation_overrides"] = {
        " XL ": "first",
        "XL": "second",
    }
    normalized = deepcopy(data)
    normalized["pronunciation_overrides"] = {"XL": "second"}
    data["package_digest"] = canonical_contract_digest_v1(
        normalized,
        exclude={"package_digest"},
    )
    with pytest.raises(ValidationError, match="unique after trimming"):
        ScriptPackageV1.model_validate(data)


def test_revalidation_rejects_model_copy_nested_bypass():
    package = ScriptPackageV1.model_validate(script_package_data())
    bad_segment = package.voice_script[0].model_copy(update={"text": "   "})
    copied = package.model_copy(
        update={"voice_script": (bad_segment, *package.voice_script[1:])}
    )
    with pytest.raises(ValidationError, match="non-empty dialogue"):
        ScriptPackageV1.model_validate(copied)


def test_beat_text_preserves_nonblank_surrounding_whitespace():
    data = beat_plan_data()
    data["beats"][0]["text"] = "  엄마, 이건 꼭 보세요.  "
    _rehash(data, "plan_digest")
    plan = BeatPlanV1.model_validate(data)
    assert plan.beats[0].text == "  엄마, 이건 꼭 보세요.  "


@pytest.mark.parametrize(
    ("field", "segments"),
    [
        ("voice_script", []),
        (
            "voice_script",
            [
                {"beat_index": 1, "text": "a"},
                {"beat_index": 2, "text": "b"},
            ],
        ),
        (
            "voice_script",
            [
                {"beat_index": 0, "text": "a"},
                {"beat_index": 2, "text": "b"},
            ],
        ),
        (
            "voice_script",
            [
                {"beat_index": 1, "text": "a"},
                {"beat_index": 0, "text": "b"},
            ],
        ),
        (
            "voice_script",
            [
                {"beat_index": 0, "text": " "},
                {"beat_index": 1, "text": "b"},
            ],
        ),
        (
            "caption_script",
            [
                {"beat_index": 0, "text": "a"},
                {"beat_index": 2, "text": "b"},
            ],
        ),
    ],
)
def test_segments_reject_empty_unordered_gapped_or_blank_voice(field, segments):
    data = script_package_data()
    data[field] = segments
    _rehash(data, "package_digest")
    with pytest.raises(ValidationError, match="script|segment|beat"):
        ScriptPackageV1.model_validate(data)


def test_segments_require_equal_lengths_and_matching_indices_but_caption_may_be_empty():
    data = script_package_data()
    data["caption_script"] = [{"beat_index": 0, "text": ""}]
    _rehash(data, "package_digest")
    with pytest.raises(ValidationError, match="one-to-one|length"):
        ScriptPackageV1.model_validate(data)

    valid = script_package_data()
    valid["caption_script"][0]["text"] = ""
    _rehash(valid, "package_digest")
    parsed = ScriptPackageV1.model_validate(valid)
    assert parsed.caption_script[0].text == ""


def test_beat_plan_requires_exact_zero_based_indices_and_normalized_scene_direction():
    for bad_indices in ([1, 2], [0, 2], [1, 0], [0, 0]):
        data = beat_plan_data()
        for beat, index in zip(data["beats"], bad_indices):
            beat["beat_index"] = index
        _rehash(data, "plan_digest")
        with pytest.raises(ValidationError, match="0..N-1|beat"):
            BeatPlanV1.model_validate(data)

    missing = beat_plan_data()
    del missing["beats"][0]["scene_direction"]["shot"]
    _rehash(missing, "plan_digest")
    with pytest.raises(ValidationError):
        BeatPlanV1.model_validate(missing)

    extra = beat_plan_data()
    extra["beats"][0]["scene_direction"]["camera"] = "invented"
    _rehash(extra, "plan_digest")
    with pytest.raises(ValidationError):
        BeatPlanV1.model_validate(extra)


def test_scene_direction_mutation_invalidates_plan_digest():
    data = beat_plan_data()
    data["beats"][0]["scene_direction"]["overlay"] = "변조"
    with pytest.raises(ValidationError, match="plan_digest"):
        BeatPlanV1.model_validate(data)


def test_revision_scope_and_plan_script_binding_fail_closed():
    data = revision_data()
    data["script_package"]["workspace_id"] = "ws-other"
    _rehash(data["script_package"], "package_digest")
    _rehash(data, "revision_digest")
    with pytest.raises(ValidationError, match="workspace_id"):
        AresScriptRevisionV1.model_validate(data)

    wrong_factory = revision_data()
    wrong_factory["script_package"]["factory_revision"] = 8
    _rehash(wrong_factory["script_package"], "package_digest")
    _rehash(wrong_factory, "revision_digest")
    with pytest.raises(ValidationError, match="factory_revision"):
        AresScriptRevisionV1.model_validate(wrong_factory)

    plan_data = beat_plan_revision_data()
    plan_data["approved_script_package_digest"] = sha256_digest("other")
    _rehash(plan_data, "revision_digest")
    with pytest.raises(ValidationError, match="script_package_digest"):
        AresBeatPlanRevisionV1.model_validate(plan_data)

    wrong_plan_factory = beat_plan_revision_data()
    wrong_plan_factory["beat_plan"]["factory_revision"] = 8
    _rehash(wrong_plan_factory["beat_plan"], "plan_digest")
    _rehash(wrong_plan_factory, "revision_digest")
    with pytest.raises(ValidationError, match="factory_revision"):
        AresBeatPlanRevisionV1.model_validate(wrong_plan_factory)

    drift = beat_plan_revision_data()
    drift["beat_plan"]["beats"][0]["text"] = "다른 대사"
    _rehash(drift["beat_plan"], "plan_digest")
    _rehash(drift, "revision_digest")
    assert not AresBeatPlanRevisionV1.model_validate(
        drift
    ).binds_script_revision(AresScriptRevisionV1.model_validate(revision_data()))


def test_g1_subject_requires_and_covers_all_four_digests():
    script_digest = script_package_data()["package_digest"]
    plan_digest = beat_plan_data()["plan_digest"]
    expected = sha256_digest(
        {
            "target_profile_digest": TARGET_PROFILE_DIGEST,
            "identity_lock_digest": IDENTITY_LOCK_DIGEST,
            "script_package_digest": script_digest,
            "beat_plan_digest": plan_digest,
        }
    )
    assert derive_ares_g1_subject_digest_v1(
        TARGET_PROFILE_DIGEST,
        IDENTITY_LOCK_DIGEST,
        script_digest,
        plan_digest,
    ) == expected

    values = [
        TARGET_PROFILE_DIGEST,
        IDENTITY_LOCK_DIGEST,
        script_digest,
        plan_digest,
    ]
    for index in range(4):
        changed = list(values)
        changed[index] = sha256_digest({"changed": index})
        assert derive_ares_g1_subject_digest_v1(*changed) != expected
        malformed = list(values)
        malformed[index] = ""
        with pytest.raises(ValueError):
            derive_ares_g1_subject_digest_v1(*malformed)

    with pytest.raises(TypeError):
        derive_ares_g1_subject_digest_v1(script_digest, plan_digest)


def test_receipt_authorizes_only_with_current_resolver_and_valid_time():
    revision = AresScriptRevisionV1.model_validate(revision_data())
    command = AresApprovalCommandV1.model_validate(approval_command_data())
    receipt = AresApprovalReceiptV1.model_validate(approval_receipt_data())
    resolver = Resolver()

    assert receipt.authorizes(
        command,
        revision,
        at_utc="2026-07-23T01:30:00Z",
        resolver=resolver,
    )
    assert resolver.calls == [
        {
            "receipt_id": "receipt-script",
            "command_id": "command-script",
            "workspace_id": WORKSPACE_ID,
            "factory_revision": 7,
            "state_revision": 11,
            "policy_version": "ares-approval.v1",
            "receipt_digest": receipt.receipt_digest,
            "command_digest": command.command_digest,
            "run_id": RUN_ID,
            "revision_id": SCRIPT_REVISION_ID,
            "approval_kind": "script",
            "artifact_digest": command.artifact_digest,
            "approver_account_id": "account-1",
            "target_profile_digest": TARGET_PROFILE_DIGEST,
            "identity_lock_digest": IDENTITY_LOCK_DIGEST,
            "script_package_digest": command.script_package_digest,
            "beat_plan_digest": None,
            "g1_subject_digest": None,
        }
    ]
    assert not receipt.authorizes(
        command,
        revision,
        at_utc="2026-07-23T02:02:04Z",
        resolver=Resolver(),
    )
    assert not receipt.authorizes(
        command,
        revision,
        at_utc="2026-07-23T01:30:00Z",
        resolver=Resolver(current=False),
    )
    with pytest.raises(TypeError):
        receipt.authorizes(
            command,
            revision,
            at_utc="2026-07-23T01:30:00Z",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_version", "ares-approval.v2"),
        ("factory_revision", 8),
        ("state_revision", 12),
    ],
)
def test_receipt_cas_metadata_must_match_the_signed_command(field, value):
    revision = AresScriptRevisionV1.model_validate(revision_data())
    command = AresApprovalCommandV1.model_validate(approval_command_data())
    receipt_payload = approval_receipt_data()
    receipt_payload[field] = value
    _rehash(receipt_payload, "receipt_digest")
    receipt = AresApprovalReceiptV1.model_validate(receipt_payload)

    assert not receipt.structurally_binds(command, revision)
    assert not receipt.authorizes(
        command,
        revision,
        at_utc="2026-07-23T01:30:00Z",
        resolver=Resolver(),
    )


def test_production_approval_binds_all_four_g1_subject_digests():
    script_revision = AresScriptRevisionV1.model_validate(revision_data())
    revision = AresBeatPlanRevisionV1.model_validate(
        beat_plan_revision_data()
    )
    command = AresApprovalCommandV1.model_validate(
        approval_command_data("production_plan")
    )
    receipt = AresApprovalReceiptV1.model_validate(
        approval_receipt_data("production_plan")
    )

    assert command.artifact_digest == command.g1_subject_digest
    assert command.artifact_digest != command.beat_plan_digest
    assert not command.binds_revision(revision)
    assert command.binds_revision(
        revision,
        approved_script_revision=script_revision,
    )
    assert not receipt.structurally_binds(command, revision)
    assert receipt.structurally_binds(
        command,
        revision,
        approved_script_revision=script_revision,
    )
    assert receipt.authorizes(
        command,
        revision,
        approved_script_revision=script_revision,
        at_utc="2026-07-23T01:30:00Z",
        resolver=Resolver(),
    )

    substituted = approval_command_data("production_plan")
    substituted["target_profile_digest"] = sha256_digest({"target": "other"})
    substituted["g1_subject_digest"] = derive_ares_g1_subject_digest_v1(
        substituted["target_profile_digest"],
        substituted["identity_lock_digest"],
        substituted["script_package_digest"],
        substituted["beat_plan_digest"],
    )
    substituted["artifact_digest"] = substituted["g1_subject_digest"]
    _rehash(substituted, "command_digest")
    substituted_command = AresApprovalCommandV1.model_validate(substituted)

    assert substituted_command.binds_revision(
        revision,
        approved_script_revision=script_revision,
    )
    assert not receipt.structurally_binds(
        substituted_command,
        revision,
        approved_script_revision=script_revision,
    )


def test_production_approval_rejects_rehashed_plan_that_drifts_from_script():
    script_revision = AresScriptRevisionV1.model_validate(revision_data())
    drifted_payload = beat_plan_revision_data()
    drifted_payload["beat_plan"]["beats"][0]["text"] = "변조된 대사"
    _rehash(drifted_payload["beat_plan"], "plan_digest")
    _rehash(drifted_payload, "revision_digest")
    drifted_revision = AresBeatPlanRevisionV1.model_validate(drifted_payload)

    command_payload = approval_command_data("production_plan")
    command_payload["beat_plan_digest"] = drifted_revision.beat_plan.plan_digest
    command_payload["g1_subject_digest"] = derive_ares_g1_subject_digest_v1(
        command_payload["target_profile_digest"],
        command_payload["identity_lock_digest"],
        command_payload["script_package_digest"],
        command_payload["beat_plan_digest"],
    )
    command_payload["artifact_digest"] = command_payload["g1_subject_digest"]
    _rehash(command_payload, "command_digest")
    command = AresApprovalCommandV1.model_validate(command_payload)

    assert not drifted_revision.binds_script_revision(script_revision)
    assert not command.binds_revision(
        drifted_revision,
        approved_script_revision=script_revision,
    )


def test_receipt_rejects_bad_decision_revision_and_time_order():
    cases = [
        ("decision", "rejected"),
        ("policy_version", ""),
        ("factory_revision", -1),
        ("state_revision", -1),
        ("expires_at_utc", "2026-07-23T01:02:04Z"),
        ("revoked_at_utc", "2026-07-23T01:02:03Z"),
    ]
    for field, value in cases:
        data = approval_receipt_data()
        data[field] = value
        _rehash(data, "receipt_digest")
        with pytest.raises(ValidationError):
            AresApprovalReceiptV1.model_validate(data)

    zero_revision = approval_receipt_data()
    zero_revision["factory_revision"] = 0
    zero_revision["state_revision"] = 0
    _rehash(zero_revision, "receipt_digest")
    with pytest.raises(ValidationError):
        AresApprovalReceiptV1.model_validate(zero_revision)


def test_revoked_or_preissued_receipt_never_authorizes():
    revision = AresScriptRevisionV1.model_validate(revision_data())
    command = AresApprovalCommandV1.model_validate(approval_command_data())

    revoked_data = approval_receipt_data()
    revoked_data["revoked_at_utc"] = "2026-07-23T01:10:00Z"
    _rehash(revoked_data, "receipt_digest")
    revoked = AresApprovalReceiptV1.model_validate(revoked_data)
    assert not revoked.authorizes(
        command,
        revision,
        at_utc="2026-07-23T01:05:00Z",
        resolver=Resolver(),
    )

    preissued_data = approval_receipt_data()
    preissued_data["approved_at_utc"] = "2026-07-23T01:02:02Z"
    _rehash(preissued_data, "receipt_digest")
    preissued = AresApprovalReceiptV1.model_validate(preissued_data)
    assert not preissued.authorizes(
        command,
        revision,
        at_utc="2026-07-23T01:30:00Z",
        resolver=Resolver(),
    )


def test_receipt_digest_covers_authorization_metadata():
    base = approval_receipt_data()
    baseline = base["receipt_digest"]
    for field, changed_value in (
        ("decision", "rejected"),
        ("policy_version", "ares-approval.v2"),
        ("factory_revision", 8),
        ("state_revision", 12),
        ("target_profile_digest", sha256_digest({"target": "other"})),
        ("identity_lock_digest", sha256_digest({"identity": "other"})),
        ("script_package_digest", sha256_digest({"script": "other"})),
        ("expires_at_utc", "2026-07-23T03:02:04Z"),
        ("revoked_at_utc", "2026-07-23T01:30:00Z"),
    ):
        changed = deepcopy(base)
        changed[field] = changed_value
        changed.pop("receipt_digest")
        assert canonical_contract_digest_v1(changed) != baseline


@pytest.mark.parametrize(
    ("model", "factory"),
    [
        (AresScriptSegmentV1, lambda: {"beat_index": 0, "text": "line"}),
        (AresSceneDirectionV1, lambda: _scene("CU", "엄마", "집", "")),
        (ScriptPackageV1, script_package_data),
        (BeatPlanV1, beat_plan_data),
        (AresScriptRevisionV1, revision_data),
        (AresBeatPlanRevisionV1, beat_plan_revision_data),
        (AresApprovalBeginCommandV1, approval_begin_command_data),
        (AresApprovalCommandV1, approval_command_data),
        (AresApprovalReceiptV1, approval_receipt_data),
    ],
)
def test_contracts_are_strict_frozen_and_forbid_extras(model, factory):
    data = factory()
    data["unsealed_extra"] = True
    with pytest.raises(ValidationError):
        model.model_validate(data)

    parsed = model.model_validate(factory())
    with pytest.raises(ValidationError):
        parsed.__setattr__(next(iter(model.model_fields)), "mutated")


def test_canonical_digest_determinism_and_ten_thousand_segments():
    left = {
        "z": [{"emoji": "👩‍👧", "line": "안녕하세요"}],
        "a": {"XL": "엑스엘", "HIOB": "하이옵"},
    }
    right = {
        "a": {"HIOB": "하이옵", "XL": "엑스엘"},
        "z": ({"line": "안녕하세요", "emoji": "👩‍👧"},),
    }
    assert canonical_contract_digest_v1(left) == canonical_contract_digest_v1(right)

    data = script_package_data()
    data["voice_script"] = [
        {"beat_index": index, "text": f"line-{index}"}
        for index in range(10_000)
    ]
    data["caption_script"] = [
        {"beat_index": index, "text": ""}
        for index in range(10_000)
    ]
    _rehash(data, "package_digest")
    assert len(ScriptPackageV1.model_validate(data).voice_script) == 10_000


def test_canonical_digest_rejects_cross_language_unsafe_numbers():
    for value in (-0.0, 1.5, 9_007_199_254_740_992):
        with pytest.raises(ValueError, match="float|safe range"):
            canonical_contract_digest_v1({"value": value})


def test_canonical_digest_astral_and_integer_like_key_golden_vectors():
    assert canonical_contract_json_v1({"\ue000": 1, "😀": 2}) == (
        '{"":1,"😀":2}'
    )
    assert canonical_contract_digest_v1({"\ue000": 1, "😀": 2}) == (
        "sha256:871954531859c7572c6279f90eb83a594ddc3a289e8bdc28d2a84ffb8c1a1703"
    )
    assert canonical_contract_digest_v1({"10": 1, "2": 2}) == (
        "sha256:4489ac68dd5e0c9eb21f0e6c3294139a7d51b793c0e2e515bdf6c12948537df1"
    )


def test_db_identity_and_revision_domains_fail_before_rpc():
    for field in ("workspace_id", "run_id", "revision_id", "candidate_id"):
        data = script_package_data()
        data[field] = "not-a-uuid"
        _rehash(data, "package_digest")
        with pytest.raises(ValidationError, match="UUID"):
            ScriptPackageV1.model_validate(data)

    data = script_package_data()
    data["factory_revision"] = 2_147_483_648
    _rehash(data, "package_digest")
    with pytest.raises(ValidationError):
        ScriptPackageV1.model_validate(data)

    command = approval_command_data()
    command["expected_state_revision"] = 2_147_483_647
    _rehash(command, "command_digest")
    with pytest.raises(ValidationError):
        AresApprovalCommandV1.model_validate(command)

    begin = approval_begin_command_data()
    begin["expected_state_revision"] = 1
    _rehash(begin, "command_digest")
    with pytest.raises(ValidationError):
        AresApprovalBeginCommandV1.model_validate(begin)

    changed_candidate = approval_begin_command_data()
    changed_candidate["candidate_id"] = (
        "00000000-0000-4000-8000-000000000099"
    )
    with pytest.raises(ValidationError, match="command_digest"):
        AresApprovalBeginCommandV1.model_validate(changed_candidate)


def test_receipt_audit_identity_and_timestamp_parity_fail_closed():
    audit_mismatch = approval_receipt_data()
    audit_mismatch["transaction_audit_id"] = "different-audit-id"
    _rehash(audit_mismatch, "receipt_digest")
    with pytest.raises(ValidationError, match="transaction_audit_id"):
        AresApprovalReceiptV1.model_validate(audit_mismatch)

    for factory, field in (
        (approval_command_data, "issued_at_utc"),
        (approval_receipt_data, "approved_at_utc"),
    ):
        payload = factory()
        payload[field] = "0000-01-01T00:00:00Z"
        _rehash(
            payload,
            "command_digest" if "command_digest" in payload else "receipt_digest",
        )
        with pytest.raises(ValidationError):
            (
                AresApprovalCommandV1
                if "command_digest" in payload
                else AresApprovalReceiptV1
            ).model_validate(payload)


def test_g1_digest_rejects_trailing_newline():
    values = [
        TARGET_PROFILE_DIGEST,
        IDENTITY_LOCK_DIGEST,
        script_package_data()["package_digest"],
        beat_plan_data()["plan_digest"],
    ]
    values[0] += "\n"
    with pytest.raises(ValueError, match="sha256"):
        derive_ares_g1_subject_digest_v1(*values)
