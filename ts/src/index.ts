/**
 * @hiob/contracts — TypeScript Zod 미러
 *
 * ⚠️ AUTHORITY: Python 정전 소스 (hiob_contracts/*.py)
 * TypeScript는 미러일 뿐, Zod schema로 선언문서화만 제공.
 *
 * 모든 필드·유효성·부재값 동작이 Python과 일치해야 함.
 * 차이 발생 시 Python을 정답으로 간주.
 */

// JanusBrief
export { JanusBriefSchema, Intake13QSchema, answeredCount } from './janus-brief';
export type { JanusBrief, Intake13Q } from './janus-brief';

// BeatPlan
export { BeatPlanSchema, BeatSchema, validateBeatPlan } from './beat-plan';
export type { BeatPlan, Beat } from './beat-plan';

// AudioClip
export { AudioClipSchema, validateAudioClip } from './audio-clip';
export type { AudioClip } from './audio-clip';
export { AudioTrackType } from './audio-clip';

// MediaArtifact
export { MediaArtifactSchema, validateMediaArtifact } from './media-artifact';
export type { MediaArtifact } from './media-artifact';
export { MediaKindType } from './media-artifact';

// EditDecisionList
export { EditDecisionListSchema, EditDecisionSchema, validateEditDecisionList } from './edit-decision-list';
export type { EditDecisionList, EditDecision } from './edit-decision-list';

// ParzifalTargetInput
export { ParzifalTargetInputSchema, validateParzifalTargetInput } from './parzifal-target-input';
export type { ParzifalTargetInput } from './parzifal-target-input';

// AresScriptInput
export { AresScriptInputSchema, validateAresScriptInput } from './ares-script-input';
export type { AresScriptInput } from './ares-script-input';

// CompositionSnapshot
export { CompositionSnapshotSchema, validateCompositionSnapshot } from './composition-snapshot';
export type { CompositionSnapshot } from './composition-snapshot';
export { RenderStatusType } from './composition-snapshot';

// ReelMetric
export { ReelMetricSchema, calculateRoas, calculateCtr, validateReelMetric } from './reel-metric';
export type { ReelMetric } from './reel-metric';

// Gate
export { assertRenderReady } from './gate';
export type { RenderReadiness } from './gate';

// Creative Factory Harmony kernel (PRD 2026-07-14 §6–§7)
export * from './factory/index.js';

// First-customer durable order / approval / paid effect / verified render v2.
export * from './overnight-first-customer-v2.js';
