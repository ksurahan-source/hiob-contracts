/** TypeScript/Zod mirror of Python FactoryPaidBudgetAuthority.v1. */
import { z } from 'zod';

import { DIGEST_RE, sha256Digest } from './factory/digest.js';

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
    approval_receipt_id: NonBlankString,
    approval_receipt_digest: DigestSchema,
    approval_subject_digest: DigestSchema,
    idempotency_key: DigestSchema,
    authority_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const expectedCalls = factoryPaidCallCardinalityV1(value.all_beat_count);
    if (sha256Digest(value.paid_calls) !== sha256Digest(expectedCalls)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'paid_calls must equal exact all_beat_count cardinality',
        path: ['paid_calls'],
      });
    }
    const expectedSubject = deriveFactoryPaidBudgetApprovalSubjectDigestV1(value);
    if (value.approval_subject_digest !== expectedSubject) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'approval_subject_digest does not match paid budget scope',
        path: ['approval_subject_digest'],
      });
    }
    const expectedIdempotency = deriveFactoryPaidBudgetIdempotencyKeyV1(value);
    if (value.idempotency_key !== expectedIdempotency) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'idempotency_key does not match approval and budget authority',
        path: ['idempotency_key'],
      });
    }
    const expectedAuthority = deriveFactoryPaidBudgetAuthorityDigestV1(value);
    if (value.authority_digest !== expectedAuthority) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'authority_digest does not match factory paid budget authority',
        path: ['authority_digest'],
      });
    }
  });

export interface FactoryPaidBudgetAuthorityBuildInputV1 {
  workspace_id: string;
  run_id: string;
  factory_revision: number;
  all_beat_count: number;
  max_total_cost_microunits: number;
  currency: string;
  approval_receipt_id: string;
  approval_receipt_digest: string;
}

export function buildFactoryPaidBudgetAuthorityV1(
  input: FactoryPaidBudgetAuthorityBuildInputV1,
): FactoryPaidBudgetAuthorityV1 {
  const body: Record<string, unknown> = {
    contract_version: FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1,
    workspace_id: input.workspace_id,
    run_id: input.run_id,
    factory_revision: input.factory_revision,
    all_beat_count: input.all_beat_count,
    paid_calls: factoryPaidCallCardinalityV1(input.all_beat_count),
    max_total_cost_microunits: input.max_total_cost_microunits,
    currency: input.currency,
    approval_receipt_id: input.approval_receipt_id,
    approval_receipt_digest: input.approval_receipt_digest,
  };
  body.approval_subject_digest = (
    deriveFactoryPaidBudgetApprovalSubjectDigestV1(body)
  );
  body.idempotency_key = deriveFactoryPaidBudgetIdempotencyKeyV1(body);
  body.authority_digest = deriveFactoryPaidBudgetAuthorityDigestV1(body);
  return FactoryPaidBudgetAuthorityV1Schema.parse(body);
}

export type FactoryPaidCallCardinalityV1 = z.infer<
  typeof FactoryPaidCallCardinalityV1Schema
>;
export type FactoryPaidBudgetAuthorityV1 = z.infer<
  typeof FactoryPaidBudgetAuthorityV1Schema
>;
