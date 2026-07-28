import {z} from 'zod';

import {sha256Digest} from './factory/digest.js';

const boundedNonBlankString = (maxLength: number) =>
  z
    .string()
    .max(maxLength)
    .refine((value) => value.trim().length > 0, 'string must not be blank');
const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');

export type VoiceSpecDigestInputV1 = {
  contract_version?: 'VoiceSpec.v1';
  subject_id: string;
  rhythm: string;
  vocabulary: readonly string[];
  forbidden_phrases: readonly string[];
  approved_examples: readonly string[];
};

export function deriveVoiceSpecDigestV1(
  value: VoiceSpecDigestInputV1 | Record<string, unknown>,
): string {
  const input = value as Record<string, unknown>;
  const payload: Record<string, unknown> = {};
  for (const key of [
    'contract_version',
    'subject_id',
    'rhythm',
    'vocabulary',
    'forbidden_phrases',
    'approved_examples',
  ]) {
    if (key in input) payload[key] = input[key];
  }
  return sha256Digest(payload);
}

export const VoiceSpecV1Schema = z
  .object({
    contract_version: z.literal('VoiceSpec.v1').default('VoiceSpec.v1'),
    subject_id: boundedNonBlankString(128),
    rhythm: boundedNonBlankString(300),
    vocabulary: z.array(boundedNonBlankString(80)).max(12),
    forbidden_phrases: z.array(boundedNonBlankString(120)).max(12),
    approved_examples: z
      .array(boundedNonBlankString(500))
      .min(3)
      .max(5),
    voice_spec_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.voice_spec_digest !== deriveVoiceSpecDigestV1(value)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'voice_spec_digest does not match VoiceSpec content',
        path: ['voice_spec_digest'],
      });
    }
  });

export type VoiceSpecV1 = z.infer<typeof VoiceSpecV1Schema>;
