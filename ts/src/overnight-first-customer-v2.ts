/**
 * Strict TypeScript/Zod mirror of Python overnight_first_customer_v2.py.
 * Python remains authoritative; parity constants live in the adjacent test.
 */
import { createHash } from 'node:crypto';
import { z } from 'zod';

import { DigestSchema } from './factory/planet-output.js';
import { sha256Digest } from './factory/digest.js';

export const FIRST_CUSTOMER_CONTRACT_VERSIONS_V2 = {
  CreativeOrder: 'CreativeOrder.v2',
  ScriptApprovalReceipt: 'ScriptApprovalReceipt.v2',
  EditorApprovalReceipt: 'EditorApprovalReceipt.v2',
  PaidEffectIntent: 'PaidEffectIntent.v2',
  PaidEffectAttempt: 'PaidEffectAttempt.v2',
  VerifiedRenderReceipt: 'VerifiedRenderReceipt.v2',
} as const;

const NonEmptyString = z.string().trim().min(1);
const Sha256HexSchema = z.string().regex(/^[0-9a-f]{64}$/);
const CurrencyCodeSchema = z.string().regex(/^[A-Z]{3}$/);
const UtcTimestampSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/)
  .refine((value) => !Number.isNaN(Date.parse(value)), 'invalid UTC timestamp');

function utcTimestampMicros(value: string): number {
  // Date.parse normalizes to milliseconds, which loses the six fractional
  // digits this sealed contract permits. Parse the fraction separately so an
  // update at .000001Z is correctly ordered after the whole second.
  const match = /^(.*?)(?:\.(\d{1,6}))?Z$/.exec(value);
  if (!match) return Number.NaN;
  const wholeMs = Date.parse(`${match[1]}Z`);
  if (Number.isNaN(wholeMs)) return Number.NaN;
  const micros = Number.parseInt((match[2] ?? '').padEnd(6, '0') || '0', 10);
  return wholeMs * 1000 + micros;
}

export const EffectKindSchema = z.enum([
  'visual', 'video', 'voiceover', 'music', 'sfx', 'render',
]);
export const PaidEffectStateSchema = z.enum([
  'PLANNED',
  'CLAIMED',
  'PROVIDER_STARTING',
  'PROVIDER_STARTED',
  'RECONCILE_REQUIRED',
  'SUCCEEDED',
  'FAILED_CONFIRMED',
  'NOT_STARTED_CONFIRMED',
]);

const EPHEMERAL_ORDER_FIELDS = new Set([
  'run_id', 'attempt_id', 'lease_id', 'provider_job_id',
]);

function isJsonValue(value: unknown): boolean {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isJsonValue);
  if (typeof value !== 'object') return false;
  return Object.entries(value as Record<string, unknown>).every(
    ([key, item]) => !EPHEMERAL_ORDER_FIELDS.has(key) && isJsonValue(item),
  );
}

const CanonicalOrderPayloadSchema = z
  .record(z.unknown())
  .refine((value) => Object.keys(value).length > 0, 'canonical_order_payload must not be empty')
  .refine(isJsonValue, 'canonical_order_payload must be JSON and exclude runtime identity');

const RevisionMapSchema = z
  .record(NonEmptyString)
  .refine((value) => Object.keys(value).length > 0, 'at least one revision is required')
  .refine(
    (value) => Object.keys(value).every((key) => key.trim().length > 0),
    'revision component names must be non-empty',
  );

function requireNonEmpty(value: string, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value.trim();
}

function requireDigest(value: string, field: string): string {
  if (!/^sha256:[0-9a-f]{64}$/.test(value)) {
    throw new Error(`${field} must be sha256:<64 lowercase hex>`);
  }
  return value;
}

function sha256Text(material: string): string {
  return createHash('sha256').update(material, 'utf8').digest('hex');
}

