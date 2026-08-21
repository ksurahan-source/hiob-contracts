"""RED tests for the run-level exact beat coverage contract."""
from __future__ import annotations

from dataclasses import replace

import pytest

from hiob_contracts import (
    DEFAULT_BEAT_COVERAGE_LANES_V1,
    BeatCoverageV1,
    BeatLaneTerminalReceiptV1,
    SerialFanInReceiptV1,
)
from hiob_contracts.factory import sha256_digest


RUN_ID = "run-coverage-1"
WORKSPACE_ID = "workspace-1"
PACKAGE_DIGEST = sha256_digest({"package": "p1"})
PLAN_DIGEST = sha256_digest({"plan": "p1"})


def _lanes(n: int = 6) -> tuple[BeatLaneTerminalReceiptV1, ...]:
    return tuple(
        BeatLaneTerminalReceiptV1.create(
            run_id=RUN_ID,
            workspace_id=WORKSPACE_ID,
            package_digest=PACKAGE_DIGEST,
            plan_digest=PLAN_DIGEST,
            beat_index=beat_index,
            lane=lane,
            output_digest=sha256_digest({"beat_index": beat_index, "lane": lane}),
        )
        for beat_index in range(n)
        for lane in DEFAULT_BEAT_COVERAGE_LANES_V1
    )


def _coverage(n: int = 6) -> BeatCoverageV1:
    return BeatCoverageV1.create(
        run_id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        package_digest=PACKAGE_DIGEST,
        plan_digest=PLAN_DIGEST,
        expected_n_beats=n,
        expected_beat_indices=tuple(range(n)),
        lane_receipts=_lanes(n),
    )


def test_six_and_twelve_beat_coverage_roundtrip_and_alias():
    for n in (6, 12):
        coverage = _coverage(n)
        assert coverage.validate() == []
        assert SerialFanInReceiptV1.from_dict(coverage.to_dict()) == coverage
        assert BeatCoverageV1.from_dict(coverage.to_dict()) == coverage


def test_coverage_digest_is_deterministic_and_bound_to_payload():
    first = _coverage()
    second = _coverage()
    assert first.coverage_digest == second.coverage_digest
    # Python/TypeScript parity vector; lane completion order is canonicalized.
    assert first.coverage_digest == "sha256:7252864e3f9091ff6d3bb3d2a381cfc11ae67f4f88cef2c4f6e90c0067ebd536"
    assert first.coverage_digest.startswith("sha256:")
    assert replace(first, workspace_id="other-workspace").validate()


def test_expected_indices_must_be_exact_zero_based_set():
    missing = replace(_coverage(), expected_beat_indices=(0, 1, 3, 4, 5, 6))
    errors = missing.validate()
    assert any("expected_beat_indices" in error for error in errors)


def test_duplicate_missing_foreign_and_failed_lane_receipts_fail_closed():
    coverage = _coverage()
    duplicate = replace(
        coverage,
        lane_receipts=coverage.lane_receipts + (coverage.lane_receipts[0],),
    )
    assert any("duplicate" in error for error in duplicate.validate())

    missing = replace(coverage, lane_receipts=coverage.lane_receipts[:-1])
    assert any("missing" in error for error in missing.validate())

    foreign = replace(
        coverage,
        lane_receipts=(replace(coverage.lane_receipts[0], run_id="other-run"),)
        + coverage.lane_receipts[1:],
    )
    assert any("run_id" in error for error in foreign.validate())

    failed = replace(
        coverage,
        lane_receipts=(replace(coverage.lane_receipts[0], status="failed"),)
        + coverage.lane_receipts[1:],
    )
    assert any("succeeded" in error or "failed" in error for error in failed.validate())


def test_out_of_range_lane_is_rejected_even_when_count_matches():
    coverage = _coverage()
    out_of_range = replace(
        coverage,
        lane_receipts=(replace(coverage.lane_receipts[0], beat_index=6),)
        + coverage.lane_receipts[1:],
    )
    assert any("out of range" in error for error in out_of_range.validate())


def test_required_lanes_cannot_drop_the_serial_f1_spine():
    coverage = replace(_coverage(), required_lanes=("evil",))
    errors = coverage.validate()
    assert any("required_lanes must include" in error for error in errors)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"unexpected": "key"},
        {"expected_n_beats": "6"},
        {"expected_n_beats": True},
        {"lane_receipts": "not-an-array"},
    ],
)
def test_from_dict_rejects_malformed_unknown_and_coercible_boundaries(payload):
    valid = _coverage().to_dict()
    if isinstance(payload, dict):
        payload = {**valid, **payload}

    with pytest.raises(ValueError):
        BeatCoverageV1.from_dict(payload)


def test_creators_return_valid_values_or_fail_closed():
    with pytest.raises(ValueError):
        BeatLaneTerminalReceiptV1.create(
            run_id=RUN_ID,
            workspace_id=WORKSPACE_ID,
            package_digest=PACKAGE_DIGEST,
            plan_digest=PLAN_DIGEST,
            beat_index=0,
            lane="athena",
            status="failed",
        )

    with pytest.raises(ValueError):
        _coverage(17)


def test_lane_constructor_preserves_nonblank_whitespace_in_digest_payload():
    receipt = BeatLaneTerminalReceiptV1.create(
        run_id=" run-padded ",
        workspace_id=" workspace-padded ",
        package_digest=sha256_digest({"package": "padded"}),
        plan_digest=sha256_digest({"plan": "padded"}),
        beat_index=0,
        lane=" athena ",
        output_digest=sha256_digest({"output": "padded"}),
    )

    assert receipt.run_id == " run-padded "
    assert receipt.lane == " athena "
    assert receipt.receipt_digest == (
        "sha256:65b1c484bebdb3d57f1dfc733748a8dd4cef862a9b374736a6c41395307c4d6a"
    )


