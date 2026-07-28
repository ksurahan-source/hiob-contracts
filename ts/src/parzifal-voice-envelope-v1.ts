import { z } from 'zod';

import { characterIdentityBindingErrorV1 } from './character-identity-v1.js';
import { sha256Digest } from './factory/digest.js';

const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');

export type ParzifalVoiceEnvelopeDigestInputV1 = {
  contract_version: 'ParzifalVoiceEnvelope.v1';
  workspace_id: string;
  run_id: string;
  subject_id: string;
  face_id: string;
  voice_id: string;
  identity_binding_digest: string;
  voice_spec_digest: string;
};

export function deriveParzifalVoiceEnvelopeDigestV1(
  value: ParzifalVoiceEnvelopeDigestInputV1 | Record<string, unknown>,
): string {
  const input = value as Record<string, unknown>;
  const payload: Record<string, unknown> = {};
  for (const key of [
    'contract_version',
    'workspace_id',
    'run_id',
    'subject_id',
    'face_id',
    'voice_id',
    'identity_binding_digest',
    'voice_spec_digest',
  ]) {
    if (key in input) payload[key] = input[key];
  }
  return sha256Digest(payload);
}

export const ParzifalVoiceEnvelopeV1Schema = z
  .object({
    contract_version: z.literal('ParzifalVoiceEnvelope.v1'),
    workspace_id: NonBlankString,
    run_id: NonBlankString,
    subject_id: NonBlankString,
    face_id: NonBlankString,
    voice_id: NonBlankString,
    identity_binding_digest: DigestSchema,
    voice_spec_digest: DigestSchema,
    envelope_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const bindingError = characterIdentityBindingErrorV1(value);
    if (bindingError) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: bindingError,
        path: ['identity_binding_digest'],
      });
    }
    if (value.envelope_digest !== deriveParzifalVoiceEnvelopeDigestV1(value)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'envelope_digest does not match Parzifal voice envelope content',
        path: ['envelope_digest'],
      });
    }
  });

export type ParzifalVoiceEnvelopeV1 = z.infer<typeof ParzifalVoiceEnvelopeV1Schema>;
