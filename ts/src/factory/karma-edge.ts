/**
 * Karma edge refinery — TS mirror of factory/karma_edge.py.
 *
 * ⚠️ AUTHORITY: Python. idempotency key 유도와 receipt invariant는 Python과 일치.
 */
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { Digest, canonicalJson, sha256Digest } from './digest.js';
import { ContractRefSchema, DigestSchema, PlanetOutputSchema } from './planet-output.js';

export const TargetRefSchema = z
  .object({ planet: z.string(), node_id: z.string(), input_contract: ContractRefSchema })
  .strict();
export type TargetRef = z.infer<typeof TargetRefSchema>;

export const PolicyRefSchema = z
  .object({ id: z.string(), version: z.string(), digest: DigestSchema })
  .strict();
export type PolicyRef = z.infer<typeof PolicyRefSchema>;

export const TransformLogEntrySchema = z
  .object({
    op: z.enum(['copy', 'rename', 'normalize', 'derive', 'drop']),
    target_path: z.string(),
    source_paths: z.array(z.string()).default([]),
    rule_id: z.string(),
    evidence_refs: z.array(z.string()).default([]),
    value_digest: DigestSchema,
    origin: z.enum(['source', 'deterministic_rule', 'karma_inference', 'human_override']),
  })
  .strict();
export type TransformLogEntry = z.infer<typeof TransformLogEntrySchema>;

export const EdgeViolationSchema = z
  .object({ code: z.string(), path: z.string(), severity: z.enum(['error', 'warning']) })
  .strict();
export type EdgeViolation = z.infer<typeof EdgeViolationSchema>;

export const MapperRefSchema = z
  .object({
    planet: z.literal('karma').default('karma'),
    node_id: z.string(),
    revision: z.string(),
    policy_digest: DigestSchema,
  })
  .strict();
export type MapperRef = z.infer<typeof MapperRefSchema>;

export type EdgeDecision = 'accepted' | 'blocked' | 'needs_human';

/**
 * 엣지 idempotency key (factory/karma_edge.py `derive_idempotency_key`와 동일).
 * ``SHA256(run_id | factory_revision | edge_id | ordered source_output_digests |
 *          target schema digest | policy digest)`` — 소스 순서는 유의미.
 */
export function deriveIdempotencyKey(args: {
  run_id: string;
  factory_revision: number;
  edge_id: string;
  source_output_digests: Digest[];
  target_schema_digest: Digest;
  policy_digest: Digest;
}): string {
  const material = canonicalJson([
    args.run_id,
    args.factory_revision,
    args.edge_id,
    [...args.source_output_digests],
    args.target_schema_digest,
    args.policy_digest,
  ]);
  return `sha256:${createHash('sha256').update(material, 'utf8').digest('hex')}`;
}

export const KarmaRefineRequestSchema = z
  .object({
    edge_id: z.string(),
    run_id: z.string(),
    factory_revision: z.number().int().nonnegative(),
    workspace_id: z.string(),
    trace_id: z.string(),
    sources: z.array(PlanetOutputSchema).min(1),
    target: TargetRefSchema,
    policy: PolicyRefSchema,
    evidence_refs: z.array(z.string()).default([]),
    approval_receipt_refs: z.array(z.string()).default([]),
    idempotency_key: z.string(),
    deadline_at: z.string(),
  })
  .strict()
  .superRefine((r, ctx) => {
    const expected = deriveIdempotencyKey({
      run_id: r.run_id,
      factory_revision: r.factory_revision,
      edge_id: r.edge_id,
      source_output_digests: r.sources.map((s) => s.output_digest),
      target_schema_digest: r.target.input_contract.schema_digest,
      policy_digest: r.policy.digest,
    });
    if (r.idempotency_key !== expected) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'idempotency_key does not match derived key' });
    }
  });
export type KarmaRefineRequest = z.infer<typeof KarmaRefineRequestSchema>;

export const KarmaEdgeReceiptSchema = z
  .object({
    receipt_id: z.string(),
    edge_id: z.string(),
    run_id: z.string(),
    factory_revision: z.number().int().nonnegative(),
    source_output_digests: z.array(DigestSchema).min(1),
    target_contract: ContractRefSchema,
    decision: z.enum(['accepted', 'blocked', 'needs_human']),
    target_input: z.record(z.string(), z.unknown()).nullable().default(null),
    target_input_digest: DigestSchema.nullable().default(null),
    transform_log: z.array(TransformLogEntrySchema).default([]),
    violations: z.array(EdgeViolationSchema).default([]),
    waiver_receipt_refs: z.array(z.string()).default([]),
    mapper: MapperRefSchema,
    created_at: z.string(),
  })
  .strict()
  .superRefine((r, ctx) => {
    const hasError = r.violations.some((v) => v.severity === 'error');
    if (r.decision === 'accepted') {
      if (hasError) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'accepted receipt cannot carry error-severity violations' });
      }
      if (r.target_input === null || r.target_input_digest === null) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'accepted receipt must carry target_input + target_input_digest' });
      } else if (r.target_input_digest !== sha256Digest(r.target_input)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'target_input_digest does not match target_input' });
      }
    } else if (r.target_input !== null || r.target_input_digest !== null) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `${r.decision} receipt must not carry a target_input projection` });
    }
  });
export type KarmaEdgeReceipt = z.infer<typeof KarmaEdgeReceiptSchema>;

/** receipt가 이 target_input 다이제스트를 승인하면 true (§4.2 step 6). */
export function receiptAuthorizes(receipt: KarmaEdgeReceipt, targetInputDigest: Digest): boolean {
  return (
    receipt.decision === 'accepted' &&
    receipt.target_input_digest !== null &&
    receipt.target_input_digest === targetInputDigest
  );
}
