"""Immutable selected narration, separate from the original visual beat count.

Digest validation proves content integrity only. Ares must bind every selection
back to the sealed request and script; execution needs a separate durable grant.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .ares_script_revision_v1 import DigestStr, canonical_contract_digest_v1

_STRICT = ConfigDict(frozen=True, extra='forbid', strict=True, revalidate_instances='always')
Text = Annotated[str, StringConstraints(min_length=1, max_length=2000, pattern=r'\S')]
Index = Annotated[int, Field(ge=0, le=63)]


class AresNarrationSegmentV1(BaseModel):
    model_config = _STRICT
    segment_index: Index
    source_beat_index: Index
    source_atom_id: Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r'^\S+$')]
    text: Text


class AresNarrationDocumentV1(BaseModel):
    model_config = _STRICT
    contract_version: Literal['AresNarrationDocument.v1']
    source_request_digest: DigestStr
    source_script_revision_digest: DigestStr
    source_script_package_digest: DigestStr
    source_catalog_digest: DigestStr
    policy_digest: DigestStr
    locale: Literal['ko', 'en']
    voice_id: Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r'^\S+$')]
    segments: Annotated[tuple[AresNarrationSegmentV1, ...], Field(min_length=2, max_length=64)]
    text: Text
    text_digest: DigestStr
    document_digest: DigestStr

    @field_validator('segments', mode='before')
    @classmethod
    def freeze_segments(cls, value):
        if not isinstance(value, (list, tuple)):
            raise ValueError('narration segments must be an ordered array')
        return tuple(value)

    @model_validator(mode='after')
    def bind_selection(self):
        if [segment.segment_index for segment in self.segments] != list(range(len(self.segments))):
            raise ValueError('narration segment indices must be consecutive')
        source_indices = [segment.source_beat_index for segment in self.segments]
        if source_indices[0] != 0 or source_indices != sorted(set(source_indices)):
            raise ValueError('source indices must retain the first hook and strictly increase')
        if len({segment.source_atom_id for segment in self.segments}) != len(self.segments):
            raise ValueError('narration source atoms must not repeat')
        if len({segment.text for segment in self.segments}) != len(self.segments):
            raise ValueError('narration text must not repeat')
        if self.text != ' '.join(segment.text for segment in self.segments):
            raise ValueError('narration text must exactly join the selected segments')
        if self.text_digest != canonical_contract_digest_v1({'text': self.text}):
            raise ValueError('narration text digest mismatch')
        if self.document_digest != canonical_contract_digest_v1(self, exclude={'document_digest'}):
            raise ValueError('narration document digest mismatch')
        return self


__all__ = ['AresNarrationDocumentV1', 'AresNarrationSegmentV1']
