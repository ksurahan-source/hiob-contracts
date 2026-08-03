import { z } from 'zod';

import { AresIdentitySealedV2Schema } from './ares-create-script-v2.js';
import { sha256Digest } from './factory/digest.js';

function normalizeUnicodeScalars(value: string): string {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const low = value.charCodeAt(index + 1);
      if (!(low >= 0xdc00 && low <= 0xdfff)) {
        throw new Error('text must contain valid Unicode scalar values');
      }
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new Error('text must contain valid Unicode scalar values');
    }
  }
  return value;
}

function isPythonStripWhitespace(code: number): boolean {
  // Mirrors Python str.strip()/str.isspace(), deliberately preserving U+FEFF.
  return (
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

function pythonStrip(value: string): string {
  let start = 0;
  let end = value.length;
  while (start < end && isPythonStripWhitespace(value.charCodeAt(start))) {
    start += 1;
  }
  while (end > start && isPythonStripWhitespace(value.charCodeAt(end - 1))) {
    end -= 1;
  }
  return value.slice(start, end);
}

function canonicalText(value: string): string {
  const normalized = pythonStrip(normalizeUnicodeScalars(value));
  if (!normalized) throw new Error('string must not be blank');
  return normalized;
}

function canonicalUtcOffsetTimestamp(value: string): string {
  const normalized = canonicalText(value);
  const source = normalized.endsWith('Z')
    ? `${normalized.slice(0, -1)}+00:00`
    : normalized;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d{1,6})?\+00:00$/.exec(source);
  if (!match) throw new Error('timestamp must be an ISO-8601 UTC value');
  if (Number(match[1]) === 0) {
    throw new Error('timestamp must be a valid calendar value');
  }
  const parsed = new Date(`${source.slice(0, -6)}Z`);
  if (Number.isNaN(parsed.valueOf())
    || parsed.getUTCFullYear() !== Number(match[1])
    || parsed.getUTCMonth() + 1 !== Number(match[2])
    || parsed.getUTCDate() !== Number(match[3])
    || parsed.getUTCHours() !== Number(match[4])
    || parsed.getUTCMinutes() !== Number(match[5])
    || parsed.getUTCSeconds() !== Number(match[6])) {
    throw new Error('timestamp must be a valid calendar value');
  }
  const fractionalDigits = match[7]?.slice(1) ?? '';
  // Python omits zero microseconds and writes every non-zero value at six digits.
  const canonicalFraction = /[1-9]/.test(fractionalDigits)
    ? `.${fractionalDigits.padEnd(6, '0')}`
    : '';
  return `${source.slice(0, 19)}${canonicalFraction}+00:00`;
}

function deepFreeze<T>(value: T): T {
  if (Array.isArray(value)) {
    return Object.freeze(value.map(deepFreeze)) as T;
  }
  if (value !== null && typeof value === 'object') {
    return Object.freeze(Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(
        ([key, item]) => [key, deepFreeze(item)],
      ),
    )) as T;
  }
  return value;
}

function enumerableDataProperty(value: object, key: string, path: string): unknown {
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  if (!descriptor?.enumerable) {
    throw new Error(`${path} contains a non-enumerable own string property`);
  }
  if (!Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
    throw new Error(`${path} contains an accessor property`);
  }
  return descriptor.value;
}

function assertJson(value: unknown, path = 'value'): void {
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'string') {
    normalizeUnicodeScalars(value);
    return;
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) {
      throw new Error(`${path} contains a non-safe-integer number`);
    }
    return;
  }
  if (
    value !== null
    && typeof value === 'object'
    && Object.getOwnPropertySymbols(value).length > 0
  ) {
    throw new Error(`${path} contains a symbol-keyed property`);
  }
  if (Array.isArray(value)) {
    for (const key of Object.getOwnPropertyNames(value)) {
      if (key === 'length') continue;
      enumerableDataProperty(value, key, `${path}.${key}`);
      const index = Number(key);
      if (!Number.isInteger(index) || index < 0 || index >= value.length || String(index) !== key) {
        throw new Error(`${path} contains a non-index array property`);
      }
    }
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.prototype.hasOwnProperty.call(value, index)) {
        throw new Error(`${path} contains a sparse array`);
      }
      assertJson(
        enumerableDataProperty(value, String(index), `${path}[${index}]`),
        `${path}[${index}]`,
      );
    }
    return;
  }
  if (value !== null && typeof value === 'object') {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new Error(`${path} contains a non-JSON object`);
    }
    for (const key of Object.getOwnPropertyNames(value)) {
      assertJson(
        enumerableDataProperty(value, key, `${path}.${key}`),
        `${path}.${key}`,
      );
    }
    return;
  }
  throw new Error(`${path} contains non-JSON value`);
}

const CanonicalTextSchema = z.string()
  .superRefine((value, ctx) => {
    try {
      canonicalText(value);
    } catch (error) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: String(error) });
    }
  })
  .transform(canonicalText);