def test_lane_receipt_from_dict_rejects_missing_and_wrong_field_types():
    with pytest.raises(ValueError, match="missing required fields"):
        BeatLaneTerminalReceiptV1.from_dict({})

    valid = _lanes(1)[0].to_dict()
    for field, value, message in (
        ("run_id", 1, "must be strings"),
        ("beat_index", True, "must be an integer"),
        ("output_digest", 1, "string or null"),
    ):
        payload = dict(valid)
        payload[field] = value
        with pytest.raises(ValueError, match=message):
            BeatLaneTerminalReceiptV1.from_dict(payload)


def test_lane_receipt_validation_reports_every_invalid_boundary():
    receipt = _lanes(1)[0]
    invalid = replace(
        receipt,
        run_id=1,
        workspace_id=" ",
        contract_version="unsupported",
        beat_index=True,
        package_digest="invalid",
        plan_digest="invalid",
        output_digest="invalid",
        status="running",
        receipt_digest="invalid",
    )
    errors = invalid.validate()
    for expected in (
        "run_id must be a string",
        "workspace_id is required",
        "unsupported lane receipt contract_version",
        "beat_index must be an integer",
        "package_digest must be a sha256 digest",
        "plan_digest must be a sha256 digest",
        "output_digest must be a sha256 digest",
        "status is not terminal",
        "receipt_digest must be a sha256 digest",
    ):
        assert any(expected in error for error in errors)

    assert "beat_index must be non-negative" in replace(
        receipt,
        beat_index=-1,
    ).validate()


def test_lane_receipt_canonical_serialization_failures_are_closed():
    with pytest.raises(ValueError, match="cannot be canonically serialized"):
        BeatLaneTerminalReceiptV1.create(
            run_id=object(),
            workspace_id=WORKSPACE_ID,
            package_digest=PACKAGE_DIGEST,
            plan_digest=PLAN_DIGEST,
            beat_index=0,
            lane="athena",
        )

    receipt = replace(_lanes(1)[0], run_id=object())
    errors = receipt.validate()
    assert "lane receipt payload cannot be canonically serialized" in errors


def test_coverage_from_dict_rejects_invalid_collection_members():
    valid = _coverage(1).to_dict()
    cases = (
        ("expected_beat_indices", [True], "contain integers"),
        ("required_lanes", [1], "contain strings"),
        ("lane_receipts", [{"unknown": "receipt"}], "contain receipts"),
    )
    for field, value, message in cases:
        payload = {**valid, field: value}
        with pytest.raises(ValueError, match=message):
            BeatCoverageV1.from_dict(payload)


def test_coverage_create_rejects_invalid_arrays_receipts_and_json():
    base = {
        "run_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "package_digest": PACKAGE_DIGEST,
        "plan_digest": PLAN_DIGEST,
        "expected_n_beats": 1,
        "expected_beat_indices": (0,),
        "lane_receipts": _lanes(1),
    }
    with pytest.raises(ValueError, match="must be an array"):
        BeatCoverageV1.create(**{**base, "required_lanes": "athena"})
    with pytest.raises(ValueError, match="lane_receipts are invalid"):
        BeatCoverageV1.create(
            **{**base, "lane_receipts": ({"unknown": "receipt"},)}
        )
    with pytest.raises(ValueError, match="cannot be canonically serialized"):
        BeatCoverageV1.create(**{**base, "run_id": object()})


def test_coverage_validation_reports_malformed_scope_and_collections():
    coverage = _coverage(1)
    malformed = replace(
        coverage,
        run_id=1,
        workspace_id=" ",
        contract_version="unsupported",
        package_digest="invalid",
        plan_digest="invalid",
        expected_beat_indices="invalid",
        required_lanes="invalid",
        lane_receipts="invalid",
        coverage_digest="invalid",
    )
    errors = malformed.validate()
    for expected in (
        "run_id must be a string",
        "workspace_id is required",
        "unsupported coverage contract_version",
        "package_digest must be a sha256 digest",
        "plan_digest must be a sha256 digest",
        "expected_beat_indices must be an array",
        "required_lanes must be an array",
        "lane_receipts must be an array",
        "coverage_digest must be a sha256 digest",
    ):
        assert expected in errors

    non_string_lanes = replace(
        coverage,
        required_lanes=(
            *DEFAULT_BEAT_COVERAGE_LANES_V1,
            1,
        ),
    )
    errors = non_string_lanes.validate()
    assert "required_lanes must contain non-blank lane names" in errors
    assert "required_lanes must contain strings" in errors

    duplicate_lanes = replace(
        coverage,
        required_lanes=(
            *DEFAULT_BEAT_COVERAGE_LANES_V1,
            DEFAULT_BEAT_COVERAGE_LANES_V1[0],
        ),
    )
    assert "required_lanes contains duplicate lanes" in duplicate_lanes.validate()

    invalid_receipts = replace(
        coverage,
        lane_receipts=(
            replace(coverage.lane_receipts[0], beat_index=True),
            object(),
            *coverage.lane_receipts[1:],
        ),
    )
    errors = invalid_receipts.validate()
    assert "lane_receipts must contain BeatLaneTerminalReceiptV1" in errors


def test_coverage_digest_canonical_serialization_failure_is_closed():
    coverage = replace(_coverage(1), run_id=object())
    assert "coverage payload cannot be canonically serialized" in coverage.validate()