export function deriveCustomerOrderKeyV2(
  workspaceId: string,
  customerExternalOrderId: string,
): string {
  const workspace = requireNonEmpty(workspaceId, 'workspace_id');
  const external = requireNonEmpty(customerExternalOrderId, 'customer_external_order_id');
  return sha256Text(`${workspace}|${external}`);
}

export function deriveEffectKeyV2(
  customerOrderKey: string,
  approvedScriptDigest: string,
  effectKind: string,
  assetSlot: string,
): string {
  if (!/^[0-9a-f]{64}$/.test(customerOrderKey)) {
    throw new Error('customer_order_key must be 64 lowercase hex');
  }
  const script = requireDigest(approvedScriptDigest, 'approved_script_digest');
  const kind = requireNonEmpty(effectKind, 'effect_kind');
  const slot = requireNonEmpty(assetSlot, 'asset_slot');
  return sha256Text(`${customerOrderKey}|${script}|${kind}|${slot}`);
}

export function deriveEditorApprovalDigestV2(
  customerOrderKey: string,
  approvedScriptDigest: string,
  timelineDigest: string,
  mediaManifestDigest: string,
  renderPolicyDigest: string,
): string {
  if (!/^[0-9a-f]{64}$/.test(customerOrderKey)) {
    throw new Error('customer_order_key must be 64 lowercase hex');
  }
  return sha256Digest({
    customer_order_key: customerOrderKey,
    approved_script_digest: requireDigest(approvedScriptDigest, 'approved_script_digest'),
    timeline_digest: requireDigest(timelineDigest, 'timeline_digest'),
    media_manifest_digest: requireDigest(mediaManifestDigest, 'media_manifest_digest'),
    render_policy_digest: requireDigest(renderPolicyDigest, 'render_policy_digest'),
  });
}

export const CreativeOrderV2Schema = z
  .object({
    contract_version: z.literal('CreativeOrder.v2'),
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    account_id: NonEmptyString,
    brand_id: NonEmptyString,
    product_or_listing_id: NonEmptyString,
    customer_external_order_id: NonEmptyString,
    canonical_order_payload: CanonicalOrderPayloadSchema,
    canonical_order_digest: DigestSchema,
    created_at_utc: UtcTimestampSchema,
  })
  .strict()
  .superRefine((order, ctx) => {
    if (order.canonical_order_digest !== sha256Digest(order.canonical_order_payload)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'canonical_order_digest mismatch' });
    }
    if (order.customer_order_key !== deriveCustomerOrderKeyV2(
      order.workspace_id, order.customer_external_order_id,
    )) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'customer_order_key mismatch' });
    }
  });
export type CreativeOrderV2 = z.infer<typeof CreativeOrderV2Schema>;

export const ScriptApprovalReceiptV2Schema = z
  .object({
    contract_version: z.literal('ScriptApprovalReceipt.v2'),
    approval_receipt_id: NonEmptyString,
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    approval_kind: z.literal('script'),
    approver_account_id: NonEmptyString,
    order_digest: DigestSchema,
    script_digest: DigestSchema,
    policy_digest: DigestSchema,
    approved_at_utc: UtcTimestampSchema,
    transaction_audit_id: NonEmptyString,
  })
  .strict();
export type ScriptApprovalReceiptV2 = z.infer<typeof ScriptApprovalReceiptV2Schema>;

export function scriptReceiptBindsOrder(
  receipt: ScriptApprovalReceiptV2,
  order: CreativeOrderV2,
  scriptDigest: string,
  policyDigest: string,
): boolean {
  return receipt.customer_order_key === order.customer_order_key
    && receipt.workspace_id === order.workspace_id
    && receipt.order_digest === order.canonical_order_digest
    && receipt.script_digest === scriptDigest
    && receipt.policy_digest === policyDigest;
}

