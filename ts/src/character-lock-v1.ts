import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
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
const CanonicalNonBlankString = NonBlankString.refine(
  (value) => !hasUnpairedSurrogate(value),
  'text must contain valid Unicode scalar values',
);
const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const UuidSchema = z
  .string()
  .regex(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    'UUID must be canonical lowercase RFC 4122',
  );

const DIGEST_FIELDS = [
  'contract_version',
  'workspace_id',
  'brand_slug',
  'subject_id',
  'version',
  'face_id',
  'voice_id',
  'source_receipt_ref',
  'source_record_version',
  'source_receipt_digest',
] as const;

const CharacterLockDigestSourceShape = {
  contract_version: z.literal('CharacterLock.v1'),
  workspace_id: UuidSchema,
  brand_slug: CanonicalNonBlankString,
  subject_id: CanonicalNonBlankString,
  version: z.number().int().safe().positive(),
  face_id: CanonicalNonBlankString,
  voice_id: CanonicalNonBlankString,
  source_receipt_ref: CanonicalNonBlankString,
  source_record_version: z.number().int().safe().positive(),
  source_receipt_digest: DigestSchema,
};
const CharacterLockDigestSourceV1Schema = z
  .object(CharacterLockDigestSourceShape)
  .strict();

function digestSourceFrom(
  value: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    DIGEST_FIELDS.map((field) => [field, value[field]]),
  );
}

export function deriveCharacterLockDigestV1(
  value: Record<string, unknown>,
): string {
  const source = CharacterLockDigestSourceV1Schema.parse(
    digestSourceFrom(value),
  );
  return sha256Digest(source);
}

export const CharacterLockV1Schema = z
  .object({
    ...CharacterLockDigestSourceShape,
    digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const source = CharacterLockDigestSourceV1Schema.safeParse(
      digestSourceFrom(value),
    );
    if (source.success && value.digest !== sha256Digest(source.data)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'digest does not match CharacterLock payload',
        path: ['digest'],
      });
    }
  })
  .transform((value) => Object.freeze(value));

export type CharacterLockV1 = z.infer<typeof CharacterLockV1Schema>;
