/**
 * ApprovalReceipt + DegradationReceipt — TS mirror of factory/approval.py,
 * factory/degradation.py.
 *
 * ⚠️ AUTHORITY: Python. 승인은 boolean이 아니라 content digest에 결박된다.
 */
import { z } from 'zod';
import { Digest } from './digest.js';
import { DigestSchema } from './planet-output.js';

export const ApprovalReceiptSchema = z
  .object({
    approval_id: z.string(),
    kind: z.enum(['script', 'production_plan', 'composition_snapshot', 'waiver']),
    run_id: z.string(),
    factory_revision: z.number().int().nonnegative(),
    target_id: z.string(),
    target_digest: DigestSchema,
    decision: z.enum(['approved', 'rejected']),
    approved_by: z.string(),
    approved_at: z.string(),
    policy_version: z.string(),
    expires_at: z.string().nullable().default(null),
    revoked_at: z.string().nullable().default(null),
  })
  .strict();
export type ApprovalReceipt = z.infer<typeof ApprovalReceiptSchema>;

/**
 * receipt가 정확히 `targetDigest`를 승인하고 여전히 유효하면 true.
 * boolean-only / stale / revoked / expired / mismatched 승인을 거부 (FR-8).
 * `now`는 ISO-8601 문자열(UTC는 사전식 정렬=시간순), 호출자가 주입(계약엔 시계 없음).
 */
export function approvalAuthorizes(
  a: ApprovalReceipt,
  targetDigest: Digest,
  now?: string
): boolean {
  if (a.decision !== 'approved') return false;
  if (a.revoked_at !== null) return false;
  if (a.target_digest !== targetDigest) return false;
  if (a.expires_at !== null && now !== undefined && now >= a.expires_at) return false;
  return true;
}

export const DegradationReceiptSchema = z
  .object({
    degradation_id: z.string(),
    run_id: z.string(),
    factory_revision: z.number().int().nonnegative(),
    omitted_stage: z.string(),
    omitted_artifact_kind: z.string(),
    source_digests: z.array(DigestSchema).default([]),
    plan_digest: DigestSchema,
    user_impact: z.string(),
    authorized_by: z.string(),
    policy_authority: z.string().default(''),
    expires_at: z.string().nullable().default(null),
    recovery_action: z.string(),
    created_at: z.string(),
  })
  .strict()
  .superRefine((d, ctx) => {
    if (d.user_impact.trim() === '') {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'degradation must state the user-visible impact' });
    }
    if (d.recovery_action.trim() === '') {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'degradation must state a recovery action' });
    }
    if (d.authorized_by.trim() === '') {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'degradation must name an approver or policy authority' });
    }
  });
export type DegradationReceipt = z.infer<typeof DegradationReceiptSchema>;
