"""Reviewed ensemble story: source facts, fixed people and editable timed scenes.

Studio and Star retain the complete object. The production leaf consumes scenes
directly; there is deliberately no projection into the legacy 16-beat format.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator, model_serializer

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]


class StrictValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_serializer(mode='wrap')
    def preserve_legacy_shape(self, serialize):
        value = serialize(self)
        # Existing immutable story receipts must retain their exact JSON shape.
        for key, default in [('narrator', None), ('audio_mode', 'dialogue'), ('narration', '')]:
            if key in value and value[key] == default:
                value.pop(key)
        return value


class ProductFact(StrictValue):
    fact_id: Id
    text: Text


class GuideNarrator(StrictValue):
    role: Literal['guide']
    voice: Literal['changu', 'gongchul']


class EnsembleBriefV1(StrictValue):
    contract_version: Literal["EnsembleBrief.v1"]
    target_duration_ms: int = Field(ge=45000, le=60000, strict=True)
    cast_count: Literal[1, 2, 3, 4]
    narrator: GuideNarrator | None = None
    product_name: Text
    product_facts: list[ProductFact] = Field(min_length=1, max_length=20)
    intake_13q: dict[str, str]
    observation: Text
    # Imported observations and founder hypotheses are never testimonials.
    observation_kind: Literal["creator_hypothesis", "external_observation"]
    observation_source: str = Field(max_length=2000)
    emotional_hypothesis: Text
    hook_strategy: Literal["relationship", "product_question", "situation"]
    creative_notes: str = Field(max_length=6000)

    @model_validator(mode="after")
    def source_scope(self):
        ids = [fact.fact_id for fact in self.product_facts]
        if len(set(ids)) != len(ids):
            raise ValueError("product fact IDs must be unique")
        if self.observation_kind == "external_observation" and not self.observation_source.startswith("https://"):
            raise ValueError("external observation requires its source URL")
        if len(self.intake_13q) > 13 or any(len(v) > 4000 for v in self.intake_13q.values()):
            raise ValueError("13Q input is too large")
        return self


class EnsembleCharacter(StrictValue):
    character_id: Id
    name: Text
    role: Text
    relationship: Text
    appearance: Text
    wardrobe: Text
    voice: Text


class EnsembleCastV1(StrictValue):
    cast: list[EnsembleCharacter] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_people(self):
        ids = [person.character_id for person in self.cast]
        if len(set(ids)) != len(ids):
            raise ValueError("character IDs must be unique")
        return self


class DialogueTurn(StrictValue):
    character_id: Id
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    start_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def speakable(self):
        duration = self.end_ms - self.start_ms
        if duration < 300 or len(self.text) * 1000 > duration * 8:
            raise ValueError("dialogue needs natural speaking time")
        return self


class EnsembleScene(StrictValue):
    scene_id: Id
    setting: Text
    cast_ids: list[Id] = Field(max_length=4)
    audio_mode: Literal['dialogue', 'narration', 'silent'] = 'dialogue'
    narration: str = Field(default='', max_length=300)
    action: Text
    emotional_change: Text
    product_role: Literal["none", "incidental", "question", "guide"]
    product_fact_ids: list[Id] = Field(max_length=20)
    source_duration_sec: int = Field(ge=4, le=30, strict=True)
    trim_start_ms: int = Field(ge=0, strict=True)
    duration_ms: int = Field(ge=1000, le=30000, strict=True)
    dialogue: list[DialogueTurn] = Field(max_length=16)
    caption: str = Field(max_length=160)

    @model_validator(mode="after")
    def timing(self):
        if (self.audio_mode != 'dialogue' and self.dialogue) or (self.narration.strip() and self.audio_mode != 'narration'):
            raise ValueError('audio mode conflicts with native dialogue or external narration')
        if self.audio_mode == 'narration' and not self.narration.strip():
            raise ValueError('narration audio mode requires its planned sentence')
        if not self.cast_ids and (self.product_role == 'none' or not self.product_fact_ids):
            raise ValueError('product cutaway requires product facts')
        if len(set(self.cast_ids)) != len(self.cast_ids):
            raise ValueError("scene cast must be unique")
        if self.trim_start_ms + self.duration_ms > self.source_duration_sec * 1000:
            raise ValueError("edit cannot exceed generated source duration")
        previous_end = 0
        for line in self.dialogue:
            if line.character_id not in self.cast_ids:
                raise ValueError("speaker must belong to the scene cast")
            if line.start_ms < previous_end or line.end_ms > self.duration_ms:
                raise ValueError("dialogue must be ordered, non-overlapping and inside the edit")
            previous_end = line.end_ms
        return self


class HookVariant(StrictValue):
    label: Text
    opening: Text
    product_entry: Text


class EnsembleNarrativeV1(StrictValue):
    title: Text
    logline: Text
    emotional_hypothesis: Text
    scenes: list[EnsembleScene] = Field(min_length=4, max_length=10)
    hook_variants: list[HookVariant] = Field(min_length=1, max_length=3)
    cta: Text


class EnsembleStoryV1(EnsembleNarrativeV1, EnsembleCastV1):
    contract_version: Literal["EnsembleStory.v1"]
    target_duration_ms: int = Field(ge=45000, le=60000, strict=True)
    narrator: GuideNarrator | None = None

    @property
    def source_duration_sec(self) -> int:
        return sum(scene.source_duration_sec for scene in self.scenes)

    @model_validator(mode="after")
    def whole_story(self):
        if sum(scene.duration_ms for scene in self.scenes) != self.target_duration_ms:
            raise ValueError("scene durations must sum to the exact target")
        ids = {person.character_id for person in self.cast}
        if len({scene.scene_id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("scene IDs must be unique")
        speakers = set()
        visible = set()
        for scene in self.scenes:
            if not set(scene.cast_ids) <= ids:
                raise ValueError("scene contains an unknown character")
            speakers.update(turn.character_id for turn in scene.dialogue)
            visible.update(scene.cast_ids)
            if scene.audio_mode == 'narration' and self.narrator is None:
                raise ValueError('external narration requires a selected guide narrator')
        if self.narrator is None and speakers != ids:
            raise ValueError("every character must contribute dialogue")
        if self.narrator is not None and visible != ids:
            raise ValueError('every character must contribute visible action')
        if self.narrator is not None and not any(scene.audio_mode == 'narration' for scene in self.scenes):
            raise ValueError('selected narrator requires a planned narration scene')
        if len({scene.setting for scene in self.scenes}) < 2:
            raise ValueError("story needs a situation change")
        return self

    def bind_brief(self, brief: EnsembleBriefV1) -> "EnsembleStoryV1":
        if len(self.cast) != brief.cast_count or self.target_duration_ms != brief.target_duration_ms or self.narrator != brief.narrator:
            raise ValueError("story does not match the approved brief")
        facts = {fact.fact_id for fact in brief.product_facts}
        if any(not set(scene.product_fact_ids) <= facts for scene in self.scenes):
            raise ValueError("story cites a product fact outside the approved source")
        return self
