/**
 * TypeScript/Zod mirror of Python strategy_approval_v2.py.
 *
 * Python is authoritative. These schemas validate immutable DB evidence; they
 * do not replace the database's active/revoked approval decision.
 */
import { z } from 'zod';

import { canonicalContractDigestV1 } from './ares-script-revision-v1.js';

const DigestSchema = z.string().regex(
  /^sha256:[0-9a-f]{64}$/,
  'digest must be sha256:<64 lowercase hex>',
);
const UuidSchema = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  'identifier must use canonical lowercase UUID form',
);
const CanonicalNonEmptyString = z.string().refine(
  (value) => value.length > 0 && value === value.trim(),
  'string must be non-empty and contain no surrounding whitespace',
);
const InputRevision = z.number().int().min(0).max(2_147_483_647);
const Revision = z.number().int().min(1).max(2_147_483_647);
const UTC_TIMESTAMP_RE =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;

function isValidUtcTimestamp(value: string): boolean {
  const match = UTC_TIMESTAMP_RE.exec(value);
  if (!match) return false;
  const [year, month, day, hour, minute, second] = match
    .slice(1, 7)
    .map((part) => Number.parseInt(part, 10));
  if (year < 1) return false;
  const candidate = new Date(0);
  candidate.setUTCHours(0, 0, 0, 0);
  candidate.setUTCFullYear(year, month - 1, day);
  candidate.setUTCHours(hour, minute, second, 0);
  return candidate.getUTCFullYear() === year
    && candidate.getUTCMonth() === month - 1
    && candidate.getUTCDate() === day
    && candidate.getUTCHours() === hour
    && candidate.getUTCMinutes() === minute
    && candidate.getUTCSeconds() === second;
}

const UtcTimestampSchema = z
  .string()
  .regex(UTC_TIMESTAMP_RE)
  .refine(isValidUtcTimestamp, 'invalid UTC timestamp');

type JsonValue =
  | null
  | string
  | number
  | boolean
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };
type JsonObject = { readonly [key: string]: JsonValue };
type MutableJsonObject = { [key: string]: JsonValue };

function isPlainObject(value: object): value is Record<string, unknown> {
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function assertValidUnicode(value: string, path: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xD800 && unit <= 0xDBFF) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xDC00 && next <= 0xDFFF)) {
        throw new TypeError(`${path} contains an unpaired Unicode surrogate`);
      }
      index += 1;
    } else if (unit >= 0xDC00 && unit <= 0xDFFF) {
      throw new TypeError(`${path} contains an unpaired Unicode surrogate`);
    }
  }
}

function cloneJsonValue(
  value: unknown,
  path: string,
  active = new WeakSet<object>(),
): JsonValue {
  if (value === null || typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    assertValidUnicode(value, path);
    return value;
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TypeError(`${path} contains a non-safe integer`);
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (active.has(value)) throw new TypeError(`${path} contains a cyclic non-JSON value`);
    active.add(value);
    try {
      if (Object.getOwnPropertySymbols(value).length > 0) {
        throw new TypeError(`${path} contains a symbol key`);
      }
      const ownNames = Object.getOwnPropertyNames(value);
      if (ownNames.length !== value.length + 1 || !ownNames.includes('length')) {
        throw new TypeError(`${path} contains a sparse array hole`);
      }
      const clone: JsonValue[] = [];
      for (const name of ownNames) {
        if (name === 'length') continue;
        const index = Number(name);
        if (
          !Number.isSafeInteger(index)
          || index < 0
          || index >= value.length
          || String(index) !== name
        ) {
          throw new TypeError(`${path} contains a non-JSON array property`);
        }
        const descriptor = Object.getOwnPropertyDescriptor(value, name);
        if (!descriptor?.enumerable || !('value' in descriptor)) {
          throw new TypeError(`${path}[${index}] is not an enumerable JSON data property`);
        }
        clone[index] = cloneJsonValue(descriptor.value, `${path}[${index}]`, active);
      }
      return clone;
    } finally {
      active.delete(value);
    }
  }
  if (typeof value === 'object' && isPlainObject(value)) {
    if (active.has(value)) throw new TypeError(`${path} contains a cyclic non-JSON value`);
    active.add(value);
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const clone = Object.create(null) as MutableJsonObject;
    try {
      for (const key of Object.getOwnPropertyNames(value)) {
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        if (!descriptor?.enumerable || !('value' in descriptor)) {
          throw new TypeError(`${path}.${key} is not an enumerable JSON data property`);
        }
        assertValidUnicode(key, `${path}.key`);
        Object.defineProperty(clone, key, {
          configurable: true,
          enumerable: true,
          value: cloneJsonValue(descriptor.value, `${path}.${key}`, active),
          writable: true,
        });
      }
      return clone;
    } finally {
      active.delete(value);
    }
  }
  throw new TypeError(`${path} contains a non-JSON value`);
}

