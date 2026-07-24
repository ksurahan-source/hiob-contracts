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
export { JanusBriefSchema, Intake13QSchema, answeredCount } from './janus-brief.js';
export type { JanusBrief, Intake13Q } from './janus-brief.js';

// BeatPlan
export { BeatPlanSchema, BeatSchema, validateBeatPlan } from './beat-plan.js';
export type { BeatPlan, Beat } from './beat-plan.js';

// AudioClip
export { AudioClipSchema, validateAudioClip } from './audio-clip.js';
export type { AudioClip } from './audio-clip.js';
export { AudioTrackType } from './audio-clip.js';

// MediaArtifact
export { MediaArtifactSchema, validateMediaArtifact } from './media-artifact.js';
export type { MediaArtifact } from './media-artifact.js';
export { MediaKindType } from './media-artifact.js';

// EditDecisionList — SUNSET (D-66): Python deleted; do not re-export TS.
// Live editorial state = run.attributes.editing_decisions dict (not this type).

// ParzifalTargetInput
export { ParzifalTargetInputSchema, validateParzifalTargetInput } from './parzifal-target-input.js';
export type { ParzifalTargetInput } from './parzifal-target-input.js';

// AresScriptInput
export { AresScriptInputSchema, validateAresScriptInput } from './ares-script-input.js';
export type { AresScriptInput } from './ares-script-input.js';

// CompositionSnapshot
export { CompositionSnapshotSchema, validateCompositionSnapshot } from './composition-snapshot.js';
export type { CompositionSnapshot } from './composition-snapshot.js';
export { RenderStatusType } from './composition-snapshot.js';

// ReelMetric
export { ReelMetricSchema, calculateRoas, calculateCtr, validateReelMetric } from './reel-metric.js';
export type { ReelMetric } from './reel-metric.js';

// Gate
export { assertRenderReady } from './gate.js';
export type { RenderReadiness } from './gate.js';

// Creative Factory Harmony kernel (PRD 2026-07-14 §6–§7)
export * from './factory/index.js';

// First-customer durable order / approval / paid effect / verified render v2.
export * from './overnight-first-customer-v2.js';

// Ares XL V1 split script/production-plan revision and approval seam.
export * from './ares-script-revision-v1.js';

// DB-backed strategy approval and Parzifal identity binding evidence.
export * from './strategy-approval-v2.js';
