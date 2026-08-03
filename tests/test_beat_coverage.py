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
