"""Strict Ares XL V1 script artifacts and approval bindings.

This module is persistence-neutral. Ares assembles semantic artifacts,
Atropos persists append-only revisions, Star owns approval state and resume,
and Studio forwards authenticated commands.

An :class:`AresApprovalReceiptV1` is evidence, not a bearer credential. A
consumer MUST call ``authorizes(..., resolver=...)`` so a durable authority can
confirm the receipt is current, unrevoked, and bound to the active factory and
state revisions. Cryptographic signing belongs to that persistence/resolver
boundary and is intentionally outside this value-contract module.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
import re
from types import MappingProxyType
from typing import Annotated, Any, Literal, Mapping, Protocol
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from .factory.digest import canonical_json, sha256_digest


_FROZEN_STRICT = ConfigDict(
    frozen=True,
    extra="forbid",
    strict=True,
    revalidate_instances="always",
)
_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_JSON_SAFE_INTEGER_MAX = 9_007_199_254_740_991
_PG_INT4_MAX = 2_147_483_647
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")

def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("string must not be blank")
    return value


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonBlankStr = Annotated[str, AfterValidator(_non_blank)]
UuidStr = Annotated[str, AfterValidator(lambda value: _valid_uuid(value))]
DigestStr = Annotated[str, AfterValidator(lambda value: _valid_digest(value))]
NonNegativeInt = Annotated[int, Field(ge=0, le=_JSON_SAFE_INTEGER_MAX)]
DbRevisionInt = Annotated[int, Field(ge=0, le=_PG_INT4_MAX)]
ExpectedStateRevisionInt = Annotated[int, Field(ge=1, lt=_PG_INT4_MAX)]
ApprovedStateRevisionInt = Annotated[int, Field(ge=2, le=_PG_INT4_MAX)]
ApprovalKind = Literal["script", "production_plan"]


class _FrozenMapping(Mapping[str, Any]):
    """Immutable mapping with no ``dict`` mutation backdoor."""

    __slots__ = ("_data",)

    def __init__(self, value: Mapping[str, Any]) -> None:
        object.__setattr__(
            self,
            "_data",
            MappingProxyType(dict(value)),
        )

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return repr(dict(self._data))

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("frozen contract mapping cannot be mutated")


def _valid_uuid(value: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("identifier must be a UUID") from exc
    if value != str(parsed):
        raise ValueError("identifier must use canonical lowercase UUID form")
    return value


def _valid_digest(value: str) -> str:
    if _DIGEST_RE.fullmatch(value) is None:
        raise ValueError("digest must be sha256:<64 lowercase hex>")
    return value


def _parse_utc(value: str) -> datetime:
    if not _UTC_RE.fullmatch(value):
        raise ValueError("timestamp must be an ISO-8601 UTC value ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp is not a valid calendar value") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return parsed


def _valid_utc(value: str) -> str:
    _parse_utc(value)
    return value


UtcTimestamp = Annotated[str, AfterValidator(_valid_utc)]


def _validate_json(value: Any, path: str = "value") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError(f"{path} contains an unpaired Unicode surrogate")
        return
    if isinstance(value, int):
        if abs(value) > _JSON_SAFE_INTEGER_MAX:
            raise ValueError(f"{path} contains an integer outside the JSON safe range")
        return
    if isinstance(value, float):
        raise ValueError(
            f"{path} contains a float; digest-bearing numbers must be safe integers"
        )
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string key")
            _validate_json(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} contains non-JSON value {type(value).__name__}")


def _deep_freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenMapping(
            {key: _deep_freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze_json(item) for item in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_contract_json_v1(
    value: BaseModel | Mapping[str, Any],
    *,
    exclude: frozenset[str] | set[str] | tuple[str, ...] = (),
) -> str:
    """Exact canonical JSON text with optional top-level fields omitted."""

    payload = _json_value(value)
    if not isinstance(payload, dict):
        raise TypeError("contract input must be a model or mapping")
    excluded = set(exclude)
    canonical_payload = {
        key: item for key, item in payload.items() if key not in excluded
    }
    _validate_json(canonical_payload, "contract")
    return canonical_json(canonical_payload)


def canonical_contract_digest_v1(
    value: BaseModel | Mapping[str, Any],
    *,
    exclude: frozenset[str] | set[str] | tuple[str, ...] = (),
) -> str:
    """Canonical JSON SHA-256 with optional top-level fields omitted."""

    payload = _json_value(value)
    if not isinstance(payload, dict):
        raise TypeError("contract digest input must be a model or mapping")
    excluded = set(exclude)
    digest_payload = {
        key: item for key, item in payload.items() if key not in excluded
    }
    _validate_json(digest_payload, "contract")
    return sha256_digest(digest_payload)


class AresScriptSegmentV1(BaseModel):
    """Actual DB segment shape used by voice_script and caption_script."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    text: str


