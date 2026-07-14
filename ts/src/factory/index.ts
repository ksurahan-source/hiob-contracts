/**
 * @hiob/contracts/factory — Creative Factory Harmony kernel (TS Zod 미러).
 *
 * ⚠️ AUTHORITY: Python (hiob_contracts/factory/*.py). 이 파일은 미러다.
 */
export {
  DIGEST_RE,
  DigestError,
  canonicalJson,
  sha256Digest,
  isDigest,
  assertDigest,
} from './digest.js';
export type { Digest } from './digest.js';

export {
  DigestSchema,
  ContractRefSchema,
  ArtifactRefSchema,
  PlanetOutputSchema,
  buildPlanetOutput,
  verifyPlanetOutput,
  computeOutputDigest,
} from './planet-output.js';
export type { ContractRef, ArtifactRef, PlanetOutput, PlanetOutputInput } from './planet-output.js';

export {
  TargetRefSchema,
  PolicyRefSchema,
  TransformLogEntrySchema,
  EdgeViolationSchema,
  MapperRefSchema,
  KarmaRefineRequestSchema,
  KarmaEdgeReceiptSchema,
  deriveIdempotencyKey,
  receiptAuthorizes,
} from './karma-edge.js';
export type {
  TargetRef,
  PolicyRef,
  TransformLogEntry,
  EdgeViolation,
  MapperRef,
  KarmaRefineRequest,
  KarmaEdgeReceipt,
  EdgeDecision,
} from './karma-edge.js';

export {
  StageErrorSchema,
  StageReceiptSchema,
  TERMINAL_STAGE_STATUSES,
  isStageTerminal,
  isStageSuccess,
} from './stage-receipt.js';
export type { StageError, StageReceipt, StageStatus } from './stage-receipt.js';

export {
  ApprovalReceiptSchema,
  DegradationReceiptSchema,
  approvalAuthorizes,
} from './approval.js';
export type { ApprovalReceipt, DegradationReceipt } from './approval.js';

export {
  FactoryState,
  TERMINAL_STATES,
  StageExecutionState,
  EdgeExecutionState,
  canTransition,
  assertTransition,
} from './state.js';

export {
  EDGES,
  getEdge,
  isRegisteredEdge,
  requiredEdges,
} from './edge-registry.js';
export type { SemanticEdge, Criticality } from './edge-registry.js';
