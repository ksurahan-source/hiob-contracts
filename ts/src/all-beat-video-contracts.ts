/** TypeScript/Zod mirror of Python-authoritative all_beat_video.py. */
import { z } from 'zod';

import { DIGEST_RE, sha256Digest } from './factory/digest.js';
import { assertStrictCanonicalValue, strictUtcMicros } from './strict-contract-value.js';
import {
  VerifiedFactoryPaidBudgetAuthorityV1,
  unwrapVerifiedFactoryPaidBudgetAuthorityV1,
  type FactoryPaidBudgetAuthorityV1,
} from './factory-paid-budget-authority-v1.js';

const DigestSchema = z.string().regex(DIGEST_RE);
const NonBlankString = z.string().refine((value) => value.trim().length > 0, 'string must not be blank');
const UuidString = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  'identifier must use canonical lowercase UUID form',
);
const PositiveSafeInteger = z.number().int().positive().max(Number.MAX_SAFE_INTEGER);
const NonNegativeSafeInteger = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const UtcTimestamp = z
  .string()
  .refine((value) => { try { strictUtcMicros(value); return true; } catch { return false; } }, 'timestamp must be valid UTC');

export const StrictAllBeatArtifactRefV1Schema = z.object({
  artifact_id: NonBlankString, kind: NonBlankString, uri: NonBlankString,
  sha256: DigestSchema, mime: NonBlankString, bytes_len: NonNegativeSafeInteger,
  duration_ms: NonNegativeSafeInteger.nullable().default(null),
  width: NonNegativeSafeInteger.nullable().default(null),
  height: NonNegativeSafeInteger.nullable().default(null),
  beat_index: NonNegativeSafeInteger.nullable().default(null),
  producer_planet: NonBlankString, producer_node_id: NonBlankString,
  execution_id: NonBlankString, producer_revision: NonBlankString,
  image_digest: DigestSchema.nullable().default(null),
  source_output_digests: z.array(DigestSchema).default([]),
  edge_receipt_digests: z.array(DigestSchema).default([]),
  provenance_refs: z.array(NonBlankString).default([]),
  consent_refs: z.array(NonBlankString).default([]),
}).strict();

export const ALL_BEAT_VIDEO_CONTRACT_VERSIONS = Object.freeze({
  FactoryBeatManifest: 'FactoryBeatManifest.v1',
  BeatVideoRequest: 'BeatVideoRequest.v1',
  BeatVideoReceipt: 'BeatVideoReceipt.v1',
  BeatArtifactSetReceipt: 'BeatArtifactSetReceipt.v1',
  AtroposFanInManifest: 'AtroposFanInManifest.v2',
  AtroposFanInManifestV2: 'AtroposFanInManifest.v2',
  AtroposFanInManifestV3: 'AtroposFanInManifest.v3',
  HephaestusFinalRenderReceipt: 'HephaestusFinalRenderReceipt.v2',
  ReelsFactoryReceipt: 'ReelsFactoryReceipt.v2',
} as const);

function withoutField(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('contract digest input must be an object');
  }
  const body = { ...(value as Record<string, unknown>) };
  delete body[field];
  assertStrictCanonicalValue(body);
  return body;
}

function safelyEqualsDigest(actual: string, derive: () => string): boolean {
  try { return actual === derive(); } catch { return false; }
}

function safelyCanonicalEqual(left: unknown, right: unknown): boolean {
  assertStrictCanonicalValue(left);
  assertStrictCanonicalValue(right);
  return sha256Digest(left) === sha256Digest(right);
}

export function deriveFactoryBeatManifestIdempotencyKeyV1(value: unknown): string {
  const data = value as Record<string, unknown>;
  const identity = {
    purpose: 'factory-beat-manifest.v1', workspace_id: data.workspace_id,
    run_id: data.run_id, factory_revision: data.factory_revision,
    plan_digest: data.plan_digest,
    paid_budget_authority_digest: data.paid_budget_authority_digest,
    beats: data.beats,
  };
  assertStrictCanonicalValue(identity);
  return sha256Digest(identity);
}