class AresSceneDirectionV1(BaseModel):
    """Normalized Ares scene prose; no alternate keys are accepted."""

    model_config = _FROZEN_STRICT

    shot: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
    subject: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=500)
    ]
    setting: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=300)
    ]
    overlay: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=200)
    ]


class AresBeatV1(BaseModel):
    """One ordered production beat with mandatory spoken dialogue and direction."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    text: NonBlankStr
    caption: str
    scene_direction: AresSceneDirectionV1


class ScriptPackageV1(BaseModel):
    """Complete approved Ares script candidate, losslessly bound by digest."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptPackage.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    candidate_id: UuidStr
    factory_revision: DbRevisionInt
    master_sales_script: Mapping[str, Any]
    voice_script: tuple[AresScriptSegmentV1, ...]
    caption_script: tuple[AresScriptSegmentV1, ...]
    pronunciation_overrides: Mapping[NonEmptyStr, NonEmptyStr]
    package_digest: DigestStr

    @field_validator("voice_script", "caption_script", mode="before")
    @classmethod
    def _segments_to_tuples(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("master_sales_script", mode="after")
    @classmethod
    def _validate_and_freeze_master(
        cls, value: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        if not value:
            raise ValueError("master_sales_script must not be empty")
        _validate_json(value, "master_sales_script")
        return _deep_freeze_json(value)

    @field_validator("pronunciation_overrides", mode="before")
    @classmethod
    def _reject_normalized_pronunciation_key_collisions(
        cls, value: Any
    ) -> Any:
        if isinstance(value, Mapping):
            normalized: set[str] = set()
            for key in value:
                if not isinstance(key, str):
                    continue
                stripped = key.strip()
                if stripped in normalized:
                    raise ValueError(
                        "pronunciation override keys must be unique after trimming"
                    )
                normalized.add(stripped)
        return value

    @field_validator("pronunciation_overrides", mode="after")
    @classmethod
    def _freeze_pronunciation_overrides(
        cls, value: Mapping[str, str]
    ) -> Mapping[str, str]:
        return _FrozenMapping(value)

    @field_serializer(
        "master_sales_script",
        "pronunciation_overrides",
        when_used="always",
    )
    def _serialize_frozen_mappings(self, value: Mapping[str, Any]) -> dict:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_content(self) -> "ScriptPackageV1":
        count = len(self.voice_script)
        if count == 0:
            raise ValueError("voice_script must contain at least one segment")
        if len(self.caption_script) != count:
            raise ValueError(
                "voice_script and caption_script must have equal length"
            )
        expected_indices = list(range(count))
        voice_indices = [segment.beat_index for segment in self.voice_script]
        caption_indices = [segment.beat_index for segment in self.caption_script]
        if voice_indices != expected_indices:
            raise ValueError("voice_script beat indices must be exactly 0..N-1")
        if caption_indices != expected_indices:
            raise ValueError("caption_script beat indices must be exactly 0..N-1")
        if voice_indices != caption_indices:
            raise ValueError("voice/caption segment indices must match")
        if any(not segment.text.strip() for segment in self.voice_script):
            raise ValueError("voice_script segments must contain non-empty dialogue")
        expected = canonical_contract_digest_v1(
            self, exclude={"package_digest"}
        )
        if self.package_digest != expected:
            raise ValueError("package_digest does not match ScriptPackage payload")
        return self


class BeatPlanV1(BaseModel):
    """Ordered production plan bound to one approved ScriptPackage digest."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresBeatPlan.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    script_revision_id: UuidStr
    factory_revision: DbRevisionInt
    script_package_digest: DigestStr
    beats: tuple[AresBeatV1, ...]
    production_plan: Mapping[str, Any]
    plan_digest: DigestStr

    @field_validator("beats", mode="before")
    @classmethod
    def _beats_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("production_plan", mode="after")
    @classmethod
    def _validate_and_freeze_production_plan(
        cls, value: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        if not value:
            raise ValueError("production_plan must not be empty")
        _validate_json(value, "production_plan")
        return _deep_freeze_json(value)

    @field_serializer("production_plan", when_used="always")
    def _serialize_production_plan(
        self, value: Mapping[str, Any]
    ) -> dict[str, Any]:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_content(self) -> "BeatPlanV1":
        if not self.beats:
            raise ValueError("beats must contain at least one beat")
        indices = [beat.beat_index for beat in self.beats]
        if indices != list(range(len(indices))):
            raise ValueError("beat indices must be exactly 0..N-1 in array order")
        expected = canonical_contract_digest_v1(self, exclude={"plan_digest"})
        if self.plan_digest != expected:
            raise ValueError("plan_digest does not match BeatPlan payload")
        return self


class AresScriptRevisionV1(BaseModel):
    """Append-only ScriptPackage revision; first approval-gate subject."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptRevision.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    candidate_id: UuidStr
    factory_revision: DbRevisionInt
    script_package: ScriptPackageV1
    revision_digest: DigestStr

    @model_validator(mode="after")
    def _bind_artifact(self) -> "AresScriptRevisionV1":
        for field in (
            "workspace_id",
            "run_id",
            "revision_id",
            "factory_revision",
        ):
            if getattr(self.script_package, field) != getattr(self, field):
                raise ValueError(f"script_package.{field} does not match revision")
        if self.script_package.candidate_id != self.candidate_id:
            raise ValueError("script_package.candidate_id does not match revision")
        expected = canonical_contract_digest_v1(
            self, exclude={"revision_digest"}
        )
        if self.revision_digest != expected:
            raise ValueError("revision_digest does not match script revision payload")
        return self


class AresBeatPlanRevisionV1(BaseModel):
    """Append-only BeatPlan revision bound to an approved ScriptPackage digest."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresBeatPlanRevision.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    script_revision_id: UuidStr
    factory_revision: DbRevisionInt
    approved_script_package_digest: DigestStr
    beat_plan: BeatPlanV1
    revision_digest: DigestStr

    @model_validator(mode="after")
    def _bind_artifact(self) -> "AresBeatPlanRevisionV1":
        for field in (
            "workspace_id",
            "run_id",
            "revision_id",
            "script_revision_id",
            "factory_revision",
        ):
            if getattr(self.beat_plan, field) != getattr(self, field):
                raise ValueError(f"beat_plan.{field} does not match plan revision")
        if (
            self.beat_plan.script_package_digest
            != self.approved_script_package_digest
        ):
            raise ValueError(
                "beat_plan.script_package_digest does not match "
                "approved_script_package_digest"
            )
        expected = canonical_contract_digest_v1(
            self, exclude={"revision_digest"}
        )
        if self.revision_digest != expected:
            raise ValueError("revision_digest does not match plan revision payload")
        return self

    def binds_script_revision(self, revision: AresScriptRevisionV1) -> bool:
        if not (
            self.workspace_id == revision.workspace_id
            and self.run_id == revision.run_id
            and self.script_revision_id == revision.revision_id
            and self.factory_revision == revision.factory_revision
            and self.approved_script_package_digest
            == revision.script_package.package_digest
            and len(self.beat_plan.beats)
            == len(revision.script_package.voice_script)
        ):
            return False
        for position, beat in enumerate(self.beat_plan.beats):
            if beat.text != revision.script_package.voice_script[position].text:
                return False
            if beat.caption != revision.script_package.caption_script[position].text:
                return False
        return True


def derive_ares_g1_subject_digest_v1(
    target_profile_digest: str,
    identity_lock_digest: str,
    script_package_digest: str,
    beat_plan_digest: str,
) -> str:
    """Bind all four mandatory G1 semantic subjects in canonical order."""

    values = {
        "target_profile_digest": target_profile_digest,
        "identity_lock_digest": identity_lock_digest,
        "script_package_digest": script_package_digest,
        "beat_plan_digest": beat_plan_digest,
    }
    for field, value in values.items():
        if _DIGEST_RE.fullmatch(value) is None:
            raise ValueError(f"{field} must be sha256:<64 lowercase hex>")
    return sha256_digest(values)


class AresApprovalCommandV1(BaseModel):
    """Authenticated intent to approve one exact revision artifact."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresApprovalCommand.v1"]
    command_id: NonEmptyStr
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    approval_kind: ApprovalKind
    artifact_digest: DigestStr
    target_profile_digest: DigestStr
    identity_lock_digest: DigestStr
    script_package_digest: DigestStr
    beat_plan_digest: DigestStr | None
    g1_subject_digest: DigestStr | None
    approver_account_id: NonEmptyStr
    policy_version: NonEmptyStr
    factory_revision: DbRevisionInt
    expected_state_revision: ExpectedStateRevisionInt
    issued_at_utc: UtcTimestamp
    command_digest: DigestStr

    @model_validator(mode="after")
    def _bind_content(self) -> "AresApprovalCommandV1":
        if self.approval_kind == "script":
            if (
                self.artifact_digest != self.script_package_digest
                or self.beat_plan_digest is not None
                or self.g1_subject_digest is not None
            ):
                raise ValueError(
                    "script approval must bind only the ScriptPackage artifact"
                )
        else:
            if self.beat_plan_digest is None or self.g1_subject_digest is None:
                raise ValueError(
                    "production approval requires BeatPlan and G1 subject digests"
                )
            expected_g1 = derive_ares_g1_subject_digest_v1(
                self.target_profile_digest,
                self.identity_lock_digest,
                self.script_package_digest,
                self.beat_plan_digest,
            )
            if (
                self.g1_subject_digest != expected_g1
                or self.artifact_digest != expected_g1
            ):
                raise ValueError(
                    "production approval artifact must equal the four-digest G1 subject"
                )
        expected = canonical_contract_digest_v1(
            self, exclude={"command_digest"}
        )
        if self.command_digest != expected:
            raise ValueError("command_digest does not match ApprovalCommand payload")
        return self

    def binds_revision(
        self,
        revision: AresScriptRevisionV1 | AresBeatPlanRevisionV1,
        *,
        approved_script_revision: AresScriptRevisionV1 | None = None,
    ) -> bool:
        if self.approval_kind == "script":
            if not isinstance(revision, AresScriptRevisionV1):
                return False
            expected_artifact = revision.script_package.package_digest
            constituent_match = (
                self.script_package_digest == expected_artifact
                and self.beat_plan_digest is None
                and self.g1_subject_digest is None
            )
        else:
            if not isinstance(revision, AresBeatPlanRevisionV1):
                return False
            if (
                approved_script_revision is None
                or not revision.binds_script_revision(approved_script_revision)
            ):
                return False
            expected_artifact = self.g1_subject_digest
            constituent_match = (
                self.script_package_digest
                == revision.approved_script_package_digest
                and self.beat_plan_digest == revision.beat_plan.plan_digest
                and self.g1_subject_digest
                == derive_ares_g1_subject_digest_v1(
                    self.target_profile_digest,
                    self.identity_lock_digest,
                    self.script_package_digest,
                    self.beat_plan_digest,
                )
            )
        return (
            constituent_match
            and expected_artifact is not None
            and self.workspace_id == revision.workspace_id
            and self.run_id == revision.run_id
            and self.revision_id == revision.revision_id
            and self.artifact_digest == expected_artifact
            and self.factory_revision == revision.factory_revision
        )


class AresApprovalBeginCommandV1(BaseModel):
    """Star intent to open the script gate for one selected candidate."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresApprovalBeginCommand.v1"]
    command_id: NonEmptyStr
    workspace_id: UuidStr
    run_id: UuidStr
    candidate_id: UuidStr
    requester_account_id: NonEmptyStr
    policy_version: NonEmptyStr
    factory_revision: DbRevisionInt
    expected_state_revision: Literal[0]
    issued_at_utc: UtcTimestamp
    command_digest: DigestStr

    @model_validator(mode="after")
    def _bind_content(self) -> "AresApprovalBeginCommandV1":
        expected = canonical_contract_digest_v1(
            self, exclude={"command_digest"}
        )
        if self.command_digest != expected:
            raise ValueError(
                "command_digest does not match ApprovalBeginCommand payload"
            )
        return self


class AresApprovalResolverV1(Protocol):
    """Durable authority required to resolve current receipt state."""

    def is_current_approval(
        self,
        *,
        receipt_id: str,
        command_id: str,
        workspace_id: str,
        factory_revision: int,
        state_revision: int,
        policy_version: str,
        receipt_digest: str,
        command_digest: str,
        run_id: str,
        revision_id: str,
        approval_kind: ApprovalKind,
        artifact_digest: str,
        approver_account_id: str,
        target_profile_digest: str,
        identity_lock_digest: str,
        script_package_digest: str,
        beat_plan_digest: str | None,
        g1_subject_digest: str | None,
    ) -> bool: ...


class AresApprovalReceiptV1(BaseModel):
    """Approval evidence that requires a durable resolver before authorization."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresApprovalReceipt.v1"]
    receipt_id: NonEmptyStr
    command_id: NonEmptyStr
    command_digest: DigestStr
    workspace_id: UuidStr
    run_id: UuidStr
    revision_id: UuidStr
    approval_kind: ApprovalKind
    artifact_digest: DigestStr
    target_profile_digest: DigestStr
    identity_lock_digest: DigestStr
    script_package_digest: DigestStr
    beat_plan_digest: DigestStr | None
    g1_subject_digest: DigestStr | None
    approver_account_id: NonEmptyStr
    decision: Literal["approved"]
    policy_version: NonEmptyStr
    factory_revision: DbRevisionInt
    state_revision: ApprovedStateRevisionInt
    approved_at_utc: UtcTimestamp
    expires_at_utc: UtcTimestamp
    revoked_at_utc: UtcTimestamp | None
    transaction_audit_id: NonEmptyStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_content(self) -> "AresApprovalReceiptV1":
        if self.transaction_audit_id != self.receipt_id:
            raise ValueError("transaction_audit_id must equal receipt_id")
        if self.approval_kind == "script":
            if (
                self.artifact_digest != self.script_package_digest
                or self.beat_plan_digest is not None
                or self.g1_subject_digest is not None
            ):
                raise ValueError(
                    "script receipt must bind only the ScriptPackage artifact"
                )
        else:
            if self.beat_plan_digest is None or self.g1_subject_digest is None:
                raise ValueError(
                    "production receipt requires BeatPlan and G1 subject digests"
                )
            expected_g1 = derive_ares_g1_subject_digest_v1(
                self.target_profile_digest,
                self.identity_lock_digest,
                self.script_package_digest,
                self.beat_plan_digest,
            )
            if (
                self.g1_subject_digest != expected_g1
                or self.artifact_digest != expected_g1
            ):
                raise ValueError(
                    "production receipt artifact must equal the four-digest G1 subject"
                )
        approved_at = _parse_utc(self.approved_at_utc)
        expires_at = _parse_utc(self.expires_at_utc)
        if expires_at <= approved_at:
            raise ValueError("expires_at_utc must follow approved_at_utc")
        if self.revoked_at_utc is not None:
            revoked_at = _parse_utc(self.revoked_at_utc)
            if revoked_at < approved_at:
                raise ValueError("revoked_at_utc cannot precede approved_at_utc")
            if revoked_at > expires_at:
                raise ValueError("revoked_at_utc cannot follow expires_at_utc")
        expected = canonical_contract_digest_v1(
            self, exclude={"receipt_digest"}
        )
        if self.receipt_digest != expected:
            raise ValueError("receipt_digest does not match ApprovalReceipt payload")
        return self

    def structurally_binds(
        self,
        command: AresApprovalCommandV1,
        revision: AresScriptRevisionV1 | AresBeatPlanRevisionV1,
        *,
        approved_script_revision: AresScriptRevisionV1 | None = None,
    ) -> bool:
        """Check immutable fields only; this does NOT authorize use."""

        return (
            command.binds_revision(
                revision,
                approved_script_revision=approved_script_revision,
            )
            and self.command_id == command.command_id
            and self.command_digest == command.command_digest
            and self.workspace_id == command.workspace_id
            and self.run_id == command.run_id
            and self.revision_id == command.revision_id
            and self.approval_kind == command.approval_kind
            and self.artifact_digest == command.artifact_digest
            and self.target_profile_digest == command.target_profile_digest
            and self.identity_lock_digest == command.identity_lock_digest
            and self.script_package_digest == command.script_package_digest
            and self.beat_plan_digest == command.beat_plan_digest
            and self.g1_subject_digest == command.g1_subject_digest
            and self.approver_account_id == command.approver_account_id
            and self.policy_version == command.policy_version
            and self.factory_revision == command.factory_revision
            and self.state_revision == command.expected_state_revision + 1
        )

    def authorizes(
        self,
        command: AresApprovalCommandV1,
        revision: AresScriptRevisionV1 | AresBeatPlanRevisionV1,
        *,
        at_utc: str,
        resolver: AresApprovalResolverV1,
        approved_script_revision: AresScriptRevisionV1 | None = None,
    ) -> bool:
        """Authorize only after resolving current durable state.

        The receipt value alone is never sufficient authority. Resolver errors
        intentionally propagate so callers cannot mistake an unavailable
        authority for approval.
        """

        if not self.structurally_binds(
            command,
            revision,
            approved_script_revision=approved_script_revision,
        ):
            return False
        approved_at = _parse_utc(self.approved_at_utc)
        if approved_at < _parse_utc(command.issued_at_utc):
            return False
        at = _parse_utc(at_utc)
        if at < approved_at or at >= _parse_utc(self.expires_at_utc):
            return False
        if self.revoked_at_utc is not None:
            return False
        return resolver.is_current_approval(
            receipt_id=self.receipt_id,
            command_id=self.command_id,
            workspace_id=self.workspace_id,
            factory_revision=self.factory_revision,
            state_revision=self.state_revision,
            policy_version=self.policy_version,
            receipt_digest=self.receipt_digest,
            command_digest=self.command_digest,
            run_id=self.run_id,
            revision_id=self.revision_id,
            approval_kind=self.approval_kind,
            artifact_digest=self.artifact_digest,
            approver_account_id=self.approver_account_id,
            target_profile_digest=self.target_profile_digest,
            identity_lock_digest=self.identity_lock_digest,
            script_package_digest=self.script_package_digest,
            beat_plan_digest=self.beat_plan_digest,
            g1_subject_digest=self.g1_subject_digest,
        )


__all__ = [
    "AresApprovalBeginCommandV1",
    "AresApprovalCommandV1",
    "AresApprovalReceiptV1",
    "AresApprovalResolverV1",
    "AresBeatPlanRevisionV1",
    "AresBeatV1",
    "AresSceneDirectionV1",
    "AresScriptRevisionV1",
    "AresScriptSegmentV1",
    "BeatPlanV1",
    "ScriptPackageV1",
    "canonical_contract_json_v1",
    "canonical_contract_digest_v1",
    "derive_ares_g1_subject_digest_v1",
]
