/** Atomic, server-owned make context for one Ares V3 command. */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const UuidSchema = z
  .string()
  .regex(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    'UUID must use canonical lowercase form',
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

export function deriveAresV3MakeContextDigestV1(
  value: Record<string, unknown>,
): string {
  const field = (name: string): unknown => {
    if (!(name in value) || value[name] === undefined) {
      throw new TypeError(`${name} is required for make context digest`);
    }
    return value[name];
  };
  return sha256Digest({
    workspace_id: field('workspace_id'),
    run_id: field('run_id'),
    brand_id: field('brand_id'),
    subject_id: field('subject_id'),
    product_id: field('product_id'),
    character_lock_digest: field('character_lock_digest'),
    character_lock_version: field('character_lock_version'),
    product_lock_digest: field('product_lock_digest'),
    artemis_approval_receipt_id: field('artemis_approval_receipt_id'),
    artemis_approval_receipt_digest:
      field('artemis_approval_receipt_digest'),
    artemis_approval_state_revision:
      field('artemis_approval_state_revision'),
  });
}

export const AresV3MakeContextV1Schema = z
  .object({
    contract_version: z.literal('AresV3MakeContext.v1'),
    workspace_id: UuidSchema,
    run_id: UuidSchema,
    brand_id: UuidSchema,
    subject_id: NonBlankString,
    product_id: NonBlankString,
    character_lock_digest: DigestSchema,
    character_lock_version: z.number().int().safe().positive(),
    product_lock_digest: DigestSchema,
    artemis_approval_receipt_id: NonBlankString,
    artemis_approval_receipt_digest: DigestSchema,
    artemis_approval_state_revision: z.number().int().safe().positive(),
    make_context_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (
      value.make_context_digest
      !== deriveAresV3MakeContextDigestV1(value)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'make_context_digest does not match server make context',
        path: ['make_context_digest'],
      });
    }
  })
  .transform(deepFreeze);

export type AresV3MakeContextV1 = z.infer<
  typeof AresV3MakeContextV1Schema
>;
