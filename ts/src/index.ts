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

// Exact run-level beat coverage / serial fan-in receipt.
export {
  BEAT_COVERAGE_CONTRACT_VERSION_V1,
  SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1,
  BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1,
  DEFAULT_BEAT_COVERAGE_LANES_V1,
  TERMINAL_BEAT_LANE_STATUSES_V1,
  BeatLaneTerminalReceiptV1Schema,
  BeatCoverageV1Schema,
  SerialFanInReceiptV1Schema,
  BeatCoverageSchema,
  SerialFanInReceiptSchema,
  beatLaneTerminalReceiptDigestV1,
  createBeatLaneTerminalReceiptV1,
  beatCoverageDigestPayloadV1,
  beatCoverageDigestV1,
  createBeatCoverageV1,
  createSerialFanInReceiptV1,
  buildBeatCoverageV1,
  buildSerialFanInReceiptV1,
} from './beat-coverage';
export type {
  BeatLaneTerminalReceiptV1,
  BeatTerminalReceiptV1,
  SerialFanInLaneReceiptV1,
  LaneTerminalReceiptV1,
  BeatCoverageV1,
  SerialFanInReceiptV1,
  BeatLaneTerminalReceiptV1Input,
  BeatCoverageV1Input,
} from './beat-coverage';

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

// Ares pure generate V2
export {
  AresCreateScriptRequestV2Schema,
  AresCreateScriptResultV2Schema,
  ScriptPackageV2Schema,
  BeatPlanV2Schema,
  aresCreateScriptRequestSchemaDescriptorV2,
  aresCreateScriptRequestSchemaDigest,
  aresCreateScriptResultSchemaDigest,
} from './ares-create-script-v2.js';
export type {
  AresCreateScriptRequestV2,
  AresCreateScriptResultV2,
  ScriptPackageV2,
  BeatPlanV2,
} from './ares-create-script-v2.js';

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
} from './ares-create-script-v3.js';

export {
  characterIdentityBindingPayloadV1,
  deriveCharacterIdentityBindingDigestV1,
} from './character-identity-v1.js';
export {
  CharacterLockV1Schema,
  deriveCharacterLockDigestV1,
} from './character-lock-v1.js';
export type { CharacterLockV1 } from './character-lock-v1.js';
export {
  VoiceSpecV1Schema,
  deriveVoiceSpecDigestV1,
} from './voice-spec-v1.js';
export type { VoiceSpecV1 } from './voice-spec-v1.js';
export {
  ParzifalVoiceEnvelopeV1Schema,
  deriveParzifalVoiceEnvelopeDigestV1,
} from './parzifal-voice-envelope-v1.js';
export type { ParzifalVoiceEnvelopeV1 } from './parzifal-voice-envelope-v1.js';
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
} from './ares-create-script-v3.js';
export {
  AresV3MakeContextV1Schema,
  deriveAresV3MakeContextDigestV1,
} from './ares-v3-make-context-v1.js';
export type {
  AresV3MakeContextV1,
} from './ares-v3-make-context-v1.js';
export {
  AresCharacterIdentityProjectionV1Schema,
  AresProvenanceMemoryV1Schema,
  AresScriptGenerationInputV1Schema,
  AresVoiceSpecProjectionV1Schema,
  deriveAresScriptGenerationInputDigestV1,
} from './planets/ares/script-generation-v1.js';
export type {
  AresCharacterIdentityProjectionV1,
  AresProvenanceMemoryV1,
  AresScriptGenerationInputV1,
  AresVoiceSpecProjectionV1,
} from './planets/ares/script-generation-v1.js';


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

// Artemis product understanding: Janus observations -> grounded draft -> lock.
export * from './artemis-product-lock-v1.js';

// All-beat video factory V2 chain.
export * from './all-beat-video-contracts.js';

// Pre-script paid budget authority; separate from post-plan manifests.
export * from './factory-paid-budget-authority-v1.js';