export function deriveFactoryBeatManifestDigestV1(value: unknown): string {
  return sha256Digest(withoutField(value, 'manifest_digest'));
}

export function deriveBeatVideoRequestDigestV1(value: unknown): string {
  return sha256Digest(withoutField(value, 'request_digest'));
}

export function deriveBeatVideoReceiptDigestV1(value: unknown): string {
  return sha256Digest(withoutField(value, 'receipt_digest'));
}

export function deriveBeatArtifactSetReceiptDigestV1(value: unknown): string {
  return sha256Digest(withoutField(value, 'receipt_digest'));
}

export function deriveAtroposFanInManifestDigestV2(value: unknown): string {
  return sha256Digest(withoutField(value, 'manifest_digest'));
}

export function deriveAtroposFanInManifestDigestV3(value: unknown): string {
  return sha256Digest(withoutField(value, 'manifest_digest'));
}

export function deriveHephaestusFinalRenderReceiptDigestV2(value: unknown): string {
  return sha256Digest(withoutField(value, 'receipt_digest'));
}

export function deriveReelsFactoryReceiptDigestV2(value: unknown): string {
  return sha256Digest(withoutField(value, 'receipt_digest'));
}

function isRelativeStorageKey(value: string): boolean {
  if (
    value.length === 0
    || value.startsWith('/')
    || value.startsWith('\\')
    || value.includes('://')
    || value.includes('?')
    || value.includes('#')
    || value.includes('\\')
  ) return false;
  return value.split('/').every((segment) => segment !== '' && segment !== '.' && segment !== '..');
}

function validateReferenceArtifacts(
  artifacts: z.infer<typeof StrictAllBeatArtifactRefV1Schema>[],
  beatIndex: number,
  ctx: z.RefinementCtx,
  path: (string | number)[],
): void {
  const digests = new Set<string>();
  artifacts.forEach((artifact, index) => {
    if (!isRelativeStorageKey(artifact.uri)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'reference artifact uri must be a durable relative storage key',
        path: [...path, index, 'uri'],
      });
    }
    if (artifact.beat_index !== null && artifact.beat_index !== beatIndex) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'reference artifact beat_index must be absent or match request beat',
        path: [...path, index, 'beat_index'],
      });
    }
    if (digests.has(artifact.sha256)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'reference artifact sha256 values must be unique',
        path: [...path, index, 'sha256'],
      });
    }
    digests.add(artifact.sha256);
  });
}

function validateVideoArtifact(
  artifact: z.infer<typeof StrictAllBeatArtifactRefV1Schema>,
  beatIndex: number | null,
  ctx: z.RefinementCtx,
  path: (string | number)[],
): void {
  if (!isRelativeStorageKey(artifact.uri)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'artifact uri must be a durable relative storage key',
      path: [...path, 'uri'],
    });
  }
  if (artifact.kind !== 'video' || artifact.mime !== 'video/mp4') {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'artifact must be a video/mp4 video', path });
  }
  if (artifact.beat_index !== beatIndex) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'artifact beat_index does not match receipt', path: [...path, 'beat_index'] });
  }
  if (
    artifact.bytes_len <= 0
    || artifact.duration_ms === null
    || artifact.duration_ms <= 0
    || artifact.width === null
    || artifact.width <= 0
    || artifact.height === null
    || artifact.height <= 0
  ) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'artifact media facts must be positive', path });
  }
}