function cloneJsonObject(value: unknown, path: string): JsonObject {
  const clone = cloneJsonValue(value, path);
  if (clone === null || Array.isArray(clone) || typeof clone !== 'object') {
    throw new TypeError(`${path} must be a JSON object`);
  }
  return clone as JsonObject;
}

function strictRoot<T extends z.ZodTypeAny>(path: string, schema: T) {
  return z.preprocess((value, ctx) => {
    try {
      if (typeof value !== 'object' || value === null || !isPlainObject(value)) {
        throw new TypeError(`${path} must be a plain JSON object`);
      }
      if (Object.getOwnPropertySymbols(value).length > 0) {
        throw new TypeError(`${path} contains a symbol key`);
      }
      for (const key of Object.getOwnPropertyNames(value)) {
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        if (!descriptor?.enumerable || !('value' in descriptor)) {
          throw new TypeError(
            `${path}.${key} is not an enumerable JSON data property`,
          );
        }
      }
      return value;
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error instanceof Error ? error.message : `invalid ${path}`,
      });
      return z.NEVER;
    }
  }, schema);
}

function deepFreeze<T>(value: T): T {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const nested of Object.values(value as Record<string, unknown>)) {
      deepFreeze(nested);
    }
    Object.freeze(value);
  }
  return value;
}

function jsonObjectSchema(path: string, requireNonEmpty: boolean) {
  return z.unknown().transform((value, ctx): JsonObject => {
    try {
      const clone = cloneJsonObject(value, path);
      if (requireNonEmpty && Object.keys(clone).length === 0) {
        throw new TypeError(`${path} must be a non-empty JSON object`);
      }
      return clone;
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error instanceof Error ? error.message : `invalid ${path}`,
      });
      return z.NEVER;
    }
  });
}

function digestMatches(
  value: Record<string, unknown>,
  field: string,
): boolean {
  try {
    return value[field] === canonicalContractDigestV1(value, [field]);
  } catch {
    return false;
  }
}

export const StrategyApprovalBundleV1Schema = strictRoot(
  'StrategyApprovalBundle.v1',
  z.object({
    contract_version: z.literal('StrategyApprovalBundle.v1'),
    run_id: UuidSchema,
    workspace_id: UuidSchema,
    strategy: jsonObjectSchema('strategy', true),
    brief_patch: jsonObjectSchema('brief_patch', false),
    attributes_patch: jsonObjectSchema('attributes_patch', false),
  }).strict(),
)
  .transform(deepFreeze)
  .readonly();
export type StrategyApprovalBundleV1 = z.infer<
  typeof StrategyApprovalBundleV1Schema
>;

export function strategyApprovalBundleDigestV1(
  bundle: StrategyApprovalBundleV1,
): string {
  return canonicalContractDigestV1(bundle);
}

export function strategyApprovalStrategyDigestV1(
  bundle: StrategyApprovalBundleV1,
): string {
  return canonicalContractDigestV1(bundle.strategy);
}

export const StrategyApprovalReceiptV2Schema = strictRoot(
  'StrategyApprovalReceipt.v2',
  z.object({
    contract_version: z.literal('StrategyApprovalReceipt.v2'),
    approval_id: UuidSchema,
    claim_id: UuidSchema,
    run_id: UuidSchema,
    workspace_id: UuidSchema,
    strategy_input_revision: InputRevision,
    approval_revision: Revision,
    source_digest: DigestSchema,
    strategy_digest: DigestSchema,
    bundle_digest: DigestSchema,
    approved_by_account_id: UuidSchema,
    approved_at: UtcTimestampSchema,
    receipt_digest: DigestSchema,
  }).strict(),
)
  .superRefine((value, ctx) => {
    if (!digestMatches(value, 'receipt_digest')) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'receipt_digest does not match StrategyApprovalReceipt payload',
      });
    }
  })
  .transform(deepFreeze)
  .readonly();
export type StrategyApprovalReceiptV2 = z.infer<
  typeof StrategyApprovalReceiptV2Schema
>;

