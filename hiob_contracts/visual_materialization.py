"""Immutable contracts for the Athena -> visual materialization boundary.

These V1 contracts keep asset ownership, per-beat composition, provider input
lineage, and semantic validation separate.  They are additive: legacy visual
contracts remain valid while producers migrate to this sealed path.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Iterator, Literal, Optional
import uuid

from .factory.digest import is_digest, sha256_digest


ReferenceOwner = Literal["parzifal", "artemis"]
ReferenceKind = Literal["character", "product", "evidence"]
CastRole = Literal["lead", "co_star", "product", "evidence"]
RoleRequirement = Literal["required", "optional", "forbidden"]
ApprovalStatus = Literal["approved", "draft", "revoked"]
MaterializationStatus = Literal[
    "planned", "generating", "uploaded", "committed", "failed"
]

VISUAL_CONTRACT_VERSION_V1 = "visual-materialization.v1"
VISUAL_CONTRACT_VERSION_V2 = "visual-materialization.v2"
SEEDREAM_V1_MAX_REFS = 5
# PiAPI Seedream 5.0 Pro task_type (not BytePlus ModelArk — business registration required).
SEEDREAM_5_PRO_MODEL_ID = "seedream-5-pro"
# Production transport SSOT: PiAPI. Legacy ModelArk receipts remain parseable but
# are not the allowed committed-path transport after founder transport lock.
SEEDREAM_V1_TRANSPORT = "piapi"
ALLOWED_V1_TRANSPORTS = frozenset({SEEDREAM_V1_TRANSPORT})
VISUAL_RENDER_MODES_V1 = frozenset({
    "persona_talk",
    "duet",
    "hands_demo",
    "product_solo",
    "social_proof",
    "scene_no_person",
    "situation_pov",
    "before_after",
})


class _FrozenJsonMapping(Mapping[str, Any]):
    """Tuple-backed immutable JSON mapping safe for copy and pickle."""

    __slots__ = ("_items",)
    _items: tuple[tuple[str, Any], ...]

    def __init__(self, value: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_items", tuple(value.items()))

    def __getitem__(self, key: str) -> Any:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return repr(dict(self._items))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        return dict(self.items()) == dict(other.items())

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("frozen JSON mapping cannot be mutated")

    def __deepcopy__(self, memo: dict[int, Any]) -> dict[str, Any]:
        copied = {
            key: deepcopy(value, memo) for key, value in self._items
        }
        memo[id(self)] = copied
        return copied

    def __reduce__(self) -> tuple[Any, tuple[dict[str, Any]]]:
        return type(self), (dict(self._items),)


def _deep_freeze(value: Any) -> Any:
    """Recursively detach mutable input and expose immutable nested containers."""
    if isinstance(value, Mapping):
        return _FrozenJsonMapping({
            key: _deep_freeze(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return deepcopy(value)


def _deep_thaw(value: Any) -> Any:
    """Return a detached JSON-shaped copy of recursively frozen contract data."""
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_deep_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_deep_thaw(item) for item in value]
    return deepcopy(value)


def _extra_forbid_dataclass_mapping(
    value: Mapping[str, Any],
    model: type[Any],
    label: str,
) -> dict[str, Any]:
    accepted = {item.name for item in fields(model)}
    extra = set(value) - accepted
    if extra:
        raise ValueError(
            f"unexpected {label} fields: " + ", ".join(sorted(extra))
        )
    return dict(value)


@dataclass(frozen=True)
class ReferenceSnapshotV1:
    """One immutable, approved asset captured in the Ares run seal."""

    owner: ReferenceOwner
    workspace_id: str
    master_id: str
    version: int
    approval_status: ApprovalStatus
    storage_key: str
    content_digest: str
    ref_kind: ReferenceKind
    subject_id: str
    label: str = "front"
    url: Optional[str] = None
    source_run_id: Optional[str] = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("workspace_id", "master_id", "storage_key", "subject_id"):
            if not str(getattr(self, name) or "").strip():
                errors.append(f"{name} is required")
        if self.version < 1:
            errors.append("version must be >= 1")
        if self.approval_status != "approved":
            errors.append("reference must be approved")
        if not is_digest(self.content_digest):
            errors.append("content_digest must be a sha256 digest")
        if self.ref_kind == "character" and self.owner != "parzifal":
            errors.append("character references must be owned by parzifal")
        if self.ref_kind in {"product", "evidence"} and self.owner != "artemis":
            errors.append("product/evidence references must be owned by artemis")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReferenceSnapshotV1":
        accepted = {item.name for item in fields(cls)}
        return cls(**{key: item for key, item in value.items() if key in accepted})


@dataclass(frozen=True)
class CastRoleIntentV1:
    """A subject assigned to a semantic role in one beat."""

    role: CastRole
    subject_id: str
    requirement: RoleRequirement = "required"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CastRoleIntentV1":
        return cls(**value)


@dataclass(frozen=True)
class BeatCastIntentV1:
    """Ares-sealed role matrix for one beat; Athena may not invent roles."""

    beat_index: int
    render_mode: str
    roles: tuple[CastRoleIntentV1, ...] = ()

    def required_roles(self) -> tuple[CastRoleIntentV1, ...]:
        return tuple(role for role in self.roles if role.requirement == "required")

    def forbidden_roles(self) -> tuple[CastRoleIntentV1, ...]:
        return tuple(role for role in self.roles if role.requirement == "forbidden")

    def validate(self) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for role in self.roles:
            if role.role in seen:
                errors.append(f"duplicate role: {role.role}")
            seen.add(role.role)
            if role.requirement != "forbidden" and not role.subject_id.strip():
                errors.append(f"{role.role}.subject_id is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_index": self.beat_index,
            "render_mode": self.render_mode,
            "roles": [role.to_dict() for role in self.roles],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BeatCastIntentV1":
        return cls(
            beat_index=int(value["beat_index"]),
            render_mode=str(value["render_mode"]),
            roles=tuple(
                role if isinstance(role, CastRoleIntentV1) else CastRoleIntentV1.from_dict(role)
                for role in value.get("roles", ())
            ),
        )


@dataclass(frozen=True)
class PlannedReferenceV1:
    """A role-bound reference in exact provider input order."""

    role: CastRole
    required: bool
    snapshot: ReferenceSnapshotV1

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "required": self.required,
            "snapshot": self.snapshot.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlannedReferenceV1":
        snapshot = value["snapshot"]
        return cls(
            role=value["role"],
            required=bool(value["required"]),
            snapshot=(
                snapshot
                if isinstance(snapshot, ReferenceSnapshotV1)
                else ReferenceSnapshotV1.from_dict(snapshot)
            ),
        )


@dataclass(frozen=True)
class BeatFramePlanV1:
    """Athena's single immutable composition plan for one visual beat."""

    run_id: str
    workspace_id: str
    beat_index: int
    shot_list_digest: str
    render_mode: str
    ordered_refs: tuple[PlannedReferenceV1, ...]
    shot: dict[str, Any]
    prompt: str
    prompt_constitution_version: str
    plan_digest: str
    provider: str = "seedream"
    model: str = SEEDREAM_5_PRO_MODEL_ID
    width: int = 1024
    height: int = 1536
    quality: str = "high"
    lock_policy: str = "hard_fail"
    max_refs: int = SEEDREAM_V1_MAX_REFS

    def digest_payload(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("plan_digest", None)
        return value

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.run_id or not self.workspace_id:
            errors.append("run_id and workspace_id are required")
        if not is_digest(self.shot_list_digest):
            errors.append("shot_list_digest must be a sha256 digest")
        if self.provider != "seedream" or self.model != SEEDREAM_5_PRO_MODEL_ID:
            errors.append(f"V1 materialization engine must be {SEEDREAM_5_PRO_MODEL_ID}")
        if not self.prompt.strip():
            errors.append("compiled prompt is required")
        if not self.prompt_constitution_version.strip():
            errors.append("prompt_constitution_version is required")
        if not isinstance(self.shot, dict) or self.shot.get("beat_index") != self.beat_index:
            errors.append("shot must contain the matching beat_index")
        if self.lock_policy != "hard_fail":
            errors.append("V1 lock_policy must be hard_fail")
        if not 1 <= self.max_refs <= SEEDREAM_V1_MAX_REFS:
            errors.append(f"max_refs must be 1..{SEEDREAM_V1_MAX_REFS}")
        if len(self.ordered_refs) > self.max_refs:
            errors.append("ordered_refs exceeds max_refs")
        keys = [ref.snapshot.storage_key for ref in self.ordered_refs]
        if len(keys) != len(set(keys)):
            errors.append("ordered_refs contains duplicate storage keys")
        if any(ref.snapshot.workspace_id != self.workspace_id for ref in self.ordered_refs):
            errors.append("cross-workspace reference")
        for ref in self.ordered_refs:
            errors.extend(f"{ref.role}: {error}" for error in ref.snapshot.validate())
        if self.plan_digest != sha256_digest(self.digest_payload()):
            errors.append("plan_digest does not match plan payload")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "beat_index": self.beat_index,
            "shot_list_digest": self.shot_list_digest,
            "render_mode": self.render_mode,
            "ordered_refs": [ref.to_dict() for ref in self.ordered_refs],
            "shot": self.shot,
            "prompt": self.prompt,
            "prompt_constitution_version": self.prompt_constitution_version,
            "plan_digest": self.plan_digest,
            "provider": self.provider,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "quality": self.quality,
            "lock_policy": self.lock_policy,
            "max_refs": self.max_refs,
        }

    @classmethod
    def create(cls, **values: Any) -> "BeatFramePlanV1":
        draft = cls(plan_digest="", **values)
        return cls(**{**draft.to_dict(), "ordered_refs": draft.ordered_refs,
                      "plan_digest": sha256_digest(draft.digest_payload())})

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BeatFramePlanV1":
        return cls(
            **{
                **value,
                "ordered_refs": tuple(
                    ref if isinstance(ref, PlannedReferenceV1) else PlannedReferenceV1.from_dict(ref)
                    for ref in value.get("ordered_refs", ())
                ),
            }
        )