function validateAudioArtifact(
  artifact: z.infer<typeof StrictAllBeatArtifactRefV1Schema>,
  ctx: z.RefinementCtx,
  path: (string | number)[],
): void {
  if (!isRelativeStorageKey(artifact.uri)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'audio artifact uri must be a durable relative storage key',
      path: [...path, 'uri'],
    });
  }
  if (
    artifact.kind !== 'audio'
    || !/^audio\/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$/.test(artifact.mime)
  ) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'audio artifact must have kind audio and an audio/* MIME',
      path,
    });
  }
  if (
    artifact.bytes_len <= 0
    || artifact.duration_ms === null
    || artifact.duration_ms <= 0
  ) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'audio artifact bytes_len and duration_ms must be positive',
      path,
    });
  }
  if (artifact.width !== null || artifact.height !== null) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'audio artifact width and height must be null',
      path,
    });
  }
  if (artifact.beat_index === null) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'audio artifact beat_index is required',
      path: [...path, 'beat_index'],
    });
  }
}

export const FactoryBeatSpecV1Schema = z
  .object({
    beat_index: NonNegativeSafeInteger,
    generation_nonce: UuidString,
    prompt: NonBlankString,
    duration_ms: PositiveSafeInteger,
    fps: PositiveSafeInteger,
    width: PositiveSafeInteger,
    height: PositiveSafeInteger,
    reference_artifacts: z.array(StrictAllBeatArtifactRefV1Schema).min(1),
    provider: NonBlankString,
    model: NonBlankString,
  })
  .strict()
  .superRefine((value, ctx) => {
    validateReferenceArtifacts(value.reference_artifacts, value.beat_index, ctx, ['reference_artifacts']);
  });

export const FactoryBeatManifestV1Schema = z
  .object({
    contract_version: z.literal('FactoryBeatManifest.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    beats: z.array(FactoryBeatSpecV1Schema).min(1).max(16),
    idempotency_key: DigestSchema,
    manifest_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const indices = value.beats.map((beat) => beat.beat_index);
    if (!indices.every((index, position) => index === position)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'manifest beat indices must be exactly 0..N-1', path: ['beats'] });
    }
    const nonces = value.beats.map((beat) => beat.generation_nonce);
    if (new Set(nonces).size !== nonces.length) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'generation_nonce must be unique per beat', path: ['beats'] });
    }
    if (!safelyEqualsDigest(value.idempotency_key, () => deriveFactoryBeatManifestIdempotencyKeyV1(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'idempotency_key does not match factory beat manifest', path: ['idempotency_key'] });
    }
    if (!safelyEqualsDigest(value.manifest_digest, () => deriveFactoryBeatManifestDigestV1(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'manifest_digest does not match factory beat manifest', path: ['manifest_digest'] });
    }
  });

export const BeatVideoRequestV1Schema = z
  .object({
    contract_version: z.literal('BeatVideoRequest.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    beat_index: NonNegativeSafeInteger,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    generation_nonce: UuidString,
    prompt: NonBlankString,
    duration_ms: PositiveSafeInteger,
    fps: PositiveSafeInteger,
    width: PositiveSafeInteger,
    height: PositiveSafeInteger,
    reference_artifacts: z.array(StrictAllBeatArtifactRefV1Schema).min(1),
    provider: NonBlankString,
    model: NonBlankString,
    request_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    validateReferenceArtifacts(value.reference_artifacts, value.beat_index, ctx, ['reference_artifacts']);
    if (!safelyEqualsDigest(value.request_digest, () => deriveBeatVideoRequestDigestV1(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'request_digest does not match beat video request', path: ['request_digest'] });
    }
  });

export const BeatVideoReceiptV1Schema = z
  .object({
    contract_version: z.literal('BeatVideoReceipt.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    beat_index: NonNegativeSafeInteger,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    generation_nonce: UuidString,
    request_digest: DigestSchema,
    duration_ms: PositiveSafeInteger,
    fps: PositiveSafeInteger,
    width: PositiveSafeInteger,
    height: PositiveSafeInteger,
    provider: NonBlankString,
    model: NonBlankString,
    provider_job_id: NonBlankString,
    status: z.literal('succeeded'),
    artifact: StrictAllBeatArtifactRefV1Schema,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    validateVideoArtifact(value.artifact, value.beat_index, ctx, ['artifact']);
    if (
      value.artifact.duration_ms !== value.duration_ms
      || value.artifact.width !== value.width
      || value.artifact.height !== value.height
    ) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'artifact dimensions or duration do not match request', path: ['artifact'] });
    }
    if (!safelyEqualsDigest(value.receipt_digest, () => deriveBeatVideoReceiptDigestV1(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'receipt_digest does not match beat video receipt', path: ['receipt_digest'] });
    }
  });

