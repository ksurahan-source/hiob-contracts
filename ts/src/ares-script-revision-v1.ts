/**
 * TypeScript/Zod mirror of Python ares_script_revision_v1.py.
 *
 * Python is authoritative. Approval receipts are evidence, not bearer
 * credentials: callers must use approvalReceiptAuthorizesV1 with a durable
 * resolver that confirms the active factory/state revision and revocation.
 */
import { createHash } from 'node:crypto';
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

const NonEmptyString = z.string().trim().min(1);
const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
const DigestSchema = z.string().refine(
  (value) => value.length === 71 && /^sha256:[0-9a-f]{64}$/.test(value),
  'digest must be sha256:<64 lowercase hex>',
);
const UuidString = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  'identifier must use canonical lowercase UUID form',
);
const NonNegativeSafeInteger = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const DbRevisionInteger = z.number().int().nonnegative().max(2_147_483_647);
const ExpectedStateRevisionInteger = z.number().int().min(1).max(2_147_483_646);
const ApprovedStateRevisionInteger = z.number().int().min(2).max(2_147_483_647);
const UTC_TIMESTAMP_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;

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
  | JsonValue[]
  | { [key: string]: JsonValue };

function isPlainJsonObject(value: object): value is Record<string, unknown> {
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function cloneJsonValue(value: unknown, path = 'json'): JsonValue {
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
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const expectedNames = new Set([
      ...Array.from({ length: value.length }, (_, index) => String(index)),
      'length',
    ]);
    if (Object.getOwnPropertyNames(value).some((name) => !expectedNames.has(name))) {
      throw new TypeError(`${path} contains a non-JSON array property`);
    }
    const clone: JsonValue[] = [];
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor) {
        throw new TypeError(`${path} contains a sparse array hole`);
      }
      if (!descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}[${index}] is not an enumerable JSON data property`);
      }
      clone.push(cloneJsonValue(descriptor.value, `${path}[${index}]`));
    }
    return clone;
  }
  if (typeof value === 'object' && isPlainJsonObject(value)) {
    const symbols = Object.getOwnPropertySymbols(value);
    if (symbols.length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const clone = Object.create(null) as Record<string, JsonValue>;
    for (const key of Object.getOwnPropertyNames(value)) {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor?.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}.${key} is not an enumerable JSON data property`);
      }
      assertValidUnicode(key, `${path}.key`);
      Object.defineProperty(clone, key, {
        configurable: true,
        enumerable: true,
        value: cloneJsonValue(descriptor.value, `${path}.${key}`),
        writable: true,
      });
    }
    return clone;
  }
  throw new TypeError(`${path} contains a non-JSON value`);
}

const JsonValueSchema = z
  .unknown()
  .transform((value, ctx): JsonValue => {
    try {
      return cloneJsonValue(value);
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error instanceof Error ? error.message : 'invalid JSON value',
      });
      return z.NEVER;
    }
  });

const MasterSalesScriptSchema = JsonValueSchema.refine(
  (value): value is Record<string, JsonValue> => (
    value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).length > 0
  ),
  'master_sales_script must be a non-empty JSON object',
);
const ProductionPlanSchema = JsonValueSchema.refine(
  (value): value is Record<string, JsonValue> => (
    value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).length > 0
  ),
  'production_plan must be a non-empty JSON object',
);
const PronunciationOverridesSchema = z
  .unknown()
  .transform((value, ctx) => {
    if (typeof value !== 'object' || value === null || !isPlainJsonObject(value)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'pronunciation_overrides must be a JSON object',
      });
      return z.NEVER;
    }
    if (Object.getOwnPropertySymbols(value).length > 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'pronunciation override keys must be strings',
      });
      return z.NEVER;
    }
    const normalized = Object.create(null) as Record<string, string>;
    for (const rawKey of Object.getOwnPropertyNames(value)) {
      const descriptor = Object.getOwnPropertyDescriptor(value, rawKey);
      const parsedPronunciation = NonEmptyString.safeParse(descriptor?.value);
      if (!descriptor?.enumerable || !('value' in descriptor) || !parsedPronunciation.success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'pronunciation override values must be non-empty strings',
        });
        return z.NEVER;
      }
      const key = rawKey.trim();
      if (key.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'pronunciation override keys must be non-empty',
        });
        return z.NEVER;
      }
      if (Object.prototype.hasOwnProperty.call(normalized, key)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'pronunciation override keys must be unique after trimming',
        });
        return z.NEVER;
      }
      Object.defineProperty(normalized, key, {
        configurable: true,
        enumerable: true,
        value: parsedPronunciation.data,
        writable: true,
      });
    }
    return normalized;
  });

