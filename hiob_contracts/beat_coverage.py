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
MAX_BEAT_COVERAGE_BEATS_V1 = 16

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
    return isinstance(value, str) and bool(value.strip())


def _strict_object(
    value: Any,
    *,
    name: str,
    accepted: set[str],
) -> dict[str, Any]:
    """Accept exactly one JSON-object shape without aliasing or coercion."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    unknown = set(value) - accepted
    if unknown:
        rendered = ", ".join(repr(item) for item in sorted(unknown, key=repr))
        raise ValueError(f"{name} contains unknown fields: {rendered}")
    return dict(value)


def _require_fields(
    value: dict[str, Any],
    *,
    name: str,
    required: set[str],
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{name} is missing required fields: {', '.join(missing)}")


def _require_string_fields(
    value: dict[str, Any],
    *,
    name: str,
    fields_to_check: tuple[str, ...],
) -> None:
    wrong = [field for field in fields_to_check if not isinstance(value[field], str)]
    if wrong:
        raise ValueError(f"{name} fields must be strings: {', '.join(wrong)}")


def _is_array(value: Any) -> bool:
    return isinstance(value, (list, tuple))


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
        data = _strict_object(
            value,
            name="BeatLaneTerminalReceiptV1",
            accepted={item.name for item in fields(cls)},
        )
        data.setdefault("status", "succeeded")
        data.setdefault("output_digest", None)
        data.setdefault(
            "contract_version", BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1
        )
        _require_fields(
            data,
            name="BeatLaneTerminalReceiptV1",
            required={
                "run_id",
                "workspace_id",
                "package_digest",
                "plan_digest",
                "beat_index",
                "lane",
                "receipt_digest",
            },
        )
        _require_string_fields(
            data,
            name="BeatLaneTerminalReceiptV1",
            fields_to_check=(
                "run_id",
                "workspace_id",
                "package_digest",
                "plan_digest",
                "lane",
                "status",
                "receipt_digest",
                "contract_version",
            ),
        )
        if isinstance(data["beat_index"], bool) or not isinstance(
            data["beat_index"], int
        ):
            raise ValueError("BeatLaneTerminalReceiptV1.beat_index must be an integer")
        if data["output_digest"] is not None and not isinstance(
            data["output_digest"], str
        ):
            raise ValueError(
                "BeatLaneTerminalReceiptV1.output_digest must be a string or null"
            )
        return cls(**data).assert_valid()

    @classmethod
    def create(cls, **values: Any) -> "BeatLaneTerminalReceiptV1":
        accepted = {item.name for item in fields(cls)}
        data = _strict_object(
            values,
            name="BeatLaneTerminalReceiptV1.create input",
            accepted=accepted,
        )
        data.pop("receipt_digest", None)
        draft = cls(**data, receipt_digest="")
        try:
            candidate = replace(
                draft,
                receipt_digest=sha256_digest(draft.digest_payload()),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "BeatLaneTerminalReceiptV1.create input cannot be canonically serialized"
            ) from exc
        return candidate.assert_valid()

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("run_id", "workspace_id", "lane"):
            value = getattr(self, name)
            if not isinstance(value, str):
                errors.append(f"{name} must be a string")
            elif not _nonblank(value):
                errors.append(f"{name} is required")
        if (
            not isinstance(self.contract_version, str)
            or self.contract_version
            != BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1
        ):
            errors.append("unsupported lane receipt contract_version")
        if isinstance(self.beat_index, bool) or not isinstance(self.beat_index, int):
            errors.append("beat_index must be an integer")
        elif self.beat_index < 0:
            errors.append("beat_index must be non-negative")
        for name in ("package_digest", "plan_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not is_digest(value):
                errors.append(f"{name} must be a sha256 digest")
        if self.output_digest is not None and (
            not isinstance(self.output_digest, str) or not is_digest(self.output_digest)
        ):
            errors.append("output_digest must be a sha256 digest when present")
        if not isinstance(self.status, str) or self.status not in TERMINAL_BEAT_LANE_STATUSES_V1:
            errors.append(f"status is not terminal: {self.status!r}")
        elif self.status != "succeeded":
            errors.append("lane receipt status must be succeeded")
        if not isinstance(self.receipt_digest, str) or not is_digest(self.receipt_digest):
            errors.append("receipt_digest must be a sha256 digest")
        else:
            try:
                expected_digest = sha256_digest(self.digest_payload())
            except (TypeError, ValueError):
                errors.append("lane receipt payload cannot be canonically serialized")
            else:
                if self.receipt_digest != expected_digest:
                    errors.append("receipt_digest does not match lane receipt payload")
        return errors

    def assert_valid(self) -> "BeatLaneTerminalReceiptV1":
        errors = self.validate()
        if errors:
            raise ValueError("BeatLaneTerminalReceiptV1 invalid: " + "; ".join(errors))
        return self


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
        data = _strict_object(
            value,
            name="BeatCoverageV1",
            accepted={item.name for item in fields(cls)},
        )
        data.setdefault("required_lanes", DEFAULT_BEAT_COVERAGE_LANES_V1)
        data.setdefault("contract_version", BEAT_COVERAGE_CONTRACT_VERSION_V1)
        _require_fields(
            data,
            name="BeatCoverageV1",
            required={
                "run_id",
                "workspace_id",
                "package_digest",
                "plan_digest",
                "expected_n_beats",
                "expected_beat_indices",
                "lane_receipts",
                "coverage_digest",
            },
        )
        _require_string_fields(
            data,
            name="BeatCoverageV1",
            fields_to_check=(
                "run_id",
                "workspace_id",
                "package_digest",
                "plan_digest",
                "coverage_digest",
                "contract_version",
            ),
        )
        if isinstance(data["expected_n_beats"], bool) or not isinstance(
            data["expected_n_beats"], int
        ):
            raise ValueError("BeatCoverageV1.expected_n_beats must be an integer")
        for field_name in ("expected_beat_indices", "lane_receipts", "required_lanes"):
            if not _is_array(data[field_name]):
                raise ValueError(f"BeatCoverageV1.{field_name} must be an array")
        if any(
            isinstance(index, bool) or not isinstance(index, int)
            for index in data["expected_beat_indices"]
        ):
            raise ValueError("BeatCoverageV1.expected_beat_indices must contain integers")
        if any(not isinstance(lane, str) for lane in data["required_lanes"]):
            raise ValueError("BeatCoverageV1.required_lanes must contain strings")
        try:
            receipts = tuple(
                receipt
                if isinstance(receipt, BeatLaneTerminalReceiptV1)
                else BeatLaneTerminalReceiptV1.from_dict(receipt)
                for receipt in data["lane_receipts"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("BeatCoverageV1.lane_receipts must contain receipts") from exc
        coverage = cls(
            **{
                **data,
                "expected_beat_indices": tuple(data["expected_beat_indices"]),
                "lane_receipts": receipts,
                "required_lanes": tuple(data["required_lanes"]),
            }
        )
        return coverage.assert_valid()

    @classmethod
    def create(cls, **values: Any) -> "BeatCoverageV1":
        data = _strict_object(
            values,
            name="BeatCoverageV1.create input",
            accepted={item.name for item in fields(cls)},
        )
        data.pop("coverage_digest", None)
        data.setdefault("required_lanes", DEFAULT_BEAT_COVERAGE_LANES_V1)
        data.setdefault("contract_version", BEAT_COVERAGE_CONTRACT_VERSION_V1)
        _require_fields(
            data,
            name="BeatCoverageV1.create input",
            required={
                "run_id",
                "workspace_id",
                "package_digest",
                "plan_digest",
                "expected_n_beats",
                "expected_beat_indices",
                "lane_receipts",
            },
        )
        for field_name in ("expected_beat_indices", "lane_receipts", "required_lanes"):
            if not _is_array(data[field_name]):
                raise ValueError(f"BeatCoverageV1.create input {field_name} must be an array")
        try:
            receipts = tuple(
                receipt.assert_valid()
                if isinstance(receipt, BeatLaneTerminalReceiptV1)
                else BeatLaneTerminalReceiptV1.create(**receipt)
                for receipt in data["lane_receipts"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("BeatCoverageV1.create input lane_receipts are invalid") from exc
        draft = cls(
            **{
                **data,
                "expected_beat_indices": tuple(data["expected_beat_indices"]),
                "lane_receipts": receipts,
                "required_lanes": tuple(data["required_lanes"]),
                "coverage_digest": "",
            }
        )
        try:
            candidate = replace(
                draft,
                coverage_digest=sha256_digest(draft.digest_payload()),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("BeatCoverageV1.create input cannot be canonically serialized") from exc
        return candidate.assert_valid()

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("run_id", "workspace_id"):
            value = getattr(self, name)
            if not isinstance(value, str):
                errors.append(f"{name} must be a string")
            elif not _nonblank(value):
                errors.append(f"{name} is required")
        if (
            not isinstance(self.contract_version, str)
            or self.contract_version not in _COVERAGE_CONTRACT_VERSIONS
        ):
            errors.append("unsupported coverage contract_version")
        for name in ("package_digest", "plan_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not is_digest(value):
                errors.append(f"{name} must be a sha256 digest")
        if (
            isinstance(self.expected_n_beats, bool)
            or not isinstance(self.expected_n_beats, int)
            or self.expected_n_beats < 1
            or self.expected_n_beats > MAX_BEAT_COVERAGE_BEATS_V1
        ):
            errors.append(
                "expected_n_beats must be an integer between 1 and "
                f"{MAX_BEAT_COVERAGE_BEATS_V1}"
            )
        valid_n = (
            self.expected_n_beats
            if isinstance(self.expected_n_beats, int)
            and not isinstance(self.expected_n_beats, bool)
            and 0 < self.expected_n_beats <= MAX_BEAT_COVERAGE_BEATS_V1
            else 0
        )
        expected = list(range(valid_n))
        if not _is_array(self.expected_beat_indices):
            errors.append("expected_beat_indices must be an array")
            observed_indices: list[Any] = []
        else:
            observed_indices = list(self.expected_beat_indices)
        if (
            any(
                isinstance(index, bool) or not isinstance(index, int)
                for index in observed_indices
            )
            or observed_indices != expected
        ):
            errors.append(
                "expected_beat_indices must be exactly 0..N-1 without duplicates, "
                "holes, or out-of-range values"
            )

        if not _is_array(self.required_lanes):
            errors.append("required_lanes must be an array")
            required: tuple[Any, ...] = ()
        else:
            required = tuple(self.required_lanes)
        if not required or any(not _nonblank(lane) for lane in required):
            errors.append("required_lanes must contain non-blank lane names")
        if any(not isinstance(lane, str) for lane in required):
            errors.append("required_lanes must contain strings")
        elif len(required) != len(set(required)):
            errors.append("required_lanes contains duplicate lanes")
        for required_lane in DEFAULT_BEAT_COVERAGE_LANES_V1:
            if required_lane not in required:
                errors.append(f"required_lanes must include {required_lane}")

        seen: set[tuple[int, str]] = set()
        if not _is_array(self.lane_receipts):
            errors.append("lane_receipts must be an array")
            lane_receipts: tuple[Any, ...] = ()
        else:
            lane_receipts = tuple(self.lane_receipts)
        for receipt in lane_receipts:
            if not isinstance(receipt, BeatLaneTerminalReceiptV1):
                errors.append("lane_receipts must contain BeatLaneTerminalReceiptV1")
                continue
            errors.extend(f"lane receipt: {error}" for error in receipt.validate())
            has_key = isinstance(receipt.beat_index, int) and not isinstance(
                receipt.beat_index, bool
            ) and isinstance(receipt.lane, str)
            if has_key:
                key = (receipt.beat_index, receipt.lane)
                if key in seen:
                    errors.append(
                        f"duplicate lane receipt for beat {key[0]} lane {key[1]!r}"
                    )
                seen.add(key)
            if receipt.run_id != self.run_id:
                errors.append("lane receipt run_id does not match coverage")
            if receipt.workspace_id != self.workspace_id:
                errors.append("lane receipt workspace_id does not match coverage")
            if receipt.package_digest != self.package_digest:
                errors.append("lane receipt package_digest does not match coverage")
            if receipt.plan_digest != self.plan_digest:
                errors.append("lane receipt plan_digest does not match coverage")
            if not has_key:
                continue
            if receipt.beat_index < 0 or receipt.beat_index >= valid_n:
                errors.append(f"lane receipt beat_index {receipt.beat_index} out of range")

        expected_pairs = (
            {
                (beat_index, lane)
                for beat_index in expected
                for lane in required
            }
            if all(isinstance(lane, str) for lane in required)
            else set()
        )
        missing = sorted(expected_pairs - seen)
        if missing:
            errors.append(f"missing lane receipts: {missing}")
        if len(seen) != len(lane_receipts):
            # Keep the duplicate diagnostic above, but ensure malformed entries
            # cannot make the terminal receipt appear complete.
            errors.append("lane receipt coverage contains duplicate keys")

        if not isinstance(self.coverage_digest, str) or not is_digest(self.coverage_digest):
            errors.append("coverage_digest must be a sha256 digest")
        else:
            try:
                expected_digest = sha256_digest(self.digest_payload())
            except (TypeError, ValueError, AttributeError):
                errors.append("coverage payload cannot be canonically serialized")
            else:
                if self.coverage_digest != expected_digest:
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
    "MAX_BEAT_COVERAGE_BEATS_V1",
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