export const EditorApprovalReceiptV2Schema = z
  .object({
    contract_version: z.literal('EditorApprovalReceipt.v2'),
    editor_approval_receipt_id: NonEmptyString,
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    editor_account_id: NonEmptyString,
    approved_script_digest: DigestSchema,
    timeline_digest: DigestSchema,
    media_manifest_digest: DigestSchema,
    render_policy_digest: DigestSchema,
    editor_approval_digest: DigestSchema,
    approved_at_utc: UtcTimestampSchema,
    transaction_audit_id: NonEmptyString,
  })
  .strict()
  .superRefine((receipt, ctx) => {
    const expected = deriveEditorApprovalDigestV2(
      receipt.customer_order_key,
      receipt.approved_script_digest,
      receipt.timeline_digest,
      receipt.media_manifest_digest,
      receipt.render_policy_digest,
    );
    if (receipt.editor_approval_digest !== expected) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'editor_approval_digest mismatch' });
    }
  });
export type EditorApprovalReceiptV2 = z.infer<typeof EditorApprovalReceiptV2Schema>;

export function editorReceiptBindsScriptApproval(
  editor: EditorApprovalReceiptV2,
  script: ScriptApprovalReceiptV2,
): boolean {
  return editor.customer_order_key === script.customer_order_key
    && editor.workspace_id === script.workspace_id
    && editor.approved_script_digest === script.script_digest
    && editor.render_policy_digest === script.policy_digest;
}

export const PaidEffectIntentV2Schema = z
  .object({
    contract_version: z.literal('PaidEffectIntent.v2'),
    effect_key: Sha256HexSchema,
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    approved_script_digest: DigestSchema,
    effect_kind: EffectKindSchema,
    asset_slot: NonEmptyString,
    request_digest: DigestSchema,
    spend_ceiling: z.number().finite().positive(),
    currency: CurrencyCodeSchema,
    created_at_utc: UtcTimestampSchema,
  })
  .strict()
  .superRefine((intent, ctx) => {
    const expected = deriveEffectKeyV2(
      intent.customer_order_key,
      intent.approved_script_digest,
      intent.effect_kind,
      intent.asset_slot,
    );
    if (intent.effect_key !== expected) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'effect_key mismatch' });
    }
  });
export type PaidEffectIntentV2 = z.infer<typeof PaidEffectIntentV2Schema>;

export const PaidEffectAttemptV2Schema = z
  .object({
    contract_version: z.literal('PaidEffectAttempt.v2'),
    effect_key: Sha256HexSchema,
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    approved_script_digest: DigestSchema,
    effect_kind: EffectKindSchema,
    asset_slot: NonEmptyString,
    attempt_id: NonEmptyString,
    attempt_number: z.number().int().positive(),
    provider: NonEmptyString,
    provider_idempotency_key: NonEmptyString,
    provider_job_id: NonEmptyString.nullable(),
    state: PaidEffectStateSchema,
    lease_owner: NonEmptyString.nullable(),
    lease_expires_at_utc: UtcTimestampSchema.nullable(),
    fencing_token: z.number().int().nonnegative(),
    request_digest: DigestSchema,
    spend_ceiling: z.number().finite().positive(),
    currency: CurrencyCodeSchema,
    response_digest: DigestSchema.nullable(),
    cost_currency: CurrencyCodeSchema.nullable(),
    cost_amount: z.number().finite().nonnegative().nullable(),
    last_reconciled_at_utc: UtcTimestampSchema.nullable(),
    created_at_utc: UtcTimestampSchema,
    updated_at_utc: UtcTimestampSchema,
  })
  .strict()
  .superRefine((attempt, ctx) => {
    const issue = (message: string) => ctx.addIssue({ code: z.ZodIssueCode.custom, message });
    const expected = deriveEffectKeyV2(
      attempt.customer_order_key,
      attempt.approved_script_digest,
      attempt.effect_kind,
      attempt.asset_slot,
    );
    if (attempt.effect_key !== expected) issue('effect_key mismatch');
    if (attempt.state !== 'PLANNED' && attempt.fencing_token < 1) issue('positive fencing_token required');
    if (['CLAIMED', 'PROVIDER_STARTING'].includes(attempt.state)
      && (attempt.lease_owner === null || attempt.lease_expires_at_utc === null)) {
      issue('active lease required');
    }
    if (['PROVIDER_STARTED', 'SUCCEEDED'].includes(attempt.state)
      && attempt.provider_job_id === null) {
      issue(`${attempt.state} requires provider_job_id`);
    }
    if (attempt.state === 'SUCCEEDED' && attempt.response_digest === null) {
      issue('SUCCEEDED requires response_digest');
    }
    if ((attempt.cost_currency === null) !== (attempt.cost_amount === null)) {
      issue('cost_currency and cost_amount must be present together');
    }
    if (attempt.cost_currency !== null && attempt.cost_currency !== attempt.currency) {
      issue('cost_currency must match authorized currency');
    }
    if (attempt.cost_amount !== null && attempt.cost_amount > attempt.spend_ceiling) {
      issue('cost_amount exceeds authorized spend_ceiling');
    }
    if (utcTimestampMicros(attempt.updated_at_utc) < utcTimestampMicros(attempt.created_at_utc)) {
      issue('updated_at cannot precede created_at');
    }
  });