export function beatVideoReceiptBindsRequestV1(
  receipt: z.infer<typeof BeatVideoReceiptV1Schema>,
  request: z.infer<typeof BeatVideoRequestV1Schema>,
): boolean {
  return receipt.workspace_id === request.workspace_id
    && receipt.run_id === request.run_id
    && receipt.beat_index === request.beat_index
    && receipt.factory_revision === request.factory_revision
    && receipt.plan_digest === request.plan_digest
    && receipt.paid_budget_authority_digest === request.paid_budget_authority_digest
    && receipt.factory_manifest_digest === request.factory_manifest_digest
    && receipt.generation_nonce === request.generation_nonce
    && receipt.request_digest === request.request_digest
    && receipt.duration_ms === request.duration_ms
    && receipt.fps === request.fps
    && receipt.width === request.width
    && receipt.height === request.height
    && receipt.provider === request.provider
    && receipt.model === request.model;
}

export const BeatArtifactSetReceiptV1Schema = z
  .object({
    contract_version: z.literal('BeatArtifactSetReceipt.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    expected_beat_count: PositiveSafeInteger,
    video_receipts: z.array(BeatVideoReceiptV1Schema).min(1),
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const indices = value.video_receipts.map((receipt) => receipt.beat_index);
    if (
      value.video_receipts.length !== value.expected_beat_count
      || !indices.every((index, position) => index === position)
    ) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'video receipts must cover exactly 0..N-1', path: ['video_receipts'] });
    }
    const receiptDigests = new Set<string>();
    const artifactDigests = new Set<string>();
    value.video_receipts.forEach((receipt, index) => {
      if (
        receipt.workspace_id !== value.workspace_id
        || receipt.run_id !== value.run_id
        || receipt.factory_revision !== value.factory_revision
        || receipt.plan_digest !== value.plan_digest
        || receipt.paid_budget_authority_digest !== value.paid_budget_authority_digest
        || receipt.factory_manifest_digest !== value.factory_manifest_digest
      ) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'video receipt scope or digest does not match set', path: ['video_receipts', index] });
      }
      if (receiptDigests.has(receipt.receipt_digest) || artifactDigests.has(receipt.artifact.sha256)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'video receipt and artifact digests must be unique', path: ['video_receipts', index] });
      }
      receiptDigests.add(receipt.receipt_digest);
      artifactDigests.add(receipt.artifact.sha256);
    });
    if (!safelyEqualsDigest(value.receipt_digest, () => deriveBeatArtifactSetReceiptDigestV1(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'receipt_digest does not match beat artifact set', path: ['receipt_digest'] });
    }
  });

export const AtroposFanInManifestV2Schema = z
  .object({
    contract_version: z.literal('AtroposFanInManifest.v2'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    beat_artifact_set_receipt: BeatArtifactSetReceiptV1Schema,
    video_artifacts: z.array(StrictAllBeatArtifactRefV1Schema).min(1),
    timeline_digest: DigestSchema,
    audio_mix_digest: DigestSchema,
    render_policy_digest: DigestSchema,
    manifest_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const receipt = value.beat_artifact_set_receipt;
    if (
      receipt.workspace_id !== value.workspace_id
      || receipt.run_id !== value.run_id
      || receipt.factory_revision !== value.factory_revision
      || receipt.plan_digest !== value.plan_digest
      || receipt.paid_budget_authority_digest !== value.paid_budget_authority_digest
      || receipt.factory_manifest_digest !== value.factory_manifest_digest
    ) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'beat artifact set scope or digest does not match fan-in', path: ['beat_artifact_set_receipt'] });
    }
    const expected = receipt.video_receipts.map((item) => item.artifact);
    if (!safelyCanonicalEqual(value.video_artifacts, expected)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'video_artifacts must exactly match ordered video receipts', path: ['video_artifacts'] });
    }
    if (!safelyEqualsDigest(value.manifest_digest, () => deriveAtroposFanInManifestDigestV2(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'manifest_digest does not match Atropos fan-in', path: ['manifest_digest'] });
    }
  });