const CanonicalUtcOffsetTimestampSchema = z.string()
  .superRefine((value, ctx) => {
    try {
      canonicalUtcOffsetTimestamp(value);
    } catch (error) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: String(error) });
    }
  })
  .transform(canonicalUtcOffsetTimestamp);
const DigestSchema = z.string().regex(/^sha256:[0-9a-f]{64}$/);
const PositiveVersionSchema = z.number().int().safe().positive();
const StrictJsonValueSchema = z.unknown()
  .superRefine((value, ctx) => {
    try {
      assertJson(value);
    } catch (error) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: String(error) });
    }
  });
const JsonObjectSchema = StrictJsonValueSchema
  .pipe(z.record(z.string(), z.unknown()))
  .transform(deepFreeze);

const RecordBodyShape = {
  id: CanonicalTextSchema,
  version: PositiveVersionSchema,
  workspace_id: CanonicalTextSchema,
  run_id: CanonicalTextSchema,
  status: z.enum(['approved', 'sealed']),
  emitted_at: CanonicalUtcOffsetTimestampSchema,
  identity_lock: JsonObjectSchema,
  master_sheet: JsonObjectSchema,
  cast_sheets: JsonObjectSchema,
};
const ParzifalIdentityAuthorityRecordBodyV1Schema = StrictJsonValueSchema.pipe(
  z.object(RecordBodyShape).strict(),
);

export const ParzifalIdentityRecordRefV1Schema = StrictJsonValueSchema
  .pipe(z.object({
    id: CanonicalTextSchema,
    version: PositiveVersionSchema,
    digest: DigestSchema,
  }).strict())
  .transform(deepFreeze);

export type ParzifalIdentityRecordRefV1 = z.infer<
  typeof ParzifalIdentityRecordRefV1Schema
>;

export function deriveParzifalIdentityAuthorityRecordDigestV1(
  value: Record<string, unknown>,
): string {
  assertJson(value);
  const body = ParzifalIdentityAuthorityRecordBodyV1Schema.parse({
    id: value.id,
    version: value.version,
    workspace_id: value.workspace_id,
    run_id: value.run_id,
    status: value.status,
    emitted_at: value.emitted_at,
    identity_lock: value.identity_lock,
    master_sheet: value.master_sheet,
    cast_sheets: value.cast_sheets,
  });
  return sha256Digest({
    contract_version: 'ParzifalIdentityAuthorityRecord.v1',
    ...body,
  });
}

export const ParzifalIdentityAuthorityRecordV1Schema = StrictJsonValueSchema
  .pipe(z.object({
    ...RecordBodyShape,
    digest: DigestSchema,
  }).strict())
  .superRefine((value, ctx) => {
    try {
      if (value.digest !== deriveParzifalIdentityAuthorityRecordDigestV1(value)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'digest does not match Parzifal identity authority record',
          path: ['digest'],
        });
      }
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: String(error),
        path: ['digest'],
      });
    }
  })
  .transform(deepFreeze);

export type ParzifalIdentityAuthorityRecordV1 = z.infer<
  typeof ParzifalIdentityAuthorityRecordV1Schema
>;

const ParzifalIdentitySealedPayloadV1Schema = StrictJsonValueSchema
  .pipe(AresIdentitySealedV2Schema)
  .superRefine((value, ctx) => {
    value.speakers.forEach((speaker, index) => {
      if (!speaker.face_id || !speaker.voice_id || !speaker.identity_binding_digest) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'sealed_payload speakers must include face_id, voice_id, and identity_binding_digest',
          path: ['speakers', index],
        });
      }
    });
  })
  .transform((value) => deepFreeze({
    ...value,
    voice_spec: value.voice_spec ?? null,
    locale: value.locale ?? 'ko',
    audience_lock: value.audience_lock ?? null,
  }));

export function deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(
  value: Record<string, unknown>,
): string {
  return sha256Digest(ParzifalIdentitySealedPayloadV1Schema.parse(value));
}

const ParzifalIdentityAuthorityMaterialBodyV1Schema = z
  .object({
    artifact_type: z.literal('identity_lock'),
    artifact_digest: DigestSchema,
    payload_digest: DigestSchema,
    receipt_id: CanonicalTextSchema,
    sealed_payload: ParzifalIdentitySealedPayloadV1Schema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.artifact_digest !== value.sealed_payload.identity_lock_digest) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'artifact_digest must equal sealed identity_lock_digest',
        path: ['artifact_digest'],
      });
    }
    try {
      if (
        value.payload_digest
        !== deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(value.sealed_payload)
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'payload_digest does not match sealed_payload',
          path: ['payload_digest'],
        });
      }
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: String(error),
        path: ['payload_digest'],
      });
    }
  });

export const ParzifalIdentityAuthorityMaterialV1Schema = StrictJsonValueSchema
  .pipe(ParzifalIdentityAuthorityMaterialBodyV1Schema)
  .transform(deepFreeze);

export type ParzifalIdentityAuthorityMaterialV1 = z.infer<
  typeof ParzifalIdentityAuthorityMaterialV1Schema
>;
