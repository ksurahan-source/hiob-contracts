/** Strict Story OS maps and the only four permitted experiment treatment axes. */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

export const MAX_PROOF_REFERENCES_V1 = 12;
export const MAX_VARIANTS_V1 = 12;

const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');

function hasUnpairedSurrogate(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const low = value.charCodeAt(index + 1);
      if (!(low >= 0xdc00 && low <= 0xdfff)) return true;
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true;
    }
  }
  return false;
}

function assertJsonUnicodeScalars(value: unknown): void {
  if (typeof value === 'string') {
    if (hasUnpairedSurrogate(value)) {
      throw new TypeError('text must contain valid Unicode scalar values');
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) assertJsonUnicodeScalars(item);
    return;
  }
  if (value !== null && typeof value === 'object') {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (hasUnpairedSurrogate(key)) {
        throw new TypeError('text must contain valid Unicode scalar values');
      }
      assertJsonUnicodeScalars(item);
    }
  }
}

function isPythonStripWhitespace(char: string): boolean {
  const code = char.codePointAt(0);
  return code !== undefined && (
    (code >= 0x0009 && code <= 0x000d)
    || (code >= 0x001c && code <= 0x001f)
    || code === 0x0020
    || code === 0x0085
    || code === 0x00a0
    || code === 0x1680
    || (code >= 0x2000 && code <= 0x200a)
    || code === 0x2028
    || code === 0x2029
    || code === 0x202f
    || code === 0x205f
    || code === 0x3000
  );
}

function isPythonBlank(value: string): boolean {
  return value.length === 0 || [...value].every(isPythonStripWhitespace);
}

const boundedNonBlankString = (maxLength: number) => z
  .string()
  .refine((value) => !isPythonBlank(value), 'string must not be blank')
  .refine(
    (value) => !hasUnpairedSurrogate(value),
    'text must contain valid Unicode scalar values',
  )
  .refine(
    (value) => [...value].length <= maxLength,
    `string must contain at most ${maxLength} Unicode scalars`,
  );

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

function requiredField(value: Record<string, unknown>, field: string): unknown {
  if (!(field in value) || value[field] === undefined) {
    throw new TypeError(`${field} is required for Story OS digest`);
  }
  return value[field];
}

function digestPayload(
  value: Record<string, unknown>,
  fields: readonly string[],
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [field, requiredField(value, field)]),
  );
}

export function deriveStoryMapDigestV1(value: Record<string, unknown>): string {
  const payload = digestPayload(value, [
    'contract_version', 'customer_scene', 'bad_alternative_tension',
    'urgent_moment', 'emotional_stake', 'proof_references', 'objection',
    'offer', 'cta', 'target_metric', 'content_mode', 'story_policy_digest',
  ]);
  assertJsonUnicodeScalars(payload);
  return sha256Digest(payload);
}

export function deriveExperimentHypothesisDigestV1(
  value: Record<string, unknown>,
): string {
  const payload = digestPayload(value, [
    'contract_version', 'story_map_digest', 'hypothesis',
  ]);
  assertJsonUnicodeScalars(payload);
  return sha256Digest(payload);
}

export function deriveVariantSetDigestV1(value: Record<string, unknown>): string {
  const payload = digestPayload(value, [
    'contract_version', 'story_map', 'story_map_digest',
    'experiment_hypothesis', 'variants',
  ]);
  assertJsonUnicodeScalars(payload);
  return sha256Digest(payload);
}

const ProofReferenceV1Schema = z.object({
  proof_ref_id: boundedNonBlankString(160),
  proof_fact_digest: DigestSchema,
}).strict();