export const AtroposFanInManifestV3Schema = z
  .object({
    contract_version: z.literal('AtroposFanInManifest.v3'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    beat_artifact_set_receipt: BeatArtifactSetReceiptV1Schema,
    video_artifacts: z.array(StrictAllBeatArtifactRefV1Schema).min(1),
    audio_artifacts: z.array(StrictAllBeatArtifactRefV1Schema).min(1),
    timeline_digest: DigestSchema,
    audio_mix_digest: DigestSchema,
    render_policy_digest: DigestSchema,
    manifest_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const receipt = value.beat_artifact_set_receipt;
    if (
      receipt.workspace_id !== value.workspace_id
      || receipt.run_id !== value.run_id
      || receipt.factory_revision !== value.factory_revision
      || receipt.plan_digest !== value.plan_digest
      || receipt.paid_budget_authority_digest !== value.paid_budget_authority_digest
      || receipt.factory_manifest_digest !== value.factory_manifest_digest
    ) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'beat artifact set scope or digest does not match fan-in', path: ['beat_artifact_set_receipt'] });
    }
    const expected = receipt.video_receipts.map((item) => item.artifact);
    if (!safelyCanonicalEqual(value.video_artifacts, expected)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'video_artifacts must exactly match ordered video receipts', path: ['video_artifacts'] });
    }
    value.audio_artifacts.forEach((artifact, index) => {
      validateAudioArtifact(artifact, ctx, ['audio_artifacts', index]);
    });
    const audioBeats = value.audio_artifacts.map((artifact) => artifact.beat_index);
    const videoBeats = value.video_artifacts.map((artifact) => artifact.beat_index);
    const artifactIds = value.audio_artifacts.map((artifact) => artifact.artifact_id);
    const artifactDigests = value.audio_artifacts.map((artifact) => artifact.sha256);
    const artifactUris = value.audio_artifacts.map((artifact) => artifact.uri);
    if (
      !safelyCanonicalEqual(audioBeats, videoBeats)
      || new Set(audioBeats).size !== audioBeats.length
      || new Set(artifactIds).size !== artifactIds.length
      || new Set(artifactDigests).size !== artifactDigests.length
      || new Set(artifactUris).size !== artifactUris.length
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'audio_artifacts must uniquely match ordered video artifact beats',
        path: ['audio_artifacts'],
      });
    }
    if (value.audio_mix_digest !== sha256Digest({ audio_artifacts: value.audio_artifacts })) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'audio_mix_digest must exactly bind ordered audio_artifacts',
        path: ['audio_mix_digest'],
      });
    }
    if (!safelyEqualsDigest(value.manifest_digest, () => deriveAtroposFanInManifestDigestV3(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'manifest_digest does not match Atropos fan-in', path: ['manifest_digest'] });
    }
  });