export const ParzifalIdentityBindingV1Schema = strictRoot(
  'ParzifalIdentityBinding.v1',
  z.object({
    contract_version: z.literal('ParzifalIdentityBinding.v1'),
    binding_id: UuidSchema,
    binding_revision: Revision,
    workspace_id: UuidSchema,
    run_id: UuidSchema,
    strategy_approval_id: UuidSchema,
    strategy_digest: DigestSchema,
    strategy_bundle_digest: DigestSchema,
    strategy_receipt_digest: DigestSchema,
    target_profile: jsonObjectSchema('target_profile', true),
    target_profile_digest: DigestSchema,
    master_sheet: jsonObjectSchema('master_sheet', true),
    master_sheet_digest: DigestSchema,
    cast_sheets: jsonObjectSchema('cast_sheets', true),
    cast_sheets_digest: DigestSchema,
    identity_source: z.literal('parzifal'),
    source_node: CanonicalNonEmptyString,
    source_revision: CanonicalNonEmptyString,
    created_at: UtcTimestampSchema,
    created_by_account_id: CanonicalNonEmptyString,
    binding_digest: DigestSchema,
  }).strict(),
)
  .superRefine((value, ctx) => {
    const expected = {
      target_profile_digest: canonicalContractDigestV1(value.target_profile),
      master_sheet_digest: canonicalContractDigestV1(value.master_sheet),
      cast_sheets_digest: canonicalContractDigestV1(value.cast_sheets),
    };
    for (const [field, digest] of Object.entries(expected)) {
      if (value[field as keyof typeof value] !== digest) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field} does not match its immutable snapshot`,
        });
      }
    }
    if (!digestMatches(value, 'binding_digest')) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'binding_digest does not match ParzifalIdentityBinding payload',
      });
    }
  })
  .transform(deepFreeze)
  .readonly();
export type ParzifalIdentityBindingV1 = z.infer<
  typeof ParzifalIdentityBindingV1Schema
>;

export function deriveParzifalIdentityBindingIdV1(receiptDigest: string): string {
  if (!DigestSchema.safeParse(receiptDigest).success) {
    throw new TypeError('receipt_digest must be a lowercase sha256 digest');
  }
  const hex = receiptDigest.slice(7, 39).split('');
  hex[12] = '5';
  hex[16] = ['8', '9', 'a', 'b'][Number.parseInt(hex[16], 16) % 4];
  return `${hex.slice(0, 8).join('')}-${hex.slice(8, 12).join('')}-${hex.slice(12, 16).join('')}-${hex.slice(16, 20).join('')}-${hex.slice(20, 32).join('')}`;
}

export function validateStrategyApprovalEvidenceV2(
  bundle: unknown,
  receipt: unknown,
): {
  bundle: StrategyApprovalBundleV1;
  receipt: StrategyApprovalReceiptV2;
} {
  const parsedBundle = StrategyApprovalBundleV1Schema.parse(bundle);
  const parsedReceipt = StrategyApprovalReceiptV2Schema.parse(receipt);
  if (parsedReceipt.run_id !== parsedBundle.run_id) {
    throw new TypeError('strategy approval run_id scope mismatch');
  }
  if (parsedReceipt.workspace_id !== parsedBundle.workspace_id) {
    throw new TypeError('strategy approval workspace_id scope mismatch');
  }
  if (parsedReceipt.strategy_digest !== strategyApprovalStrategyDigestV1(parsedBundle)) {
    throw new TypeError('strategy approval strategy_digest mismatch');
  }
  if (parsedReceipt.bundle_digest !== strategyApprovalBundleDigestV1(parsedBundle)) {
    throw new TypeError('strategy approval bundle_digest mismatch');
  }
  return { bundle: parsedBundle, receipt: parsedReceipt };
}

export function validateParzifalIdentityBindingV1(
  binding: unknown,
  evidence: { bundle: unknown; receipt: unknown },
): ParzifalIdentityBindingV1 {
  const { bundle, receipt } = validateStrategyApprovalEvidenceV2(
    evidence.bundle,
    evidence.receipt,
  );
  const parsed = ParzifalIdentityBindingV1Schema.parse(binding);
  const expected = {
    binding_id: deriveParzifalIdentityBindingIdV1(receipt.receipt_digest),
    binding_revision: receipt.approval_revision,
    workspace_id: bundle.workspace_id,
    run_id: bundle.run_id,
    strategy_approval_id: receipt.approval_id,
    strategy_digest: receipt.strategy_digest,
    strategy_bundle_digest: receipt.bundle_digest,
    strategy_receipt_digest: receipt.receipt_digest,
    source_node: 'parzifal.identity.bind',
    source_revision: 'parzifal.identity.bind.v1',
    created_at: receipt.approved_at,
    created_by_account_id: receipt.approved_by_account_id,
  };
  for (const [field, value] of Object.entries(expected)) {
    if (parsed[field as keyof typeof parsed] !== value) {
      throw new TypeError(`Parzifal identity ${field} binding mismatch`);
    }
  }
  if (bundle.attributes_patch.identity_source !== 'parzifal') {
    throw new TypeError('Parzifal identity bundle identity_source must be parzifal');
  }
  const approvedSnapshots = {
    target_profile: bundle.attributes_patch.target_profile,
    master_sheet: bundle.attributes_patch.parzifal_master_sheet,
    cast_sheets: bundle.attributes_patch.parzifal_cast_sheets,
  };
  for (const [field, approved] of Object.entries(approvedSnapshots)) {
    if (
      approved === null
      || Array.isArray(approved)
      || typeof approved !== 'object'
      || Object.keys(approved).length === 0
    ) {
      throw new TypeError(`Parzifal identity bundle ${field} snapshot is missing`);
    }
    if (
      canonicalContractDigestV1(approved as Record<string, unknown>)
      !== canonicalContractDigestV1(
        parsed[field as keyof typeof parsed] as Record<string, unknown>,
      )
    ) {
      throw new TypeError(
        `Parzifal identity ${field} does not match approved bundle`,
      );
    }
  }
  return parsed;
}
