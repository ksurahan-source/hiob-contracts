/**
 * PlanetOutput + ArtifactRef — TS mirror of factory/planet_output.py.
 *
 * ⚠️ AUTHORITY: Python. envelope 다이제스트는 Python `model_dump(by_alias=True)`에서
 * `output_digest`를 제거한 canonical-JSON SHA-256과 일치해야 한다.
 */
import { z } from 'zod';
import { DIGEST_RE, Digest, sha256Digest } from './digest.js';

export const DigestSchema = z.string().regex(DIGEST_RE);

export const ContractRefSchema = z
  .object({
    name: z.string(),
    version: z.string(),
    schema_digest: DigestSchema,
  })
  .strict();
export type ContractRef = z.infer<typeof ContractRefSchema>;

export const ArtifactRefSchema = z
  .object({
    artifact_id: z.string(),
    kind: z.string(),
    uri: z.string(),
    sha256: DigestSchema,
    mime: z.string(),
    bytes_len: z.number().int().nonnegative(),
    duration_ms: z.number().int().nonnegative().nullable().default(null),
    width: z.number().int().nonnegative().nullable().default(null),
    height: z.number().int().nonnegative().nullable().default(null),
    beat_index: z.number().int().nonnegative().nullable().default(null),
    producer_planet: z.string(),
    producer_node_id: z.string(),
    execution_id: z.string(),
    producer_revision: z.string(),
    image_digest: DigestSchema.nullable().default(null),
    source_output_digests: z.array(DigestSchema).default([]),
    edge_receipt_digests: z.array(DigestSchema).default([]),
    provenance_refs: z.array(z.string()).default([]),
    consent_refs: z.array(z.string()).default([]),
  })
  .strict();
export type ArtifactRef = z.infer<typeof ArtifactRefSchema>;

const ProducerSchema = z
  .object({ planet: z.string(), node_id: z.string(), revision: z.string() })
  .strict();

export const PlanetOutputSchema = z
  .object({
    schema: z.literal('hiob.planet-output.v1').default('hiob.planet-output.v1'),
    output_id: z.string(),
    run_id: z.string(),
    factory_revision: z.number().int().nonnegative(),
    workspace_id: z.string(),
    trace_id: z.string(),
    execution_id: z.string(),
    attempt_no: z.number().int().min(1),
    producer: ProducerSchema,
    contract: ContractRefSchema,
    payload: z.record(z.string(), z.unknown()),
    payload_digest: DigestSchema,
    artifacts: z.array(ArtifactRefSchema).default([]),
    output_digest: DigestSchema,
    prior_edge_receipt_id: z.string().nullable().default(null),
    emitted_at: z.string(),
  })
  .strict()
  .superRefine((o, ctx) => {
    if (o.payload_digest !== sha256Digest(o.payload)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'payload_digest does not match payload' });
    }
    if (o.output_digest !== computeOutputDigest(o)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'output_digest does not match envelope' });
    }
  });
export type PlanetOutput = z.infer<typeof PlanetOutputSchema>;

/** envelope에서 `output_digest`를 제외한 canonical-JSON SHA-256 (Python `_compute_output_digest`). */
export function computeOutputDigest(out: Record<string, unknown>): Digest {
  const body: Record<string, unknown> = { ...out };
  delete body.output_digest;
  return sha256Digest(body);
}

export interface PlanetOutputInput {
  output_id: string;
  run_id: string;
  factory_revision: number;
  workspace_id: string;
  trace_id: string;
  execution_id: string;
  attempt_no: number;
  producer: { planet: string; node_id: string; revision: string };
  contract: ContractRef;
  payload: Record<string, unknown>;
  emitted_at: string;
  artifacts?: ArtifactRef[];
  prior_edge_receipt_id?: string | null;
}

/** payload_digest/output_digest를 결정적으로 채워 PlanetOutput 생성 (Python `build`). */
export function buildPlanetOutput(input: PlanetOutputInput): PlanetOutput {
  const artifacts = (input.artifacts ?? []).map((a) => ArtifactRefSchema.parse(a));
  const payload_digest = sha256Digest(input.payload);
  const envelope = {
    schema: 'hiob.planet-output.v1' as const,
    output_id: input.output_id,
    run_id: input.run_id,
    factory_revision: input.factory_revision,
    workspace_id: input.workspace_id,
    trace_id: input.trace_id,
    execution_id: input.execution_id,
    attempt_no: input.attempt_no,
    producer: input.producer,
    contract: input.contract,
    payload: input.payload,
    payload_digest,
    artifacts,
    prior_edge_receipt_id: input.prior_edge_receipt_id ?? null,
    emitted_at: input.emitted_at,
  };
  const output_digest = computeOutputDigest(envelope);
  return PlanetOutputSchema.parse({ ...envelope, output_digest });
}

/** 다이제스트 재계산으로 envelope 내부 정합성 확인 (Python `verify`). */
export function verifyPlanetOutput(out: PlanetOutput): boolean {
  return out.payload_digest === sha256Digest(out.payload) && out.output_digest === computeOutputDigest(out);
}