export type PaidEffectAttemptV2 = z.infer<typeof PaidEffectAttemptV2Schema>;

export function paidEffectAttemptBindsIntent(
  attempt: PaidEffectAttemptV2,
  intent: PaidEffectIntentV2,
): boolean {
  return attempt.effect_key === intent.effect_key
    && attempt.customer_order_key === intent.customer_order_key
    && attempt.workspace_id === intent.workspace_id
    && attempt.approved_script_digest === intent.approved_script_digest
    && attempt.effect_kind === intent.effect_kind
    && attempt.asset_slot === intent.asset_slot
    && attempt.request_digest === intent.request_digest
    && attempt.spend_ceiling === intent.spend_ceiling
    && attempt.currency === intent.currency;
}

export function paidEffectAttemptAllowsNewAttempt(attempt: PaidEffectAttemptV2): boolean {
  return ['PLANNED', 'FAILED_CONFIRMED', 'NOT_STARTED_CONFIRMED'].includes(attempt.state);
}

export const VerifiedRenderReceiptV2Schema = z
  .object({
    contract_version: z.literal('VerifiedRenderReceipt.v2'),
    verified_render_receipt_id: NonEmptyString,
    customer_order_key: Sha256HexSchema,
    workspace_id: NonEmptyString,
    run_id: NonEmptyString,
    render_job_id: NonEmptyString,
    render_effect_key: Sha256HexSchema,
    editor_approval_digest: DigestSchema,
    output_url: z.string().url().refine((value) => value.startsWith('https://'), 'HTTPS required'),
    storage_key: NonEmptyString,
    output_sha256: Sha256HexSchema,
    output_bytes: z.number().int().positive(),
    duration_ms: z.number().int().positive(),
    video_codec: NonEmptyString,
    audio_codec: NonEmptyString,
    mechanical_checker_version: NonEmptyString,
    qa_checker_version: NonEmptyString,
    qa_verdict: z.literal('PASS'),
    qa_evidence_digest: DigestSchema,
    source_revisions: RevisionMapSchema,
    deployed_revisions: RevisionMapSchema,
    created_at_utc: UtcTimestampSchema,
    transaction_audit_id: NonEmptyString,
  })
  .strict();
export type VerifiedRenderReceiptV2 = z.infer<typeof VerifiedRenderReceiptV2Schema>;

export function verifiedReceiptBindsEditorApproval(
  receipt: VerifiedRenderReceiptV2,
  editor: EditorApprovalReceiptV2,
): boolean {
  return receipt.customer_order_key === editor.customer_order_key
    && receipt.workspace_id === editor.workspace_id
    && receipt.editor_approval_digest === editor.editor_approval_digest;
}

export function verifiedReceiptMatchesOutputBytes(
  receipt: VerifiedRenderReceiptV2,
  data: Uint8Array,
): boolean {
  return createHash('sha256').update(data).digest('hex') === receipt.output_sha256;
}
