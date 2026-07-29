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

// EditDecisionList — SUNSET (D-66): Python deleted; do not re-export TS.
// Live editorial state = run.attributes.editing_decisions dict (not this type).

// ParzifalTargetInput
export { ParzifalTargetInputSchema, validateParzifalTargetInput } from './parzifal-target-input';
export type { ParzifalTargetInput } from './parzifal-target-input';

// AresScriptInput
export { AresScriptInputSchema, validateAresScriptInput } from './ares-script-input';
export type { AresScriptInput } from './ares-script-input';

// Ares pure generate V2
export {
  AresCreateScriptRequestV2Schema,
  AresCreateScriptResultV2Schema,
  ScriptPackageV2Schema,
  BeatPlanV2Schema,
  aresCreateScriptRequestSchemaDescriptorV2,
  aresCreateScriptRequestSchemaDigest,
  aresCreateScriptResultSchemaDigest,
} from './ares-create-script-v2';
export type {
  AresCreateScriptRequestV2,
  AresCreateScriptResultV2,
  ScriptPackageV2,
  BeatPlanV2,
} from './ares-create-script-v2';

// Ares pure generate V3 — explicit authority refs and semantic-only beat plan
export {
  AresRequestScopeV3Schema,
  AresAuthorityArtifactRefV3Schema,
  AresP2ATargetProjectionV3Schema,
  AresAuthorityBundleV3Schema,
  AresCreateScriptRequestV3Schema,
  ScriptPackageV3Schema,
  AresSemanticBeatV3Schema,
  SemanticBeatPlanV3Schema,
  AresQualityFindingV3Schema,
  AresGenerateProvenanceV3Schema,
  AresGenerateUsageV3Schema,
  AresCreateScriptResultV3Schema,
  aresCreateScriptRequestV3SchemaDescriptor,
  aresCreateScriptRequestV3SchemaDigest,
  aresCreateScriptResultV3SchemaDigest,
  authorityRefReceiptDigestV3,
  aresP2ATargetProjectionV3SchemaDescriptor,
  aresP2ATargetProjectionV3SchemaDigest,
} from './ares-create-script-v3';

export {
  characterIdentityBindingPayloadV1,
  deriveCharacterIdentityBindingDigestV1,
} from './character-identity-v1';
export {
  CharacterLockV1Schema,
  deriveCharacterLockDigestV1,
} from './character-lock-v1';
export type { CharacterLockV1 } from './character-lock-v1';
export {
  VoiceSpecV1Schema,
  deriveVoiceSpecDigestV1,
} from './voice-spec-v1';
export type { VoiceSpecV1 } from './voice-spec-v1';
export {
  ParzifalVoiceEnvelopeV1Schema,
  deriveParzifalVoiceEnvelopeDigestV1,
} from './parzifal-voice-envelope-v1';
export type { ParzifalVoiceEnvelopeV1 } from './parzifal-voice-envelope-v1';
export {
  ParzifalRecordRefV1Schema,
  ParzifalIdentityReceiptV1Schema,
  StarMakeReadyReceiptV1Schema,
  deriveParzifalIdentityReceiptPayloadDigestV1,
  deriveStarMakeReadyReceiptDigestV1,
} from './star-make-ready-v1';
export type {
  ParzifalRecordRefV1,
  ParzifalIdentityReceiptV1,
  StarMakeReadyReceiptV1,
} from './star-make-ready-v1';
export type {
  AresRequestScopeV3,
  AresAuthorityArtifactRefV3,
  AresP2ATargetProjectionV3,
  AresAuthorityBundleV3,
  AresCreateScriptRequestV3,
  ScriptPackageV3,
  AresSemanticBeatV3,
  SemanticBeatPlanV3,
  AresQualityFindingV3,
  AresGenerateProvenanceV3,
  AresGenerateUsageV3,
  AresCreateScriptResultV3,
} from './ares-create-script-v3';


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

// Ares XL V1 split script/production-plan revision and approval seam.
export * from './ares-script-revision-v1.js';

// Artemis product understanding: Janus observations -> grounded draft -> lock.
export * from './artemis-product-lock-v1.js';