function utcMicros(value: string): bigint {
  const match = UTC_TIMESTAMP_RE.exec(value);
  if (!match || !isValidUtcTimestamp(value)) {
    throw new TypeError('invalid UTC timestamp');
  }
  const wholeSecond = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}Z`;
  const wholeMs = Date.parse(wholeSecond);
  const micros = BigInt((match[7] ?? '').padEnd(6, '0') || '0');
  return BigInt(wholeMs) * 1000n + micros;
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

function compareCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(left, (char) => char.codePointAt(0) as number);
  const rightPoints = Array.from(right, (char) => char.codePointAt(0) as number);
  const count = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < count; index += 1) {
    if (leftPoints[index] !== rightPoints[index]) {
      return leftPoints[index] - rightPoints[index];
    }
  }
  return leftPoints.length - rightPoints.length;
}

export function canonicalContractJsonV1(value: unknown, path = 'contract'): string {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') {
    assertValidUnicode(value, path);
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TypeError(
        `${path} contains a non-safe integer; digest-bearing numbers must be safe integers`,
      );
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const expectedNames = new Set([
      ...Array.from({ length: value.length }, (_, index) => String(index)),
      'length',
    ]);
    if (Object.getOwnPropertyNames(value).some((name) => !expectedNames.has(name))) {
      throw new TypeError(`${path} contains a non-JSON array property`);
    }
    const items: string[] = [];
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor) {
        throw new TypeError(`${path} contains a sparse array hole`);
      }
      if (!descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}[${index}] is not an enumerable JSON data property`);
      }
      items.push(canonicalContractJsonV1(descriptor.value, `${path}[${index}]`));
    }
    return `[${items.join(',')}]`;
  }
  if (typeof value === 'object' && isPlainJsonObject(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const record = value as Record<string, unknown>;
    const keys = Object.getOwnPropertyNames(record).sort(compareCodePoints);
    return `{${keys.map((key) => {
      const descriptor = Object.getOwnPropertyDescriptor(record, key);
      if (!descriptor?.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}.${key} is not an enumerable JSON data property`);
      }
      assertValidUnicode(key, `${path}.key`);
      return `${JSON.stringify(key)}:${canonicalContractJsonV1(descriptor.value, `${path}.${key}`)}`;
    }).join(',')}}`;
  }
  throw new TypeError(`${path} contains non-JSON value`);
}

export function canonicalContractDigestV1(
  value: Record<string, unknown>,
  exclude: readonly string[] = [],
): string {
  if (!isPlainJsonObject(value)) {
    throw new TypeError('contract contains non-JSON value');
  }
  if (Object.getOwnPropertySymbols(value).length > 0) {
    throw new TypeError('contract contains a symbol key');
  }
  const excluded = new Set(exclude);
  const payload = Object.create(null) as Record<string, unknown>;
  for (const key of Object.getOwnPropertyNames(value)) {
    if (excluded.has(key)) continue;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor?.enumerable || !('value' in descriptor)) {
      throw new TypeError(`contract.${key} is not an enumerable JSON data property`);
    }
    Object.defineProperty(payload, key, {
      configurable: true,
      enumerable: true,
      value: descriptor.value,
      writable: true,
    });
  }
  const canonical = canonicalContractJsonV1(payload);
  return `sha256:${createHash('sha256').update(canonical, 'utf8').digest('hex')}`;
}

function digestMatchesV1(
  value: Record<string, unknown>,
  field: string,
): boolean {
  try {
    return value[field] === canonicalContractDigestV1(value, [field]);
  } catch {
    return false;
  }
}

export const AresScriptSegmentV1Schema = z
  .object({
    beat_index: NonNegativeSafeInteger,
    text: z.string(),
  })
  .strict()
  .transform(deepFreeze);
export type AresScriptSegmentV1 = z.infer<typeof AresScriptSegmentV1Schema>;

export const AresSceneDirectionV1Schema = z
  .object({
    shot: z.string().trim().max(300),
    subject: z.string().trim().max(500),
    setting: z.string().trim().max(300),
    overlay: z.string().trim().max(200),
  })
  .strict()
  .transform(deepFreeze);
export type AresSceneDirectionV1 = z.infer<typeof AresSceneDirectionV1Schema>;

export const AresBeatV1Schema = z
  .object({
    beat_index: NonNegativeSafeInteger,
    text: NonBlankString,
    caption: z.string(),
    scene_direction: AresSceneDirectionV1Schema,
  })
  .strict()
  .transform(deepFreeze);
export type AresBeatV1 = z.infer<typeof AresBeatV1Schema>;

export const ScriptPackageV1Schema = z
  .object({
    contract_version: z.literal('AresScriptPackage.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    candidate_id: UuidString,
    factory_revision: DbRevisionInteger,
    master_sales_script: MasterSalesScriptSchema,
    voice_script: z.array(AresScriptSegmentV1Schema),
    caption_script: z.array(AresScriptSegmentV1Schema),
    pronunciation_overrides: PronunciationOverridesSchema,
    package_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string) => ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message,
    });
    const count = value.voice_script.length;
    if (count === 0) issue('voice_script must contain at least one segment');
    if (value.caption_script.length !== count) {
      issue('voice_script and caption_script must have equal length');
    }
    const expected = Array.from({ length: count }, (_, index) => index);
    const voiceIndices = value.voice_script.map((segment) => segment.beat_index);
    const captionIndices = value.caption_script.map((segment) => segment.beat_index);
    if (voiceIndices.some((index, position) => index !== expected[position])) {
      issue('voice_script beat indices must be exactly 0..N-1');
    }
    if (captionIndices.some((index, position) => index !== expected[position])) {
      issue('caption_script beat indices must be exactly 0..N-1');
    }
    if (value.voice_script.some((segment) => segment.text.trim().length === 0)) {
      issue('voice_script segments must contain non-empty dialogue');
    }
    if (!digestMatchesV1(value, 'package_digest')) {
      issue('package_digest mismatch');
    }
  })
  .transform(deepFreeze);
export type ScriptPackageV1 = z.infer<typeof ScriptPackageV1Schema>;

export const BeatPlanV1Schema = z
  .object({
    contract_version: z.literal('AresBeatPlan.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    script_revision_id: UuidString,
    factory_revision: DbRevisionInteger,
    script_package_digest: DigestSchema,
    beats: z.array(AresBeatV1Schema).min(1),
    production_plan: ProductionPlanSchema,
    plan_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.beats.some((beat, position) => beat.beat_index !== position)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'beat indices must be exactly 0..N-1',
      });
    }
    if (!digestMatchesV1(value, 'plan_digest')) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'plan_digest mismatch' });
    }
  })
  .transform(deepFreeze);
export type BeatPlanV1 = z.infer<typeof BeatPlanV1Schema>;

export const AresScriptRevisionV1Schema = z
  .object({
    contract_version: z.literal('AresScriptRevision.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    candidate_id: UuidString,
    factory_revision: DbRevisionInteger,
    script_package: ScriptPackageV1Schema,
    revision_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string) => ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message,
    });
    if (value.script_package.workspace_id !== value.workspace_id) issue('workspace_id mismatch');
    if (value.script_package.run_id !== value.run_id) issue('run_id mismatch');
    if (value.script_package.revision_id !== value.revision_id) issue('revision_id mismatch');
    if (value.script_package.candidate_id !== value.candidate_id) issue('candidate_id mismatch');
    if (value.script_package.factory_revision !== value.factory_revision) {
      issue('factory_revision mismatch');
    }
    if (!digestMatchesV1(value, 'revision_digest')) {
      issue('revision_digest mismatch');
    }
  })
  .transform(deepFreeze);
export type AresScriptRevisionV1 = z.infer<typeof AresScriptRevisionV1Schema>;

export const AresBeatPlanRevisionV1Schema = z
  .object({
    contract_version: z.literal('AresBeatPlanRevision.v1'),
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    script_revision_id: UuidString,
    factory_revision: DbRevisionInteger,
    approved_script_package_digest: DigestSchema,
    beat_plan: BeatPlanV1Schema,
    revision_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string) => ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message,
    });
    if (value.beat_plan.workspace_id !== value.workspace_id) issue('workspace_id mismatch');
    if (value.beat_plan.run_id !== value.run_id) issue('run_id mismatch');
    if (value.beat_plan.revision_id !== value.revision_id) issue('revision_id mismatch');
    if (value.beat_plan.script_revision_id !== value.script_revision_id) {
      issue('script_revision_id mismatch');
    }
    if (value.beat_plan.factory_revision !== value.factory_revision) {
      issue('factory_revision mismatch');
    }
    if (value.beat_plan.script_package_digest !== value.approved_script_package_digest) {
      issue('approved_script_package_digest mismatch');
    }
    if (!digestMatchesV1(value, 'revision_digest')) {
      issue('revision_digest mismatch');
    }
  })
  .transform(deepFreeze);
export type AresBeatPlanRevisionV1 = z.infer<typeof AresBeatPlanRevisionV1Schema>;

export function planRevisionBindsScriptRevisionV1(
  plan: AresBeatPlanRevisionV1,
  script: AresScriptRevisionV1,
): boolean {
  return plan.workspace_id === script.workspace_id
    && plan.run_id === script.run_id
    && plan.script_revision_id === script.revision_id
    && plan.factory_revision === script.factory_revision
    && plan.approved_script_package_digest === script.script_package.package_digest
    && plan.beat_plan.beats.length === script.script_package.voice_script.length
    && plan.beat_plan.beats.every((beat, index) => (
      beat.text === script.script_package.voice_script[index].text
      && beat.caption === script.script_package.caption_script[index].text
    ));
}

export function deriveAresG1SubjectDigestV1(
  targetProfileDigest: string,
  identityLockDigest: string,
  scriptPackageDigest: string,
  beatPlanDigest: string,
): string {
  const values = {
    target_profile_digest: targetProfileDigest,
    identity_lock_digest: identityLockDigest,
    script_package_digest: scriptPackageDigest,
    beat_plan_digest: beatPlanDigest,
  };
  for (const [field, value] of Object.entries(values)) {
    if (!DigestSchema.safeParse(value).success) {
      throw new Error(`${field} must be sha256:<64 lowercase hex>`);
    }
  }
  return sha256Digest(values);
}

export const AresApprovalCommandV1Schema = z
  .object({
    contract_version: z.literal('AresApprovalCommand.v1'),
    command_id: NonEmptyString,
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    approval_kind: z.enum(['script', 'production_plan']),
    artifact_digest: DigestSchema,
    target_profile_digest: DigestSchema,
    identity_lock_digest: DigestSchema,
    script_package_digest: DigestSchema,
    beat_plan_digest: DigestSchema.nullable(),
    g1_subject_digest: DigestSchema.nullable(),
    approver_account_id: NonEmptyString,
    policy_version: NonEmptyString,
    factory_revision: DbRevisionInteger,
    expected_state_revision: ExpectedStateRevisionInteger,
    issued_at_utc: UtcTimestampSchema,
    command_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.approval_kind === 'script') {
      if (
        value.artifact_digest !== value.script_package_digest
        || value.beat_plan_digest !== null
        || value.g1_subject_digest !== null
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'script approval must bind only the ScriptPackage artifact',
        });
      }
    } else if (value.beat_plan_digest === null || value.g1_subject_digest === null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'production approval requires BeatPlan and G1 subject digests',
      });
    } else {
      let expectedG1: string | null = null;
      try {
        expectedG1 = deriveAresG1SubjectDigestV1(
          value.target_profile_digest,
          value.identity_lock_digest,
          value.script_package_digest,
          value.beat_plan_digest,
        );
      } catch {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'production approval contains an invalid G1 constituent digest',
        });
      }
      if (expectedG1 !== null && (
        value.g1_subject_digest !== expectedG1
        || value.artifact_digest !== expectedG1
      )) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'production approval artifact must equal the four-digest G1 subject',
        });
      }
    }
    if (!digestMatchesV1(value, 'command_digest')) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'command_digest mismatch' });
    }
  })
  .transform(deepFreeze);
export type AresApprovalCommandV1 = z.infer<typeof AresApprovalCommandV1Schema>;

export const AresApprovalBeginCommandV1Schema = z
  .object({
    contract_version: z.literal('AresApprovalBeginCommand.v1'),
    command_id: NonEmptyString,
    workspace_id: UuidString,
    run_id: UuidString,
    candidate_id: UuidString,
    requester_account_id: NonEmptyString,
    policy_version: NonEmptyString,
    factory_revision: DbRevisionInteger,
    expected_state_revision: z.literal(0),
    issued_at_utc: UtcTimestampSchema,
    command_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (!digestMatchesV1(value, 'command_digest')) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'command_digest mismatch',
      });
    }
  })
  .transform(deepFreeze);
export type AresApprovalBeginCommandV1 = z.infer<
  typeof AresApprovalBeginCommandV1Schema
>;

type ApprovalRevisionV1 = AresScriptRevisionV1 | AresBeatPlanRevisionV1;

export function approvalCommandBindsRevisionV1(
  command: AresApprovalCommandV1,
  revision: ApprovalRevisionV1,
  approvedScriptRevision?: AresScriptRevisionV1,
): boolean {
  const expected = command.approval_kind === 'script'
    ? revision.contract_version === 'AresScriptRevision.v1'
      ? revision.script_package.package_digest
      : null
    : revision.contract_version === 'AresBeatPlanRevision.v1'
      ? command.g1_subject_digest
      : null;
  const constituentsMatch = command.approval_kind === 'script'
    ? revision.contract_version === 'AresScriptRevision.v1'
      && command.script_package_digest === revision.script_package.package_digest
      && command.beat_plan_digest === null
      && command.g1_subject_digest === null
    : revision.contract_version === 'AresBeatPlanRevision.v1'
      && command.script_package_digest === revision.approved_script_package_digest
      && approvedScriptRevision !== undefined
      && planRevisionBindsScriptRevisionV1(revision, approvedScriptRevision)
      && command.beat_plan_digest === revision.beat_plan.plan_digest
      && command.g1_subject_digest !== null
      && command.g1_subject_digest === deriveAresG1SubjectDigestV1(
        command.target_profile_digest,
        command.identity_lock_digest,
        command.script_package_digest,
        command.beat_plan_digest,
      );
  return expected !== null
    && constituentsMatch
    && command.workspace_id === revision.workspace_id
    && command.run_id === revision.run_id
    && command.revision_id === revision.revision_id
    && command.artifact_digest === expected
    && command.factory_revision === revision.factory_revision;
}

export const AresApprovalReceiptV1Schema = z
  .object({
    contract_version: z.literal('AresApprovalReceipt.v1'),
    receipt_id: NonEmptyString,
    command_id: NonEmptyString,
    command_digest: DigestSchema,
    workspace_id: UuidString,
    run_id: UuidString,
    revision_id: UuidString,
    approval_kind: z.enum(['script', 'production_plan']),
    artifact_digest: DigestSchema,
    target_profile_digest: DigestSchema,
    identity_lock_digest: DigestSchema,
    script_package_digest: DigestSchema,
    beat_plan_digest: DigestSchema.nullable(),
    g1_subject_digest: DigestSchema.nullable(),
    approver_account_id: NonEmptyString,
    decision: z.literal('approved'),
    policy_version: NonEmptyString,
    factory_revision: DbRevisionInteger,
    state_revision: ApprovedStateRevisionInteger,
    approved_at_utc: UtcTimestampSchema,
    expires_at_utc: UtcTimestampSchema,
    revoked_at_utc: UtcTimestampSchema.nullable(),
    transaction_audit_id: NonEmptyString,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string) => ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message,
    });
    if (value.transaction_audit_id !== value.receipt_id) {
      issue('transaction_audit_id must equal receipt_id');
    }
    if (value.approval_kind === 'script') {
      if (
        value.artifact_digest !== value.script_package_digest
        || value.beat_plan_digest !== null
        || value.g1_subject_digest !== null
      ) {
        issue('script receipt must bind only the ScriptPackage artifact');
      }
    } else if (value.beat_plan_digest === null || value.g1_subject_digest === null) {
      issue('production receipt requires BeatPlan and G1 subject digests');
    } else {
      let expectedG1: string | null = null;
      try {
        expectedG1 = deriveAresG1SubjectDigestV1(
          value.target_profile_digest,
          value.identity_lock_digest,
          value.script_package_digest,
          value.beat_plan_digest,
        );
      } catch {
        issue('production receipt contains an invalid G1 constituent digest');
      }
      if (expectedG1 !== null && (
        value.g1_subject_digest !== expectedG1
        || value.artifact_digest !== expectedG1
      )) {
        issue('production receipt artifact must equal the four-digest G1 subject');
      }
    }
    try {
      const approved = utcMicros(value.approved_at_utc);
      const expires = utcMicros(value.expires_at_utc);
      if (expires <= approved) issue('expires_at_utc must follow approved_at_utc');
      if (value.revoked_at_utc !== null) {
        const revoked = utcMicros(value.revoked_at_utc);
        if (revoked < approved) issue('revoked_at_utc cannot precede approved_at_utc');
        if (revoked > expires) issue('revoked_at_utc cannot follow expires_at_utc');
      }
    } catch {
      issue('receipt timestamps must be valid UTC values');
    }
    if (!digestMatchesV1(value, 'receipt_digest')) {
      issue('receipt_digest mismatch');
    }
  })
  .transform(deepFreeze);
export type AresApprovalReceiptV1 = z.infer<typeof AresApprovalReceiptV1Schema>;

export interface AresApprovalResolverV1 {
  isCurrentApproval(identity: {
    receipt_id: string;
    command_id: string;
    workspace_id: string;
    factory_revision: number;
    state_revision: number;
    policy_version: string;
    receipt_digest: string;
    command_digest: string;
    run_id: string;
    revision_id: string;
    approval_kind: 'script' | 'production_plan';
    artifact_digest: string;
    approver_account_id: string;
    target_profile_digest: string;
    identity_lock_digest: string;
    script_package_digest: string;
    beat_plan_digest: string | null;
    g1_subject_digest: string | null;
  }): boolean;
}

export function approvalReceiptStructurallyBindsV1(
  receipt: AresApprovalReceiptV1,
  command: AresApprovalCommandV1,
  revision: ApprovalRevisionV1,
  approvedScriptRevision?: AresScriptRevisionV1,
): boolean {
  return approvalCommandBindsRevisionV1(command, revision, approvedScriptRevision)
    && receipt.command_id === command.command_id
    && receipt.command_digest === command.command_digest
    && receipt.workspace_id === command.workspace_id
    && receipt.run_id === command.run_id
    && receipt.revision_id === command.revision_id
    && receipt.approval_kind === command.approval_kind
    && receipt.artifact_digest === command.artifact_digest
    && receipt.target_profile_digest === command.target_profile_digest
    && receipt.identity_lock_digest === command.identity_lock_digest
    && receipt.script_package_digest === command.script_package_digest
    && receipt.beat_plan_digest === command.beat_plan_digest
    && receipt.g1_subject_digest === command.g1_subject_digest
    && receipt.approver_account_id === command.approver_account_id
    && receipt.policy_version === command.policy_version
    && receipt.factory_revision === command.factory_revision
    && receipt.state_revision === command.expected_state_revision + 1;
}

export function approvalReceiptAuthorizesV1(
  receipt: AresApprovalReceiptV1,
  command: AresApprovalCommandV1,
  revision: ApprovalRevisionV1,
  atUtc: string,
  resolver: AresApprovalResolverV1,
  approvedScriptRevision?: AresScriptRevisionV1,
): boolean {
  if (!approvalReceiptStructurallyBindsV1(
    receipt,
    command,
    revision,
    approvedScriptRevision,
  )) return false;
  const approved = utcMicros(receipt.approved_at_utc);
  if (approved < utcMicros(command.issued_at_utc)) return false;
  const at = utcMicros(UtcTimestampSchema.parse(atUtc));
  if (at < approved || at >= utcMicros(receipt.expires_at_utc)) return false;
  if (receipt.revoked_at_utc !== null) return false;
  return resolver.isCurrentApproval({
    receipt_id: receipt.receipt_id,
    command_id: receipt.command_id,
    workspace_id: receipt.workspace_id,
    factory_revision: receipt.factory_revision,
    state_revision: receipt.state_revision,
    policy_version: receipt.policy_version,
    receipt_digest: receipt.receipt_digest,
    command_digest: receipt.command_digest,
    run_id: receipt.run_id,
    revision_id: receipt.revision_id,
    approval_kind: receipt.approval_kind,
    artifact_digest: receipt.artifact_digest,
    approver_account_id: receipt.approver_account_id,
    target_profile_digest: receipt.target_profile_digest,
    identity_lock_digest: receipt.identity_lock_digest,
    script_package_digest: receipt.script_package_digest,
    beat_plan_digest: receipt.beat_plan_digest,
    g1_subject_digest: receipt.g1_subject_digest,
  });
}
