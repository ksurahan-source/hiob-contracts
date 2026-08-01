/** TypeScript/Zod mirror of Python FactoryPaidBudgetAuthority.v1. */
import { z } from 'zod';

import { DIGEST_RE, sha256Digest } from './factory/digest.js';
import { assertStrictCanonicalValue, strictUtcMicros } from './strict-contract-value.js';

export const FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1 = (
  'FactoryPaidBudgetAuthority.v1'
);

const DigestSchema = z.string().regex(DIGEST_RE);
const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
const UuidString = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  'identifier must use canonical lowercase UUID form',
);
const NonNegativeSafeInteger = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const PositiveSafeInteger = z.number().int().positive().max(Number.MAX_SAFE_INTEGER);
const AllBeatCount = z.number().int().min(1).max(16);
const CurrencyCode = z.string().regex(/^[A-Z]{3}$/);

function safeDerivedDigest(derive: () => string): string | null {
  try { return derive(); } catch { return null; }
}

export const FactoryPaidCallCardinalityV1Schema = z
  .object({
    script: z.literal(1),
    image: PositiveSafeInteger,
    video: PositiveSafeInteger,
    voice: PositiveSafeInteger,
    render: z.literal(1),
    retries: z.literal(0),
    fallbacks: z.literal(0),
    character_lock: z.literal(0),
  })
  .strict();

export function factoryPaidCallCardinalityV1(allBeatCount: number) {
  return {
    script: 1 as const,
    image: allBeatCount,
    video: allBeatCount,
    voice: allBeatCount,
    render: 1 as const,
    retries: 0 as const,
    fallbacks: 0 as const,
    character_lock: 0 as const,
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('factory paid budget input must be an object');
  }
  assertStrictCanonicalValue(value);
  return value as Record<string, unknown>;
}

export function deriveFactoryPaidBudgetApprovalSubjectDigestV1(
  value: unknown,
): string {
  const data = asRecord(value);
  return sha256Digest({
    contract_version: 'FactoryPaidBudgetApprovalSubject.v1',
    workspace_id: data.workspace_id,
    run_id: data.run_id,
    factory_revision: data.factory_revision,
    all_beat_count: data.all_beat_count,
    paid_calls: data.paid_calls,
    max_total_cost_microunits: data.max_total_cost_microunits,
    currency: data.currency,
    cost_profile_digest: data.cost_profile_digest,
    pricing_policy_revision: data.pricing_policy_revision,
  });
}

export function deriveFactoryPaidBudgetIdempotencyKeyV1(
  value: unknown,
): string {
  const data = asRecord(value);
  return sha256Digest({
    purpose: 'factory-paid-budget-authority.v1',
    workspace_id: data.workspace_id,
    run_id: data.run_id,
    factory_revision: data.factory_revision,
    approval_subject_digest: data.approval_subject_digest,
    approval_receipt_id: data.approval_receipt_id,
    approval_receipt_digest: data.approval_receipt_digest,
    cost_profile_digest: data.cost_profile_digest,
    pricing_policy_revision: data.pricing_policy_revision,
  });
}

export function deriveFactoryPaidBudgetAuthorityDigestV1(
  value: unknown,
): string {
  const data = { ...asRecord(value) };
  delete data.authority_digest;
  return sha256Digest(data);
}

export const FactoryPaidBudgetAuthorityV1Schema = z
  .object({
    contract_version: z.literal('FactoryPaidBudgetAuthority.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    all_beat_count: AllBeatCount,
    paid_calls: FactoryPaidCallCardinalityV1Schema,
    max_total_cost_microunits: PositiveSafeInteger,
    currency: CurrencyCode,
    cost_profile_digest: DigestSchema,
    pricing_policy_revision: NonNegativeSafeInteger,
    approval_receipt_id: NonBlankString,
    approval_receipt_digest: DigestSchema,
    approval_subject_digest: DigestSchema,
    idempotency_key: DigestSchema,
    authority_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (!Number.isSafeInteger(value.all_beat_count)
      || !Number.isSafeInteger(value.max_total_cost_microunits)) return;
    const expectedCalls = factoryPaidCallCardinalityV1(value.all_beat_count);
    if (sha256Digest(value.paid_calls) !== sha256Digest(expectedCalls)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'paid_calls must equal exact all_beat_count cardinality',
        path: ['paid_calls'],
      });
    }
    const expectedSubject = safeDerivedDigest(
      () => deriveFactoryPaidBudgetApprovalSubjectDigestV1(value),
    );
    if (value.approval_subject_digest !== expectedSubject) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'approval_subject_digest does not match paid budget scope',
        path: ['approval_subject_digest'],
      });
    }
    const expectedIdempotency = safeDerivedDigest(
      () => deriveFactoryPaidBudgetIdempotencyKeyV1(value),
    );
    if (value.idempotency_key !== expectedIdempotency) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'idempotency_key does not match approval and budget authority',
        path: ['idempotency_key'],
      });
    }
    const expectedAuthority = safeDerivedDigest(
      () => deriveFactoryPaidBudgetAuthorityDigestV1(value),
    );
    if (value.authority_digest !== expectedAuthority) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'authority_digest does not match factory paid budget authority',
        path: ['authority_digest'],
      });
    }
  });

