"""Canonical persistence state for one rendered artifact."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HttpsUrl = Annotated[
    str,
    Field(pattern=r"^https://\S+$", strict=True),
]


class RenderPersistenceV1(BaseModel):
    """Persisted render truth; provider transport states never leak through."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )

    contract_version: Literal["RenderPersistence.v1"]
    status: Literal["pending", "rendering", "ready", "failed"]
    output_url: HttpsUrl | None = None

    @model_validator(mode="after")
    def _bind_success_to_artifact(self) -> "RenderPersistenceV1":
        if self.status == "ready" and self.output_url is None:
            raise ValueError("ready requires output_url")
        if self.status != "ready" and self.output_url is not None:
            raise ValueError("only ready may set output_url")
        return self

    @property
    def is_success(self) -> bool:
        return self.status == "ready" and self.output_url is not None


__all__ = ["RenderPersistenceV1"]
