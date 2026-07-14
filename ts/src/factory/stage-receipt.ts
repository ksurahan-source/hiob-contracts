/**
 * StageReceipt — TS mirror of factory/stage_receipt.py.
 *
 * ⚠️ AUTHORITY: Python. spawn handle ≠ success: accepted/running은 non-terminal.
 */
import { z } from 'zod';
import { DigestSchema } from './planet-output.js';

export type StageStatus =
  | 'accepted'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'superseded';

export const TERMINAL_STAGE_STATUSES: ReadonlySet<string> = new Set([
  'succeeded',
  'failed',
  'cancelled',
  'superseded',
]);

export const StageErrorSchema = z
  .object({ code: z.string(), retryable: z.boolean(), details: z.string().default('') })
  .strict();
export type StageError = z.infer<typeof StageErrorSchema>;

export const StageReceiptSchema = z
  .object({
    operation_id: z.string(),
    stage_id: z.string(),
    planet: z.string(),
    node_id: z.string(),
    producer_revision: z.string(),
    image_digest: DigestSchema.nullable().default(null),
    contract_version: z.string(),
    input_digests: z.array(DigestSchema).default([]),
    output_digests: z.array(DigestSchema).default([]),
    status: z.enum(['accepted', 'running', 'succeeded', 'failed', 'cancelled', 'superseded']),
    attempt_no: z.number().int().min(1),
    started_at: z.string(),
    completed_at: z.string().nullable().default(null),
    cost: z.record(z.string(), z.unknown()).nullable().default(null),
    warnings: z.array(z.string()).default([]),
    error: StageErrorSchema.nullable().default(null),
  })
  .strict()
  .superRefine((r, ctx) => {
    const isTerminal = TERMINAL_STAGE_STATUSES.has(r.status);
    if (isTerminal && r.completed_at === null) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `terminal status ${r.status} requires completed_at` });
    }
    if (!isTerminal && r.completed_at !== null) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `non-terminal status ${r.status} must not set completed_at` });
    }
    if (r.status === 'succeeded') {
      if (r.output_digests.length === 0) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'succeeded stage must produce at least one output digest' });
      }
      if (r.error !== null) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'succeeded stage cannot carry an error' });
      }
    }
    if (r.status === 'failed' && r.error === null) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'failed stage must carry a structured error' });
    }
  });
export type StageReceipt = z.infer<typeof StageReceiptSchema>;

export function isStageTerminal(r: StageReceipt): boolean {
  return TERMINAL_STAGE_STATUSES.has(r.status);
}

export function isStageSuccess(r: StageReceipt): boolean {
  return r.status === 'succeeded';
}