export function deriveFactoryPaidBudgetApprovalReceiptDigestV1(value: unknown): string {
  const data = { ...asRecord(value) };
  delete data.receipt_digest;
  return sha256Digest(data);
}

const UtcTimestamp = z.string().refine((value) => {
  try { strictUtcMicros(value); return true; } catch { return false; }
}, 'timestamp must be a real strict UTC instant');

export const FactoryPaidBudgetApprovalReceiptV1Schema = z
  .object({
    contract_version: z.literal('FactoryPaidBudgetApprovalReceipt.v1'),
    receipt_id: NonBlankString,
    workspace_id: UuidString,
    run_id: UuidString,
    factory_revision: NonNegativeSafeInteger,
    all_beat_count: AllBeatCount,
    paid_calls: FactoryPaidCallCardinalityV1Schema,
    max_total_cost_microunits: PositiveSafeInteger,
    currency: CurrencyCode,
    cost_profile_digest: DigestSchema,
    pricing_policy_revision: NonNegativeSafeInteger,
    approval_subject_digest: DigestSchema,
    approver_account_id: NonBlankString,
    decision: z.literal('approved'),
    policy_version: NonBlankString,
    state_revision: PositiveSafeInteger,
    approved_at_utc: UtcTimestamp,
    expires_at_utc: UtcTimestamp,
    revoked_at_utc: UtcTimestamp.nullable(),
    transaction_audit_id: NonBlankString,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string) => ctx.addIssue({ code: z.ZodIssueCode.custom, message });
    if (value.transaction_audit_id !== value.receipt_id) issue('transaction_audit_id must equal receipt_id');
    if (sha256Digest(value.paid_calls) !== sha256Digest(factoryPaidCallCardinalityV1(value.all_beat_count))) {
      issue('paid_calls must equal exact all_beat_count cardinality');
    }
    if (value.approval_subject_digest !== safeDerivedDigest(
      () => deriveFactoryPaidBudgetApprovalSubjectDigestV1(value),
    )) {
      issue('approval_subject_digest does not match paid budget scope');
    }
    try {
      const approved = strictUtcMicros(value.approved_at_utc);
      const expires = strictUtcMicros(value.expires_at_utc);
      if (expires <= approved) issue('expires_at_utc must follow approved_at_utc');
      if (value.revoked_at_utc !== null) {
        const revoked = strictUtcMicros(value.revoked_at_utc);
        if (revoked < approved || revoked > expires) issue('revoked_at_utc must fall within approval lifetime');
      }
    } catch { issue('receipt timestamps must be valid strict UTC'); }
    if (value.receipt_digest !== safeDerivedDigest(
      () => deriveFactoryPaidBudgetApprovalReceiptDigestV1(value),
    )) {
      issue('receipt_digest does not match approval receipt');
    }
  });

export type FactoryPaidBudgetApprovalReceiptV1 = z.infer<typeof FactoryPaidBudgetApprovalReceiptV1Schema>;

export interface FactoryPaidBudgetApprovalResolverV1 {
  isCurrentApproval(identity: {
    receipt_id: string;
    receipt_digest: string;
    workspace_id: string;
    run_id: string;
    factory_revision: number;
    state_revision: number;
    policy_version: string;
    approval_subject_digest: string;
    approver_account_id: string;
    cost_profile_digest: string;
    pricing_policy_revision: number;
  }): boolean;
}

export function factoryPaidBudgetApprovalReceiptStructurallyBindsV1(
  receipt: FactoryPaidBudgetApprovalReceiptV1,
  authority: FactoryPaidBudgetAuthorityV1,
): boolean {
  return receipt.receipt_id === authority.approval_receipt_id
    && receipt.receipt_digest === authority.approval_receipt_digest
    && receipt.workspace_id === authority.workspace_id && receipt.run_id === authority.run_id
    && receipt.factory_revision === authority.factory_revision
    && receipt.all_beat_count === authority.all_beat_count
    && sha256Digest(receipt.paid_calls) === sha256Digest(authority.paid_calls)
    && receipt.max_total_cost_microunits === authority.max_total_cost_microunits
    && receipt.currency === authority.currency
    && receipt.cost_profile_digest === authority.cost_profile_digest
    && receipt.pricing_policy_revision === authority.pricing_policy_revision
    && receipt.approval_subject_digest === authority.approval_subject_digest;
}

