"""Provider-neutral execution contract for domain logic.

This module defines the interface that any execution backend (Modal, Temporal, Lambda, etc.)
must implement. Domain logic imports ONLY from this module; runtime_adapters/ implement it.

PRD PR-2: ExecutionBackend contract + attempt ledger + transactional outbox.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


# === Status and Result Types ===


OperationStatusType = Literal["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled", "unknown"]


@dataclass(frozen=True)
class OperationRef:
    """Handle to a submitted operation (provider-neutral).

    Attributes:
        operation_id: Unique operation ID (stable across attempts).
        provider: Execution provider (e.g., "modal", "temporal", "lambda").
        call_id: Provider-specific call/job ID (may change on retry).
    """
    operation_id: str
    provider: str
    call_id: str


@dataclass(frozen=True)
class OperationStatus:
    """Current status of an operation.

    Attributes:
        operation_id: Unique operation ID.
        status: One of {queued, running, succeeded, failed, cancel_requested, cancelled, unknown}.
        attempt_no: Current attempt number (1-based).
        started_at: Timestamp when attempt started (None if queued).
        completed_at: Timestamp when operation completed (None if still running).
        error_message: Failure reason (None if successful).
        provider_error_code: Provider-specific error code for debugging (None if no error).
        metadata: Additional provider-specific data (side effect phase, revision, etc.).
    """
    operation_id: str
    status: OperationStatusType
    attempt_no: int = 1
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    provider_error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CancelResult:
    """Result of a cancel operation.

    Attributes:
        operation_id: Unique operation ID.
        was_running: True if operation was running when cancel was requested.
        side_effect_phase: Where side effects were when cancel took effect.
            - none: No side effects committed
            - started: Side effects began but may not be complete
            - committed: Side effects are durable (compensation workflow required)
        compensation_workflow: Name of workflow to clean up side effects (if phase=committed).
        cancelled_at: Timestamp of cancellation.
    """
    operation_id: str
    was_running: bool
    side_effect_phase: Literal["none", "started", "committed"]
    compensation_workflow: str | None = None
    cancelled_at: datetime | None = None


# === Job Envelope (PRD 5.2 minimum fields) ===


@dataclass(frozen=True)
class RouteSnapshot:
    """Immutable routing info captured at operation creation (never changes on retry).

    Attributes:
        provider: Execution backend (e.g., "modal", "temporal").
        target_kind: Function/workflow kind (e.g., "voiceover", "visual", "compose").
        target_resource: Fully qualified resource ID (e.g., "app.voiceover_run").
        artifact_digest: SHA256 of target code/config (for cache invalidation).
        spec_digest: SHA256 of operation spec/parameters (for idempotency).
    """
    provider: str
    target_kind: str
    target_resource: str
    artifact_digest: str
    spec_digest: str


@dataclass(frozen=True)
class JobEnvelope:
    """Complete operation input contract (PRD 5.2 + attempt ledger binding).

    Attributes:
        operation_id: Unique operation ID (stable across retries + attempts).
        job_id: Business-level job ID (e.g., run_id in hiob).
        node_id: Logical node/step in orchestration graph (e.g., "voice", "visual").
        contract_version: Contract schema version for forward compatibility.
        workspace_id: Multi-tenant isolation key (e.g., brand slug).
        input_uri: S3/R2 path to input data (if large).
        output_uri: S3/R2 path where output should land.
        image_digest: Container image SHA256 (for L4 audit trail).
        idempotency_key: Token for end-to-end idempotency (unchanged across retries).
        trace_id: Distributed trace ID (from studio/orchestrator).
        deadline_at: Absolute deadline (operation fails if exceeded).
        route_snapshot: Immutable routing (fixed at creation, same on all retries).
        parameters: Execution parameters (passed to target function).
        attributes: Extra metadata (not used for routing/idempotency).
    """
    operation_id: str
    job_id: str
    node_id: str
    contract_version: str
    workspace_id: str
    input_uri: str | None
    output_uri: str | None
    image_digest: str
    idempotency_key: str
    trace_id: str
    deadline_at: datetime | None
    route_snapshot: RouteSnapshot
    parameters: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Ensure minimum required fields are present."""
        required = [
            self.operation_id, self.job_id, self.node_id, self.contract_version,
            self.workspace_id, self.image_digest, self.idempotency_key, self.trace_id,
            self.route_snapshot,
        ]
        for field_val in required:
            if field_val is None or (isinstance(field_val, str) and not field_val.strip()):
                raise ValueError(f"JobEnvelope missing required field: {field_val}")


# === Attempt Ledger (DUR-01: append-only) ===