@dataclass(frozen=True)
class BeatFramePlanV2:
    """V1 composition plus the exact Ares visual seal and policy.

    V2 is additive. V1 payloads remain valid and unchanged; callers opt into
    V2 only when both Ares-owned fields are available.
    """

    run_id: str
    workspace_id: str
    beat_index: int
    shot_list_digest: str
    visual_bridge_digest: str
    visual_policy: Mapping[str, Any]
    render_mode: str
    ordered_refs: tuple[PlannedReferenceV1, ...]
    shot: Mapping[str, Any]
    prompt: str
    prompt_constitution_version: str
    plan_digest: str
    provider: str = "seedream"
    model: str = SEEDREAM_5_PRO_MODEL_ID
    width: int = 1024
    height: int = 1536
    quality: str = "high"
    lock_policy: str = "hard_fail"
    max_refs: int = SEEDREAM_V1_MAX_REFS
    contract_version: str = VISUAL_CONTRACT_VERSION_V2

    def __post_init__(self) -> None:
        object.__setattr__(self, "visual_policy", _deep_freeze(self.visual_policy))
        object.__setattr__(self, "shot", _deep_freeze(self.shot))
        object.__setattr__(self, "ordered_refs", tuple(self.ordered_refs))

    def __deepcopy__(self, memo: dict[int, Any]) -> "BeatFramePlanV2":
        copied = type(self).from_dict(self.to_dict())
        memo[id(self)] = copied
        return copied

    def digest_payload(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("plan_digest", None)
        return value

    def validate(self) -> list[str]:
        # Project common fields through the proven V1 validator. Its digest is
        # recomputed locally because V2's digest intentionally binds more data.
        v1 = BeatFramePlanV1.create(
            run_id=self.run_id,
            workspace_id=self.workspace_id,
            beat_index=self.beat_index,
            shot_list_digest=self.shot_list_digest,
            render_mode=self.render_mode,
            ordered_refs=self.ordered_refs,
            shot=_deep_thaw(self.shot),
            prompt=self.prompt,
            prompt_constitution_version=self.prompt_constitution_version,
            provider=self.provider,
            model=self.model,
            width=self.width,
            height=self.height,
            quality=self.quality,
            lock_policy=self.lock_policy,
            max_refs=self.max_refs,
        )
        errors = list(v1.validate())
        if self.contract_version != VISUAL_CONTRACT_VERSION_V2:
            errors.append(
                f"contract_version must be {VISUAL_CONTRACT_VERSION_V2}"
            )
        if not is_digest(self.visual_bridge_digest):
            errors.append("visual_bridge_digest must be a sha256 digest")
        if not isinstance(self.visual_policy, Mapping) or set(self.visual_policy) != {
            "allow_all_persona"
        }:
            errors.append("visual_policy must contain only allow_all_persona")
        elif type(self.visual_policy["allow_all_persona"]) is not bool:
            errors.append("visual_policy.allow_all_persona must be a boolean")
        if self.plan_digest != sha256_digest(self.digest_payload()):
            errors.append("plan_digest does not match plan payload")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "beat_index": self.beat_index,
            "shot_list_digest": self.shot_list_digest,
            "visual_bridge_digest": self.visual_bridge_digest,
            "visual_policy": _deep_thaw(self.visual_policy),
            "render_mode": self.render_mode,
            "ordered_refs": [ref.to_dict() for ref in self.ordered_refs],
            "shot": _deep_thaw(self.shot),
            "prompt": self.prompt,
            "prompt_constitution_version": self.prompt_constitution_version,
            "plan_digest": self.plan_digest,
            "provider": self.provider,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "quality": self.quality,
            "lock_policy": self.lock_policy,
            "max_refs": self.max_refs,
        }

    @classmethod
    def create(cls, **values: Any) -> "BeatFramePlanV2":
        draft = cls(plan_digest="", **values)
        return cls(
            **{
                **draft.to_dict(),
                "ordered_refs": draft.ordered_refs,
                "plan_digest": sha256_digest(draft.digest_payload()),
            }
        )

    @classmethod
    def from_v1(
        cls,
        plan: BeatFramePlanV1,
        *,
        visual_bridge_digest: str,
        visual_policy: dict[str, Any],
    ) -> "BeatFramePlanV2":
        errors = plan.validate()
        if errors:
            raise ValueError(
                "invalid BeatFramePlanV1 cannot be upgraded: " + "; ".join(errors)
            )
        values = plan.to_dict()
        values.pop("plan_digest", None)
        values["ordered_refs"] = plan.ordered_refs
        return cls.create(
            **values,
            visual_bridge_digest=visual_bridge_digest,
            visual_policy=visual_policy,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BeatFramePlanV2":
        strict_value = _extra_forbid_dataclass_mapping(
            value, cls, "BeatFramePlanV2"
        )
        if value.get("contract_version") != VISUAL_CONTRACT_VERSION_V2:
            raise ValueError("BeatFramePlanV2 contract_version downgrade")
        ordered_refs: list[PlannedReferenceV1] = []
        for raw_ref in value.get("ordered_refs", ()):
            if isinstance(raw_ref, PlannedReferenceV1):
                ordered_refs.append(raw_ref)
                continue
            if not isinstance(raw_ref, Mapping):
                raise ValueError("BeatFramePlanV2 ordered_ref must be an object")
            strict_ref = _extra_forbid_dataclass_mapping(
                raw_ref, PlannedReferenceV1, "PlannedReferenceV1"
            )
            if type(strict_ref.get("required")) is not bool:
                raise ValueError("PlannedReferenceV1.required must be a boolean")
            raw_snapshot = strict_ref.get("snapshot")
            if isinstance(raw_snapshot, ReferenceSnapshotV1):
                snapshot = raw_snapshot
            elif isinstance(raw_snapshot, Mapping):
                snapshot = ReferenceSnapshotV1(**_extra_forbid_dataclass_mapping(
                    raw_snapshot, ReferenceSnapshotV1, "ReferenceSnapshotV1"
                ))
            else:
                raise ValueError("PlannedReferenceV1.snapshot must be an object")
            ordered_refs.append(PlannedReferenceV1(
                role=strict_ref["role"],
                required=strict_ref["required"],
                snapshot=snapshot,
            ))
        return cls(
            **{
                **strict_value,
                "ordered_refs": tuple(ordered_refs),
            }
        )


@dataclass(frozen=True)
class VisualMaterializationRequestV1:
    """Paid generation command; a new explicit command gets a new nonce."""

    plan: BeatFramePlanV1
    generation_nonce: str
    requires_human_review: bool = True
    contract_version: str = VISUAL_CONTRACT_VERSION_V1

    def validate(self) -> list[str]:
        errors = list(self.plan.validate())
        if not self.generation_nonce.strip():
            errors.append("generation_nonce is required")
        else:
            try:
                uuid.UUID(self.generation_nonce)
            except (ValueError, TypeError):
                errors.append("generation_nonce must be a UUID")
        return errors

    @property
    def idempotency_key(self) -> str:
        return sha256_digest({
            "workspace_id": self.plan.workspace_id,
            "run_id": self.plan.run_id,
            "beat_index": self.plan.beat_index,
            "plan_digest": self.plan.plan_digest,
            "generation_nonce": self.generation_nonce,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "plan": self.plan.to_dict(),
            "generation_nonce": self.generation_nonce,
            "requires_human_review": self.requires_human_review,
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VisualMaterializationRequestV1":
        plan = value["plan"]
        return cls(
            plan=plan if isinstance(plan, BeatFramePlanV1) else BeatFramePlanV1.from_dict(plan),
            generation_nonce=value["generation_nonce"],
            requires_human_review=bool(value.get("requires_human_review", True)),
            contract_version=value.get("contract_version", VISUAL_CONTRACT_VERSION_V1),
        )


@dataclass(frozen=True)
class VisualMaterializationRequestV2:
    """Paid generation command that accepts only a sealed BeatFramePlanV2."""

    plan: BeatFramePlanV2
    generation_nonce: str
    requires_human_review: bool = True
    contract_version: str = VISUAL_CONTRACT_VERSION_V2

    def validate(self) -> list[str]:
        if not isinstance(self.plan, BeatFramePlanV2):
            errors = ["plan must be BeatFramePlanV2; downgrade is forbidden"]
        else:
            errors = list(self.plan.validate())
        if self.contract_version != VISUAL_CONTRACT_VERSION_V2:
            errors.append(
                f"contract_version must be {VISUAL_CONTRACT_VERSION_V2}"
            )
        if not self.generation_nonce.strip():
            errors.append("generation_nonce is required")
        else:
            try:
                uuid.UUID(self.generation_nonce)
            except (ValueError, TypeError):
                errors.append("generation_nonce must be a UUID")
        if type(self.requires_human_review) is not bool:
            errors.append("requires_human_review must be a boolean")
        return errors

    @property
    def idempotency_key(self) -> str:
        """End-to-end command identity, including the review gate."""
        return self.command_digest

    @property
    def provider_idempotency_key(self) -> str:
        """Provider-call identity; review policy does not create another paid call."""
        return sha256_digest({
            "purpose": "visual-provider-call.v2",
            "workspace_id": self.plan.workspace_id,
            "run_id": self.plan.run_id,
            "beat_index": self.plan.beat_index,
            "plan_digest": self.plan.plan_digest,
            "generation_nonce": self.generation_nonce,
        })

    @property
    def command_digest(self) -> str:
        """Digest of the complete paid command and its execution policy."""
        return sha256_digest({
            "contract_version": self.contract_version,
            "workspace_id": self.plan.workspace_id,
            "run_id": self.plan.run_id,
            "beat_index": self.plan.beat_index,
            "plan_contract_version": self.plan.contract_version,
            "plan_digest": self.plan.plan_digest,
            "generation_nonce": self.generation_nonce,
            "requires_human_review": self.requires_human_review,
            "provider_idempotency_key": self.provider_idempotency_key,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "plan": self.plan.to_dict(),
            "generation_nonce": self.generation_nonce,
            "requires_human_review": self.requires_human_review,
            "command_digest": self.command_digest,
            "provider_idempotency_key": self.provider_idempotency_key,
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VisualMaterializationRequestV2":
        accepted = {
            "contract_version",
            "plan",
            "generation_nonce",
            "requires_human_review",
            "command_digest",
            "provider_idempotency_key",
            "idempotency_key",
        }
        extra = set(value) - accepted
        if extra:
            raise ValueError(
                "unexpected VisualMaterializationRequestV2 fields: "
                + ", ".join(sorted(extra))
            )
        missing = accepted - set(value)
        if missing:
            raise ValueError(
                "missing VisualMaterializationRequestV2 fields: "
                + ", ".join(sorted(missing))
            )
        if value.get("contract_version") != VISUAL_CONTRACT_VERSION_V2:
            raise ValueError("V2 request downgrade or missing contract_version")
        plan_value = value.get("plan")
        if isinstance(plan_value, BeatFramePlanV1):
            raise ValueError("V2 request rejects BeatFramePlanV1 downgrade")
        if isinstance(plan_value, BeatFramePlanV2):
            plan = plan_value
        elif isinstance(plan_value, Mapping):
            if plan_value.get("contract_version") != VISUAL_CONTRACT_VERSION_V2:
                raise ValueError("V2 request rejects downgraded plan")
            try:
                plan = BeatFramePlanV2.from_dict(dict(plan_value))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid BeatFramePlanV2: {exc}") from exc
        else:
            raise ValueError("V2 request requires BeatFramePlanV2 plan")
        if type(value.get("requires_human_review", True)) is not bool:
            raise ValueError("requires_human_review must be a boolean")
        request = cls(
            plan=plan,
            generation_nonce=str(value.get("generation_nonce") or ""),
            requires_human_review=value.get("requires_human_review", True),
            contract_version=value["contract_version"],
        )
        errors = request.validate()
        if errors:
            raise ValueError(
                "invalid VisualMaterializationRequestV2: " + "; ".join(errors)
            )
        if value["provider_idempotency_key"] != request.provider_idempotency_key:
            raise ValueError(
                "provider_idempotency_key does not match V2 provider call"
            )
        if value["command_digest"] != request.command_digest:
            raise ValueError("command_digest does not match full V2 command")
        if value["idempotency_key"] != request.idempotency_key:
            raise ValueError("idempotency_key does not match V2 paid command")
        return request


def assert_visual_provider_key_reuse_safe_v2(
    existing: VisualMaterializationRequestV2 | dict[str, Any],
    incoming: VisualMaterializationRequestV2 | dict[str, Any],
) -> str:
    """Fail closed when one provider key is reused for a different command."""

    def _validated(
        value: VisualMaterializationRequestV2 | dict[str, Any],
    ) -> VisualMaterializationRequestV2:
        if not isinstance(value, VisualMaterializationRequestV2):
            return VisualMaterializationRequestV2.from_dict(value)
        errors = value.validate()
        if errors:
            raise ValueError(
                "invalid VisualMaterializationRequestV2 object: "
                + "; ".join(errors)
            )
        return value

    prior = _validated(existing)
    candidate = _validated(incoming)
    if (
        prior.provider_idempotency_key == candidate.provider_idempotency_key
        and prior.command_digest != candidate.command_digest
    ):
        raise ValueError(
            "provider_idempotency_key reuse with differing command_digest"
        )
    return candidate.provider_idempotency_key


@dataclass(frozen=True)
class VisualMaterializationReceiptV1:
    """Execution and semantic proof for one provider materialization."""

    idempotency_key: str
    plan_digest: str
    status: MaterializationStatus
    requested_provider: str
    requested_model: str
    resolved_provider: str
    resolved_model: str
    transport: str = SEEDREAM_V1_TRANSPORT
    planned_refs: tuple[dict[str, Any], ...] = ()
    downloaded_refs: tuple[dict[str, Any], ...] = ()
    sent_refs: tuple[dict[str, Any], ...] = ()
    provider_task_id: Optional[str] = None
    actual_width: Optional[int] = None
    actual_height: Optional[int] = None
    artifact_sha256: Optional[str] = None
    execution_validation: dict[str, Any] = field(default_factory=dict)
    semantic_validation: dict[str, Any] = field(default_factory=dict)
    human_review_status: Literal["pending", "approved", "rejected", "not_required"] = "pending"
    failure_reason: Optional[str] = None
    degraded_reason: Optional[str] = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not is_digest(self.idempotency_key) or not is_digest(self.plan_digest):
            errors.append("idempotency_key and plan_digest must be sha256 digests")
        if self.requested_provider != self.resolved_provider:
            errors.append("provider fallback is forbidden")
        if self.requested_model != self.resolved_model:
            errors.append("model fallback is forbidden")
        if self.transport not in ALLOWED_V1_TRANSPORTS:
            errors.append(
                f"V1 transport must be one of {sorted(ALLOWED_V1_TRANSPORTS)}; "
                f"got {self.transport!r}"
            )
        if self.status == "committed":
            if self.planned_refs != self.downloaded_refs or self.planned_refs != self.sent_refs:
                errors.append("committed receipt requires exact reference lineage")
            if not self.artifact_sha256 or not is_digest(self.artifact_sha256):
                errors.append("committed receipt requires artifact_sha256")
            if not self.actual_width or not self.actual_height:
                errors.append("committed receipt requires decoded dimensions")
            if self.semantic_validation.get("ok") is not True:
                errors.append("committed receipt requires semantic_validation.ok=true")
            if self.human_review_status not in {"approved", "not_required"}:
                errors.append("committed receipt requires human approval or explicit not_required")
        if self.degraded_reason:
            errors.append("degraded output is forbidden in V1")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VisualMaterializationReceiptV1":
        return cls(
            **{
                **value,
                "planned_refs": tuple(value.get("planned_refs", ())),
                "downloaded_refs": tuple(value.get("downloaded_refs", ())),
                "sent_refs": tuple(value.get("sent_refs", ())),
            }
        )


__all__ = [
    "ALLOWED_V1_TRANSPORTS", "ApprovalStatus", "BeatCastIntentV1", "BeatFramePlanV1",
    "BeatFramePlanV2",
    "CastRole", "CastRoleIntentV1", "MaterializationStatus", "PlannedReferenceV1",
    "ReferenceKind", "ReferenceOwner", "ReferenceSnapshotV1", "RoleRequirement",
    "SEEDREAM_5_PRO_MODEL_ID", "SEEDREAM_V1_MAX_REFS", "SEEDREAM_V1_TRANSPORT",
    "VISUAL_CONTRACT_VERSION_V1", "VISUAL_CONTRACT_VERSION_V2",
    "VISUAL_RENDER_MODES_V1",
    "assert_visual_provider_key_reuse_safe_v2",
    "VisualMaterializationRequestV1", "VisualMaterializationRequestV2",
    "VisualMaterializationReceiptV1",
]