export const StoryMapV1Schema = z.object({
  contract_version: z.literal('StoryMap.v1'),
  customer_scene: boundedNonBlankString(1200),
  bad_alternative_tension: boundedNonBlankString(1200),
  urgent_moment: boundedNonBlankString(600),
  emotional_stake: boundedNonBlankString(600),
  proof_references: z.array(ProofReferenceV1Schema).min(1).max(MAX_PROOF_REFERENCES_V1),
  objection: boundedNonBlankString(600),
  offer: boundedNonBlankString(600),
  cta: boundedNonBlankString(300),
  target_metric: boundedNonBlankString(160),
  content_mode: z.enum(['ugc', 'information']),
  story_policy_digest: DigestSchema,
  story_map_digest: DigestSchema,
}).strict().superRefine((value, ctx) => {
  const ids = value.proof_references.map((reference) => reference.proof_ref_id);
  if (new Set(ids).size !== ids.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['proof_references'],
      message: 'proof_references contains duplicate proof_ref_id',
    });
  }
  try {
    if (value.story_map_digest === deriveStoryMapDigestV1(value)) return;
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['story_map_digest'],
      message: 'story_map_digest does not match StoryMap content',
    });
  } catch {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: [],
      message: 'StoryMap text must contain valid Unicode scalar values',
    });
  }
}).transform(deepFreeze);

export type StoryMapV1 = z.infer<typeof StoryMapV1Schema>;

export const ExperimentHypothesisV1Schema = z.object({
  contract_version: z.literal('ExperimentHypothesis.v1'),
  story_map_digest: DigestSchema,
  hypothesis: boundedNonBlankString(1200),
  experiment_hypothesis_digest: DigestSchema,
}).strict().superRefine((value, ctx) => {
  try {
    if (value.experiment_hypothesis_digest === deriveExperimentHypothesisDigestV1(value)) return;
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['experiment_hypothesis_digest'],
      message: 'experiment_hypothesis_digest does not match ExperimentHypothesis content',
    });
  } catch {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: [],
      message: 'ExperimentHypothesis text must contain valid Unicode scalar values',
    });
  }
}).transform(deepFreeze);

export type ExperimentHypothesisV1 = z.infer<typeof ExperimentHypothesisV1Schema>;

const StoryVariantV1Schema = z.object({
  variant_id: boundedNonBlankString(160),
  story_map_digest: DigestSchema,
  hook: boundedNonBlankString(600),
  proof_order: z.array(boundedNonBlankString(160)).min(1).max(MAX_PROOF_REFERENCES_V1),
  framing: boundedNonBlankString(1200),
  cta: boundedNonBlankString(300),
}).strict();

export const VariantSetV1Schema = z.object({
  contract_version: z.literal('VariantSet.v1'),
  story_map: StoryMapV1Schema,
  story_map_digest: DigestSchema,
  experiment_hypothesis: ExperimentHypothesisV1Schema,
  variants: z.array(StoryVariantV1Schema).min(1).max(MAX_VARIANTS_V1),
  variant_set_digest: DigestSchema,
}).strict().superRefine((value, ctx) => {
  if (value.story_map_digest !== value.story_map.story_map_digest) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['story_map_digest'],
      message: 'story_map_digest does not match embedded StoryMap',
    });
  }
  if (value.experiment_hypothesis.story_map_digest !== value.story_map.story_map_digest) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['experiment_hypothesis', 'story_map_digest'],
      message: 'experiment_hypothesis is bound to a different story_map_digest',
    });
  }
  const variantIds = value.variants.map((variant) => variant.variant_id);
  if (new Set(variantIds).size !== variantIds.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['variants'],
      message: 'variants contains duplicate variant_id',
    });
  }
  const expectedProofIds = value.story_map.proof_references.map(
    (reference) => reference.proof_ref_id,
  );
  for (const [index, variant] of value.variants.entries()) {
    if (variant.story_map_digest !== value.story_map.story_map_digest) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['variants', index, 'story_map_digest'],
        message: 'variant story_map_digest does not match VariantSet',
      });
    }
    if (
      variant.proof_order.length !== expectedProofIds.length
      || new Set(variant.proof_order).size !== expectedProofIds.length
      || variant.proof_order.some((proofRefId) => !expectedProofIds.includes(proofRefId))
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['variants', index, 'proof_order'],
        message: 'variant proof_order must be an exact ordering of StoryMap proof_ref_id values',
      });
    }
  }
  try {
    if (value.variant_set_digest === deriveVariantSetDigestV1(value)) return;
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['variant_set_digest'],
      message: 'variant_set_digest does not match VariantSet content',
    });
  } catch {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: [],
      message: 'VariantSet text must contain valid Unicode scalar values',
    });
  }
}).transform(deepFreeze);

export type VariantSetV1 = z.infer<typeof VariantSetV1Schema>;
