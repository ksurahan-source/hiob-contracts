"""Exact run-level beat coverage and serial fan-in receipts.

The per-beat lane builders are intentionally free to finish out of order.  This
contract is the terminal join: it proves that every expected beat has exactly
one successful receipt for every required lane, all receipts belong to the same
run/workspace/script package/beat plan, and the resulting coverage is immutable
through a canonical digest.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from .factory.digest import is_digest, sha256_digest


BEAT_COVERAGE_CONTRACT_VERSION_V1 = "BeatCoverage.v1"
SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1 = "SerialFanInReceipt.v1"
BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1 = "BeatLaneTerminalReceipt.v1"

# The serial F1 spine requires these lanes.  Apollo/SFX is an optional lane and
# may be included in a receipt without changing the required coverage set.
DEFAULT_BEAT_COVERAGE_LANES_V1 = ("athena", "orpheus_vo", "atropos")
TERMINAL_BEAT_LANE_STATUSES_V1 = frozenset(
    {"succeeded", "failed", "cancelled", "blocked", "needs_human"}
)
_COVERAGE_CONTRACT_VERSIONS = frozenset(
    {
        BEAT_COVERAGE_CONTRACT_VERSION_V1,
        SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1,
    }
)


def _nonblank(value: Any) -> bool:
    return bool(str(value or "").strip())


@dataclass(frozen=True)
class BeatLaneTerminalReceiptV1:
    """One terminal result for one beat/lane pair."""

    run_id: str
    workspace_id: str
    package_digest: str
    plan_digest: str
    beat_index: int
    lane: str
    status: str = "succeeded"
    output_digest: str | None = None
    receipt_digest: str = ""
    contract_version: str = BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1

    def digest_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("receipt_digest", None)
        return payload

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BeatLaneTerminalReceiptV1":
        accepted = {item.name for item in fields(cls)}
        return cls(**{key: item for key, item in value.items() if key in accepted})

    @classmethod
    def create(cls, **values: Any) -> "BeatLaneTerminalReceiptV1":
        draft = cls(**{**values, "receipt_digest": ""})
        return replace(draft, receipt_digest=sha256_digest(draft.digest_payload()))

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("run_id", "workspace_id", "lane"):
            if not _nonblank(getattr(self, name)):
                errors.append(f"{name} is required")
        if self.contract_version != BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1:
            errors.append("unsupported lane receipt contract_version")
        if isinstance(self.beat_index, bool) or not isinstance(self.beat_index, int):
            errors.append("beat_index must be an integer")
        elif self.beat_index < 0:
            errors.append("beat_index must be non-negative")
        for name in ("package_digest", "plan_digest"):
            if not is_digest(getattr(self, name)):
                errors.append(f"{name} must be a sha256 digest")
        if self.output_digest is not None and not is_digest(self.output_digest):
            errors.append("output_digest must be a sha256 digest when present")
        if self.status not in TERMINAL_BEAT_LANE_STATUSES_V1:
            errors.append(f"status is not terminal: {self.status!r}")
        elif self.status != "succeeded":
            errors.append("lane receipt status must be succeeded")
        if not is_digest(self.receipt_digest):
            errors.append("receipt_digest must be a sha256 digest")
        elif self.receipt_digest != sha256_digest(self.digest_payload()):
            errors.append("receipt_digest does not match lane receipt payload")
        return errors


@dataclass(frozen=True)
class BeatCoverageV1:
    """Terminal exact beat coverage for a serial fan-in run."""

    run_id: str
    workspace_id: str
    package_digest: str
    plan_digest: str
    expected_n_beats: int
    expected_beat_indices: tuple[int, ...]
    lane_receipts: tuple[BeatLaneTerminalReceiptV1, ...]
    required_lanes: tuple[str, ...] = DEFAULT_BEAT_COVERAGE_LANES_V1
    coverage_digest: str = ""
    contract_version: str = BEAT_COVERAGE_CONTRACT_VERSION_V1

    def digest_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("coverage_digest", None)
        # Completion order is intentionally not part of run identity.  Sort
        # the exact lane set before hashing so workers may finish out of order.
        payload["lane_receipts"] = sorted(
            payload["lane_receipts"],
            key=lambda receipt: (int(receipt["beat_index"]), str(receipt["lane"])),
        )
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "package_digest": self.package_digest,
            "plan_digest": self.plan_digest,
            "expected_n_beats": self.expected_n_beats,
            "expected_beat_indices": list(self.expected_beat_indices),
            "lane_receipts": [receipt.to_dict() for receipt in self.lane_receipts],
            "required_lanes": list(self.required_lanes),
            "coverage_digest": self.coverage_digest,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BeatCoverageV1":
        receipts = value.get("lane_receipts")
        if receipts is None:
            receipts = value.get("terminal_receipts") or value.get("receipts") or ()
        package_digest = value.get("package_digest") or value.get("script_package_digest") or ""
        plan_digest = value.get("plan_digest") or value.get("beat_plan_digest") or ""
        return cls(
            run_id=str(value.get("run_id") or ""),
            workspace_id=str(value.get("workspace_id") or ""),
            package_digest=str(package_digest),
            plan_digest=str(plan_digest),
            expected_n_beats=int(value.get("expected_n_beats") or 0),
            expected_beat_indices=tuple(value.get("expected_beat_indices") or ()),
            lane_receipts=tuple(
                receipt
                if isinstance(receipt, BeatLaneTerminalReceiptV1)
                else BeatLaneTerminalReceiptV1.from_dict(receipt)
                for receipt in (receipts or ())
            ),
            required_lanes=tuple(
                value.get("required_lanes") or DEFAULT_BEAT_COVERAGE_LANES_V1
            ),
            coverage_digest=str(value.get("coverage_digest") or ""),
            contract_version=str(
                value.get("contract_version") or BEAT_COVERAGE_CONTRACT_VERSION_V1
            ),
        )

    @classmethod
    def create(cls, **values: Any) -> "BeatCoverageV1":
        raw_receipts = values.get("lane_receipts") or ()
        receipts = tuple(
            receipt
            if isinstance(receipt, BeatLaneTerminalReceiptV1)
            else BeatLaneTerminalReceiptV1.from_dict(receipt)
            for receipt in raw_receipts
        )
        receipts = tuple(
            receipt
            if receipt.receipt_digest
            else BeatLaneTerminalReceiptV1.create(**receipt.to_dict())
            for receipt in receipts
        )
        draft = cls(**{**values, "lane_receipts": receipts, "coverage_digest": ""})
        return replace(draft, coverage_digest=sha256_digest(draft.digest_payload()))

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("run_id", "workspace_id"):
            if not _nonblank(getattr(self, name)):
                errors.append(f"{name} is required")
        if self.contract_version not in _COVERAGE_CONTRACT_VERSIONS:
            errors.append("unsupported coverage contract_version")
        for name in ("package_digest", "plan_digest"):
            if not is_digest(getattr(self, name)):
                errors.append(f"{name} must be a sha256 digest")
        if (
            isinstance(self.expected_n_beats, bool)
            or not isinstance(self.expected_n_beats, int)
            or self.expected_n_beats < 1
        ):
            errors.append("expected_n_beats must be a positive integer")
        valid_n = (
            self.expected_n_beats
            if isinstance(self.expected_n_beats, int)
            and not isinstance(self.expected_n_beats, bool)
            and self.expected_n_beats > 0
            else 0
        )
        expected = list(range(valid_n))
        observed_indices = list(self.expected_beat_indices)
        if observed_indices != expected:
            errors.append(
                "expected_beat_indices must be exactly 0..N-1 without duplicates, "
                "holes, or out-of-range values"
            )

        required = tuple(self.required_lanes)
        if not required or any(not _nonblank(lane) for lane in required):
            errors.append("required_lanes must contain non-blank lane names")
        if len(required) != len(set(required)):
            errors.append("required_lanes contains duplicate lanes")
        for required_lane in DEFAULT_BEAT_COVERAGE_LANES_V1:
            if required_lane not in required:
                errors.append(f"required_lanes must include {required_lane}")

        seen: set[tuple[int, str]] = set()
        for receipt in self.lane_receipts:
            if not isinstance(receipt, BeatLaneTerminalReceiptV1):
                errors.append("lane_receipts must contain BeatLaneTerminalReceiptV1")
                continue
            errors.extend(f"lane receipt: {error}" for error in receipt.validate())
            key = (receipt.beat_index, receipt.lane)
            if key in seen:
                errors.append(f"duplicate lane receipt for beat {key[0]} lane {key[1]!r}")
            seen.add(key)
            if receipt.run_id != self.run_id:
                errors.append("lane receipt run_id does not match coverage")
            if receipt.workspace_id != self.workspace_id:
                errors.append("lane receipt workspace_id does not match coverage")
            if receipt.package_digest != self.package_digest:
                errors.append("lane receipt package_digest does not match coverage")
            if receipt.plan_digest != self.plan_digest:
                errors.append("lane receipt plan_digest does not match coverage")
            if not isinstance(receipt.beat_index, int) or isinstance(receipt.beat_index, bool):
                continue
            if receipt.beat_index < 0 or receipt.beat_index >= valid_n:
                errors.append(f"lane receipt beat_index {receipt.beat_index} out of range")

        expected_pairs = {
            (beat_index, lane)
            for beat_index in expected
            for lane in required
        }
        missing = sorted(expected_pairs - seen)
        if missing:
            errors.append(f"missing lane receipts: {missing}")
        if len(seen) != len(self.lane_receipts):
            # Keep the duplicate diagnostic above, but ensure malformed entries
            # cannot make the terminal receipt appear complete.
            errors.append("lane receipt coverage contains duplicate keys")

        if not is_digest(self.coverage_digest):
            errors.append("coverage_digest must be a sha256 digest")
        elif self.coverage_digest != sha256_digest(self.digest_payload()):
            errors.append("coverage_digest does not match coverage payload")
        return errors

    def assert_valid(self) -> "BeatCoverageV1":
        errors = self.validate()
        if errors:
            raise ValueError("BeatCoverageV1 invalid: " + "; ".join(errors))
        return self


# The two names describe the same terminal payload.  Keeping both names lets
# Star call the receipt by its fan-in role while Contracts callers use the
# shorter coverage name, without creating two divergent digest formats.
SerialFanInReceiptV1 = BeatCoverageV1
BeatTerminalReceiptV1 = BeatLaneTerminalReceiptV1
SerialFanInLaneReceiptV1 = BeatLaneTerminalReceiptV1
LaneTerminalReceiptV1 = BeatLaneTerminalReceiptV1

create_serial_fan_in_receipt_v1 = BeatCoverageV1.create
build_beat_coverage_v1 = BeatCoverageV1.create
build_serial_fan_in_receipt_v1 = BeatCoverageV1.create


__all__ = [
    "BEAT_COVERAGE_CONTRACT_VERSION_V1",
    "SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1",
    "BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1",
    "DEFAULT_BEAT_COVERAGE_LANES_V1",
    "TERMINAL_BEAT_LANE_STATUSES_V1",
    "BeatLaneTerminalReceiptV1",
    "BeatTerminalReceiptV1",
    "SerialFanInLaneReceiptV1",
    "LaneTerminalReceiptV1",
    "BeatCoverageV1",
    "SerialFanInReceiptV1",
    "create_serial_fan_in_receipt_v1",
    "build_beat_coverage_v1",
    "build_serial_fan_in_receipt_v1",
]