export const HephaestusFinalRenderReceiptV2Schema = z
  .object({
    contract_version: z.literal('HephaestusFinalRenderReceipt.v2'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    fan_in_manifest_digest: DigestSchema,
    status: z.literal('ready'),
    output_artifact: StrictAllBeatArtifactRefV1Schema,
    output_url: z.string().refine(isCredentialFreeHttpsUrl, 'output_url must be credential-free HTTPS with a valid host'),
    mechanical_qa_passed: z.literal(true),
    rendered_at_utc: UtcTimestamp,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    validateVideoArtifact(value.output_artifact, null, ctx, ['output_artifact']);
    if (!safelyEqualsDigest(value.receipt_digest, () => deriveHephaestusFinalRenderReceiptDigestV2(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'receipt_digest does not match final render receipt', path: ['receipt_digest'] });
    }
  });

export const ReelsFactoryReceiptV2Schema = z
  .object({
    contract_version: z.literal('ReelsFactoryReceipt.v2'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    plan_digest: DigestSchema,
    paid_budget_authority_digest: DigestSchema,
    factory_manifest_digest: DigestSchema,
    beat_artifact_set_receipt_digest: DigestSchema,
    fan_in_manifest_digest: DigestSchema,
    final_render_receipt: HephaestusFinalRenderReceiptV2Schema,
    status: z.literal('succeeded'),
    output_url: z.string().refine(isCredentialFreeHttpsUrl, 'output_url must be credential-free HTTPS with a valid host'),
    output_sha256: DigestSchema,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const render = value.final_render_receipt;
    if (
      render.workspace_id !== value.workspace_id
      || render.run_id !== value.run_id
      || render.factory_revision !== value.factory_revision
    ) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'final render receipt scope does not match factory', path: ['final_render_receipt'] });
    }
    if (render.fan_in_manifest_digest !== value.fan_in_manifest_digest) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'fan_in_manifest_digest does not match final render receipt', path: ['fan_in_manifest_digest'] });
    }
    if (render.output_url !== value.output_url) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'output_url does not match final render receipt', path: ['output_url'] });
    }
    if (render.output_artifact.sha256 !== value.output_sha256) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'output_sha256 does not match final render artifact', path: ['output_sha256'] });
    }
    if (!safelyEqualsDigest(value.receipt_digest, () => deriveReelsFactoryReceiptDigestV2(value))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'receipt_digest does not match reels factory receipt', path: ['receipt_digest'] });
    }
  });

