"""StageReceipt builder — terminal stage execution record.

PRD_BIG_FOOTSTEP phase 6: Every Planet stage execution must emit a
StageReceipt with terminal status (succeeded/failed/cancelled/superseded),
not just a spawn handle or 202 accepted. This builder ensures the receipt
is properly constructed with all required fields and validation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .stage_receipt import (
    StageReceipt,
    StageError,
    StageStatus,
)
from .digest import Digest


class StageReceiptBuilder:
    """Build StageReceipt envelopes for terminal stage execution records.

    A Stage Receipt records one Planet's execution of one semantic stage, with
    terminal status, input/output digests, and optional error details. Unlike
    spawn handles (202 accepted), a StageReceipt is a **terminal** record of
    what actually happened.
    """

    def __init__(
        self,
        *,
        operation_id: str,
        stage_id: str,
        planet: str,
        node_id: str,
        producer_revision: str,
        contract_version: str,
    ):
        self.operation_id = operation_id
        self.stage_id = stage_id
        self.planet = planet
        self.node_id = node_id
        self.producer_revision = producer_revision
        self.contract_version = contract_version

    def build_succeeded(
        self,
        *,
        output_digests: tuple[Digest, ...],
        input_digests: tuple[Digest, ...] = (),
        attempt_no: int = 1,
        started_at: str | None = None,
        warnings: tuple[str, ...] = (),
        cost: dict[str, Any] | None = None,
        image_digest: Digest | None = None,
    ) -> StageReceipt:
        """Build a successful (succeeded) stage receipt.

        Args:
            output_digests: Tuple of output artifact/payload digests (≥1 required).
            input_digests: Tuple of input digests (optional, defaults to empty).
            attempt_no: Attempt number (≥1).
            started_at: ISO 8601 timestamp of stage start (defaults to now).
            warnings: Tuple of warning messages (optional).
            cost: Cost metadata (optional).
            image_digest: Optional image digest for visual stages.

        Returns:
            Immutable StageReceipt with status="succeeded".
        Raises:
            ValueError: If output_digests is empty (succeeded requires at least one output).
        """
        if not output_digests:
            raise ValueError("succeeded stage must produce at least one output digest")

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        return StageReceipt(
            operation_id=self.operation_id,
            stage_id=self.stage_id,
            planet=self.planet,
            node_id=self.node_id,
            producer_revision=self.producer_revision,
            image_digest=image_digest,
            contract_version=self.contract_version,
            input_digests=input_digests,
            output_digests=output_digests,
            status="succeeded",
            attempt_no=attempt_no,
            started_at=started_at or now_iso,
            completed_at=now_iso,
            cost=cost,
            warnings=warnings,
            error=None,
        )

    def build_failed(
        self,
        *,
        error_code: str,
        error_message: str,
        retryable: bool = False,
        input_digests: tuple[Digest, ...] = (),
        attempt_no: int = 1,
        started_at: str | None = None,
        warnings: tuple[str, ...] = (),
        error_details: str = "",
        cost: dict[str, Any] | None = None,
        image_digest: Digest | None = None,
    ) -> StageReceipt:
        """Build a failed stage receipt.

        Args:
            error_code: Structured error code (e.g., "TIMEOUT", "LLAMA_ERROR").
            error_message: Human-readable error message.
            retryable: Whether the error is retryable by Star.
            input_digests: Tuple of input digests (optional).
            attempt_no: Attempt number (≥1).
            started_at: ISO 8601 timestamp of stage start (defaults to now).
            warnings: Tuple of warning messages (optional).
            error_details: Extended error details (optional).
            cost: Cost metadata (optional).
            image_digest: Optional image digest for visual stages.

        Returns:
            Immutable StageReceipt with status="failed" and error set.
        """
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        error = StageError(
            code=error_code,
            retryable=retryable,
            details=error_details,
        )
        return StageReceipt(
            operation_id=self.operation_id,
            stage_id=self.stage_id,
            planet=self.planet,
            node_id=self.node_id,
            producer_revision=self.producer_revision,
            image_digest=image_digest,
            contract_version=self.contract_version,
            input_digests=input_digests,
            output_digests=(),
            status="failed",
            attempt_no=attempt_no,
            started_at=started_at or now_iso,
            completed_at=now_iso,
            cost=cost,
            warnings=warnings,
            error=error,
        )

    def build_blocked(
        self,
        *,
        input_digests: tuple[Digest, ...] = (),
        attempt_no: int = 1,
        started_at: str | None = None,
        reason: str = "Execution was blocked by policy or gate",
        cost: dict[str, Any] | None = None,
        image_digest: Digest | None = None,
    ) -> StageReceipt:
        """Build a blocked stage receipt (terminal, not retryable).

        Args:
            input_digests: Tuple of input digests (optional).
            attempt_no: Attempt number (≥1).
            started_at: ISO 8601 timestamp of stage start (defaults to now).
            reason: Reason the stage was blocked.
            cost: Cost metadata (optional).
            image_digest: Optional image digest for visual stages.

        Returns:
            Immutable StageReceipt with status="cancelled" and error.
        """
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        error = StageError(
            code="BLOCKED",
            retryable=False,
            details=reason,
        )
        return StageReceipt(
            operation_id=self.operation_id,
            stage_id=self.stage_id,
            planet=self.planet,
            node_id=self.node_id,
            producer_revision=self.producer_revision,
            image_digest=image_digest,
            contract_version=self.contract_version,
            input_digests=input_digests,
            output_digests=(),
            status="cancelled",
            attempt_no=attempt_no,
            started_at=started_at or now_iso,
            completed_at=now_iso,
            cost=cost,
            warnings=(),
            error=error,
        )