export function factoryPaidBudgetApprovalReceiptAuthorizesV1(
  receipt: FactoryPaidBudgetApprovalReceiptV1,
  authority: FactoryPaidBudgetAuthorityV1,
  atUtc: string,
  resolver: FactoryPaidBudgetApprovalResolverV1,
): boolean {
  if (!factoryPaidBudgetApprovalReceiptStructurallyBindsV1(receipt, authority)) return false;
  const at = strictUtcMicros(atUtc);
  if (at < strictUtcMicros(receipt.approved_at_utc)
    || at >= strictUtcMicros(receipt.expires_at_utc)
    || receipt.revoked_at_utc !== null) return false;
  return resolver.isCurrentApproval({
    receipt_id: receipt.receipt_id, receipt_digest: receipt.receipt_digest,
    workspace_id: receipt.workspace_id, run_id: receipt.run_id,
    factory_revision: receipt.factory_revision, state_revision: receipt.state_revision,
    policy_version: receipt.policy_version,
    approval_subject_digest: receipt.approval_subject_digest,
    approver_account_id: receipt.approver_account_id,
    cost_profile_digest: receipt.cost_profile_digest,
    pricing_policy_revision: receipt.pricing_policy_revision,
  });
}

const VERIFIED_AUTHORITY_TOKEN = Symbol('verified-factory-paid-budget-authority');

export class VerifiedFactoryPaidBudgetAuthorityV1 {
  readonly #authority: FactoryPaidBudgetAuthorityV1;

  private constructor(authority: FactoryPaidBudgetAuthorityV1, token: symbol) {
    if (token !== VERIFIED_AUTHORITY_TOKEN) {
      throw new TypeError('verified authority can only be minted by fromVerified');
    }
    this.#authority = authority;
    Object.freeze(this);
  }

  static mint(
    authority: FactoryPaidBudgetAuthorityV1,
    token: symbol,
  ): VerifiedFactoryPaidBudgetAuthorityV1 {
    return new VerifiedFactoryPaidBudgetAuthorityV1(authority, token);
  }

  get authority(): FactoryPaidBudgetAuthorityV1 { return this.#authority; }

  toJSON(): never {
    throw new TypeError('verified paid authority is not serializable');
  }
}

export function factoryPaidBudgetAuthorityFromVerifiedV1(
  value: unknown,
  receipt: FactoryPaidBudgetApprovalReceiptV1,
  atUtc: string,
  resolver: FactoryPaidBudgetApprovalResolverV1,
): VerifiedFactoryPaidBudgetAuthorityV1 {
  const authority = FactoryPaidBudgetAuthorityV1Schema.parse(value);
  if (!factoryPaidBudgetApprovalReceiptAuthorizesV1(receipt, authority, atUtc, resolver)) {
    throw new TypeError('authority requires current durable approval');
  }
  return VerifiedFactoryPaidBudgetAuthorityV1.mint(
    authority, VERIFIED_AUTHORITY_TOKEN,
  );
}

export interface FactoryPaidBudgetAuthorityBuildInputV1 {
  workspace_id: string;
  run_id: string;
  factory_revision: number;
  all_beat_count: number;
  max_total_cost_microunits: number;
  currency: string;
  cost_profile_digest: string;
  pricing_policy_revision: number;
  approval_receipt: FactoryPaidBudgetApprovalReceiptV1;
  at_utc: string;
  resolver: FactoryPaidBudgetApprovalResolverV1;
}

export function buildFactoryPaidBudgetAuthorityV1(
  input: FactoryPaidBudgetAuthorityBuildInputV1,
): VerifiedFactoryPaidBudgetAuthorityV1 {
  const body: Record<string, unknown> = {
    contract_version: FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1,
    workspace_id: input.workspace_id,
    run_id: input.run_id,
    factory_revision: input.factory_revision,
    all_beat_count: input.all_beat_count,
    paid_calls: factoryPaidCallCardinalityV1(input.all_beat_count),
    max_total_cost_microunits: input.max_total_cost_microunits,
    currency: input.currency,
    cost_profile_digest: input.cost_profile_digest,
    pricing_policy_revision: input.pricing_policy_revision,
    approval_receipt_id: input.approval_receipt.receipt_id,
    approval_receipt_digest: input.approval_receipt.receipt_digest,
  };
  body.approval_subject_digest = (
    deriveFactoryPaidBudgetApprovalSubjectDigestV1(body)
  );
  body.idempotency_key = deriveFactoryPaidBudgetIdempotencyKeyV1(body);
  body.authority_digest = deriveFactoryPaidBudgetAuthorityDigestV1(body);
  return factoryPaidBudgetAuthorityFromVerifiedV1(
    body, input.approval_receipt, input.at_utc, input.resolver,
  );
}

export type FactoryPaidCallCardinalityV1 = z.infer<
  typeof FactoryPaidCallCardinalityV1Schema
>;
export type FactoryPaidBudgetAuthorityV1 = z.infer<
  typeof FactoryPaidBudgetAuthorityV1Schema
>;