function isCredentialFreeHttpsUrl(value: string): boolean {
  try {
    if (/\s/.test(value)) return false;
    const rawAuthority = /^https:\/\/([^/?#]+)/.exec(value)?.[1];
    if (!rawAuthority || rawAuthority.includes('@')) return false;
    const parsed = new URL(value);
    const hostname = parsed.hostname;
    const dnsHost = hostname.length <= 253 && hostname.replace(/\.$/, '').split('.').every(
      (label) => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label),
    );
    const ipv6Host = /^\[[0-9A-Fa-f:]+\]$/.test(hostname);
    return parsed.protocol === 'https:' && hostname.length > 0 && (dnsHost || ipv6Host)
      && parsed.username === '' && parsed.password === '';
  } catch { return false; }
}

export function factoryBeatManifestStructurallyBindsPaidAuthorityV1(
  manifest: FactoryBeatManifestV1,
  authority: FactoryPaidBudgetAuthorityV1,
): boolean {
  return manifest.workspace_id === authority.workspace_id
    && manifest.run_id === authority.run_id
    && manifest.factory_revision === authority.factory_revision
    && manifest.beats.length === authority.all_beat_count
    && manifest.paid_budget_authority_digest === authority.authority_digest;
}

export function factoryBeatManifestBindsPaidAuthorityV1(
  manifest: FactoryBeatManifestV1,
  authority: unknown,
): boolean {
  const sealed = unwrapVerifiedFactoryPaidBudgetAuthorityV1(authority);
  return sealed !== null
    && factoryBeatManifestStructurallyBindsPaidAuthorityV1(manifest, sealed);
}

export function requireFactoryBeatManifestPaidAuthorityV1(
  manifest: FactoryBeatManifestV1,
  authority: unknown,
): VerifiedFactoryPaidBudgetAuthorityV1 {
  if (unwrapVerifiedFactoryPaidBudgetAuthorityV1(authority) === null) {
    throw new TypeError('execution requires VerifiedFactoryPaidBudgetAuthorityV1');
  }
  if (!factoryBeatManifestBindsPaidAuthorityV1(manifest, authority)) {
    throw new TypeError('verified paid authority does not bind factory manifest');
  }
  return authority as VerifiedFactoryPaidBudgetAuthorityV1;
}

export function beatVideoRequestBindsManifestV1(
  request: BeatVideoRequestV1,
  manifest: FactoryBeatManifestV1,
): boolean {
  const beat = manifest.beats[request.beat_index];
  return beat !== undefined
    && request.workspace_id === manifest.workspace_id && request.run_id === manifest.run_id
    && request.factory_revision === manifest.factory_revision
    && request.plan_digest === manifest.plan_digest
    && request.paid_budget_authority_digest === manifest.paid_budget_authority_digest
    && request.factory_manifest_digest === manifest.manifest_digest
    && request.generation_nonce === beat.generation_nonce && request.prompt === beat.prompt
    && request.duration_ms === beat.duration_ms && request.fps === beat.fps
    && request.width === beat.width && request.height === beat.height
    && sha256Digest(request.reference_artifacts) === sha256Digest(beat.reference_artifacts)
    && request.provider === beat.provider && request.model === beat.model;
}

export function reelsFactoryReceiptBindsChainV2(
  factory: ReelsFactoryReceiptV2,
  manifest: FactoryBeatManifestV1,
  artifactSet: BeatArtifactSetReceiptV1,
  fanIn: AtroposFanInManifestV2 | AtroposFanInManifestV3,
): boolean {
  const scope = [factory.workspace_id, factory.run_id, factory.factory_revision,
    factory.plan_digest, factory.paid_budget_authority_digest, factory.factory_manifest_digest];
  return sha256Digest(scope) === sha256Digest([
    manifest.workspace_id, manifest.run_id, manifest.factory_revision,
    manifest.plan_digest, manifest.paid_budget_authority_digest, manifest.manifest_digest,
  ]) && sha256Digest(scope) === sha256Digest([
    artifactSet.workspace_id, artifactSet.run_id, artifactSet.factory_revision,
    artifactSet.plan_digest, artifactSet.paid_budget_authority_digest,
    artifactSet.factory_manifest_digest,
  ]) && sha256Digest(scope) === sha256Digest([
    fanIn.workspace_id, fanIn.run_id, fanIn.factory_revision, fanIn.plan_digest,
    fanIn.paid_budget_authority_digest, fanIn.factory_manifest_digest,
  ]) && factory.beat_artifact_set_receipt_digest === artifactSet.receipt_digest
    && sha256Digest(fanIn.beat_artifact_set_receipt) === sha256Digest(artifactSet)
    && factory.fan_in_manifest_digest === fanIn.manifest_digest
    && factory.final_render_receipt.fan_in_manifest_digest === fanIn.manifest_digest;
}

export type FactoryBeatSpecV1 = z.infer<typeof FactoryBeatSpecV1Schema>;
export type StrictAllBeatArtifactRefV1 = z.infer<typeof StrictAllBeatArtifactRefV1Schema>;
export type FactoryBeatManifestV1 = z.infer<typeof FactoryBeatManifestV1Schema>;
export type BeatVideoRequestV1 = z.infer<typeof BeatVideoRequestV1Schema>;
export type BeatVideoReceiptV1 = z.infer<typeof BeatVideoReceiptV1Schema>;
export type BeatArtifactSetReceiptV1 = z.infer<typeof BeatArtifactSetReceiptV1Schema>;
export type AtroposFanInManifestV2 = z.infer<typeof AtroposFanInManifestV2Schema>;
export type AtroposFanInManifestV3 = z.infer<typeof AtroposFanInManifestV3Schema>;
export type HephaestusFinalRenderReceiptV2 = z.infer<typeof HephaestusFinalRenderReceiptV2Schema>;
export type ReelsFactoryReceiptV2 = z.infer<typeof ReelsFactoryReceiptV2Schema>;
