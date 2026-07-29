/** Exact provider input emitted by `ares.script.prepare_generation`. */
import { z } from 'zod';

import {
  characterIdentityBindingErrorV1,
} from '../../character-identity-v1.js';
import { sha256Digest } from '../../factory/digest.js';
import { deriveVoiceSpecDigestV1 } from '../../voice-spec-v1.js';

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
    for (const [key, item] of Object.entries(
      value as Record<string, unknown>,
    )) {
      if (hasUnpairedSurrogate(key)) {
        throw new TypeError('text must contain valid Unicode scalar values');
      }
      assertJsonUnicodeScalars(item);
    }
  }
}

const boundedNonBlankString = (maxLength: number) =>
  z
    .string()
    .refine(
      (value) => value.trim().length > 0,
      'string must not be blank',
    )
    .refine(
      (value) => !hasUnpairedSurrogate(value),
      'text must contain valid Unicode scalar values',
    )
    .refine(
      (value) => [...value].length <= maxLength,
      `string must contain at most ${maxLength} Unicode scalars`,
    );
const NonBlankString = boundedNonBlankString(512);

const DIGEST_FIELDS = [
  'contract_version',
  'workspace_id',
  'run_id',
  'script_revision_id',
  'plan_revision_id',
  'factory_revision',
  'character_lock',
  'voice_spec',
  'current_character',
  'conflict',
  'adjacent_beat_summaries',
  'memories',
] as const;

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

export function deriveAresScriptGenerationInputDigestV1(
  value: Record<string, unknown>,
): string {
  const body = Object.fromEntries(
    DIGEST_FIELDS.map((field) => {
      if (!(field in value) || value[field] === undefined) {
        throw new TypeError(`${field} is required for generation input digest`);
      }
      return [field, value[field]];
    }),
  );
  assertJsonUnicodeScalars(body);
  return sha256Digest(body);
}

export const AresCharacterIdentityProjectionV1Schema = z
  .object({
    persona_id: boundedNonBlankString(128),
    face_id: boundedNonBlankString(256),
    voice_id: boundedNonBlankString(256),
    identity_binding_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const error = characterIdentityBindingErrorV1({
      subject_id: value.persona_id,
      face_id: value.face_id,
      voice_id: value.voice_id,
      identity_binding_digest: value.identity_binding_digest,
    });
    if (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error,
        path: ['identity_binding_digest'],
      });
    }
  });

export const AresProvenanceMemoryV1Schema = z
  .object({
    text: boundedNonBlankString(500),
    provenance: boundedNonBlankString(200),
  })
  .strict();

export const AresVoiceSpecProjectionV1Schema = z
  .object({
    contract_version: z.literal('VoiceSpec.v1'),
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

export const AresScriptGenerationInputV1Schema = z
  .object({
    contract_version: z.literal('AresScriptGenerationInput.v1'),
    workspace_id: NonBlankString,
    run_id: NonBlankString,
    script_revision_id: NonBlankString,
    plan_revision_id: NonBlankString,
    factory_revision: z.number().int().min(0).max(2_147_483_647),
    character_lock: AresCharacterIdentityProjectionV1Schema,
    voice_spec: AresVoiceSpecProjectionV1Schema,
    current_character: boundedNonBlankString(500),
    conflict: boundedNonBlankString(500),
    adjacent_beat_summaries: z
      .array(boundedNonBlankString(300))
      .max(2),
    memories: z
      .array(AresProvenanceMemoryV1Schema)
      .max(3),
    generation_input_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.voice_spec.subject_id !== value.character_lock.persona_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          'voice_spec.subject_id must match character_lock.persona_id',
        path: ['voice_spec', 'subject_id'],
      });
    }
    let expectedDigest: string | null = null;
    try {
      expectedDigest = deriveAresScriptGenerationInputDigestV1(value);
    } catch {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'generation input must contain valid Unicode scalar values',
        path: ['generation_input_digest'],
      });
      return;
    }
    if (value.generation_input_digest !== expectedDigest) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'generation_input_digest does not match generation input',
        path: ['generation_input_digest'],
      });
    }
  })
  .transform(deepFreeze);

export type AresCharacterIdentityProjectionV1 = z.infer<
  typeof AresCharacterIdentityProjectionV1Schema
>;
export type AresProvenanceMemoryV1 = z.infer<
  typeof AresProvenanceMemoryV1Schema
>;
export type AresVoiceSpecProjectionV1 = z.infer<
  typeof AresVoiceSpecProjectionV1Schema
>;
export type AresScriptGenerationInputV1 = z.infer<
  typeof AresScriptGenerationInputV1Schema
>;