@dataclass(frozen=True)
class ExecutionAttempt:
    """Record of a single execution attempt (immutable log entry).

    Attributes:
        operation_id: Parent operation ID.
        attempt_no: Attempt number (1-based).
        execution_provider: Backend that executed this attempt.
        provider_call_id: Backend-specific call/job ID.
        revision: Retryable state revision (e.g., artifact digest).
        started_at: When attempt started.
        completed_at: When attempt finished (None if still running).
        status: Outcome status (queued, running, succeeded, failed, etc.).
        error_code: Provider error code (if failed).
        error_message: Human-readable error (if failed).
    """
    operation_id: str
    attempt_no: int
    execution_provider: str
    provider_call_id: str
    revision: str
    started_at: datetime
    completed_at: datetime | None = None
    status: OperationStatusType = "queued"
    error_code: str | None = None
    error_message: str | None = None


# === Contract Errors ===


class ExecutionContractError(Exception):
    """Base error for execution backend violations."""
    pass


class ProviderError(ExecutionContractError):
    """Provider-specific error (normalized to contract errors)."""
    pass


class IdempotencyError(ExecutionContractError):
    """Idempotency conflict (same request already processed)."""
    pass


class DeadlineExceededError(ExecutionContractError):
    """Operation deadline exceeded."""
    pass


class UnknownOperationError(ExecutionContractError):
    """Operation not found (not failure, not re-run authorization)."""
    pass


# === Transactional Outbox (DUR-01) ===


@dataclass(frozen=True)
class OutboxEntry:
    """Durable record for transactional outbox (operation + route snapshot committed together).

    This is a write-ahead log entry. The operation is persisted BEFORE any invocation.
    On success, a corresponding completion event is written. Consumers use this for
    exactly-once semantics.

    Attributes:
        operation_id: Unique operation ID.
        job_id: Business-level job ID.
        envelope: Complete JobEnvelope (persisted before execution).
        outbox_status: "pending" (not yet acked), "published" (acked to bus), "completed" (finished).
        created_at: When outbox entry was written.
        published_at: When acked to event bus (None if still pending).
        completed_at: When operation finished (None if still running).
    """
    operation_id: str
    job_id: str
    envelope: JobEnvelope
    outbox_status: Literal["pending", "published", "completed"] = "pending"
    created_at: datetime | None = None
    published_at: datetime | None = None
    completed_at: datetime | None = None


# === ExecutionBackend Protocol (ABC) ===


class ExecutionBackend(ABC):
    """Provider-neutral interface for executing operations.

    All implementations MUST:
    - Preserve existing behavior (Modal adapter is the reference)
    - Fix route snapshot at operation creation (never change on retry)
    - Normalize provider errors to contract errors
    - Support idempotency via idempotency_key
    - Record attempts in append-only ledger
    - NOT cross-provider fallback (one envelope = one provider)
    - Handle unknown/cancel/side-effect-phase transitions per spec

    Domain code imports ONLY this module and calls these methods.
    Runtime adapters live in hiob-infra.runtime_adapters.
    """

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this backend is configured and available."""
        pass

    @abstractmethod
    def submit(
        self,
        envelope: JobEnvelope,
    ) -> OperationRef:
        """Submit an operation for execution.

        MUST:
        - Validate envelope
        - Persist envelope + route snapshot in durable outbox (DUR-01)
        - Invoke target function with parameters
        - Return operation_id immediately (do not wait for completion)

        On success, operation_id is stable across retries and attempts.
        On provider error, normalize to contract error type.

        Args:
            envelope: Complete operation definition.

        Returns:
            OperationRef with operation_id, provider, call_id.

        Raises:
            ExecutionContractError: If envelope invalid or provider unavailable.
            IdempotencyError: If idempotency_key already processed.
        """
        pass

    @abstractmethod
    def status(self, operation_id: str) -> OperationStatus:
        """Fetch current status of an operation.

        MUST:
        - Consult attempt ledger + provider for latest state
        - Return "unknown" if operation not found (NOT failure, NOT re-run)
        - Normalize provider status to canonical types
        - Include attempt_no, provider_error_code, side effect metadata

        Args:
            operation_id: Unique operation ID from submit().

        Returns:
            OperationStatus with current state.
        """
        pass

    @abstractmethod
    def cancel(self, operation_id: str) -> CancelResult:
        """Request cancellation of a running operation.

        MUST:
        - Mark operation as cancel_requested
        - If still running, halt execution
        - Record side_effect_phase (none/started/committed)
        - If committed side effects, emit compensation_workflow name
        - Return immediately (do not wait for full cancellation)

        Args:
            operation_id: Unique operation ID to cancel.

        Returns:
            CancelResult with cancellation details.
        """
        pass
