/**
 * TypeScript/Zod mirror of Python ares_create_script_v3.py.
 *
 * V3 binds explicit producer authority and request scope to sealed inputs.
 * Output is script content plus semantic scene intent; Athena-owned shot,
 * camera, and render fields are structurally absent and rejected.
 */
import { z } from 'zod';
import {
  aresIdentitySchemaDescriptorV2,
  aresSharedRequestSchemaDescriptorV2,
  aresSharedResultSchemaDescriptorV2,
} from './ares-create-script-v2.js';
import { characterIdentityBindingErrorV1 } from './character-identity-v1.js';
import { VoiceSpecV1Schema } from './voice-spec-v1.js';
export {
  AresV3MakeContextV1Schema,
  deriveAresV3MakeContextDigestV1,
} from './ares-v3-make-context-v1.js';
export type {
  AresV3MakeContextV1,
} from './ares-v3-make-context-v1.js';

import { sha256Digest } from './factory/digest.js';
import { KarmaEdgeReceiptSchema } from './factory/karma-edge.js';
import { compareLocaleStrings } from './string-order.js';

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
const NonNegativeInt = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const UTC_TIMESTAMP_RE =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;
const AthenaOwnedOutputKeys = new Set([
  'shot',
  'shottype',
  'shotplan',
  'camera',
  'cameraangle',
  'cameramode',
  'render',
  'rendermode',
  'productionplan',
  'visualplan',
  'visualprompt',
  'personacast',
  'cast',
  'scenedirection',
  'visualcontext',
]);

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

function cloneCanonicalJson(value: unknown, path = 'json'): JsonValue {
  if (value === null || typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    for (const char of value) {
      const codePoint = char.charCodeAt(0);
      if (codePoint >= 0xd800 && codePoint <= 0xdfff && char.length === 1) {
        throw new TypeError(`${path} contains an unpaired Unicode surrogate`);
      }
    }
    return value;
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new TypeError(
        `${path} contains a non-safe integer; digest-bearing numbers must be safe integers`,
      );
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
    const result: JsonValue[] = [];
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor) {
        throw new TypeError(`${path} contains a sparse array hole`);
      }
      if (!descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}[${index}] is not an enumerable JSON data property`);
      }
      result.push(cloneCanonicalJson(descriptor.value, `${path}[${index}]`));
    }
    return result;
  }
  if (typeof value === 'object' && isPlainJsonObject(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) {
      throw new TypeError(`${path} contains a symbol key`);
    }
    const result = Object.create(null) as Record<string, JsonValue>;
    for (const key of Object.getOwnPropertyNames(value)) {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor?.enumerable || !('value' in descriptor)) {
        throw new TypeError(`${path}.${key} is not an enumerable JSON data property`);
      }
      Object.defineProperty(result, key, {
        configurable: true,
        enumerable: true,
        value: cloneCanonicalJson(descriptor.value, `${path}.${key}`),
        writable: true,
      });
    }
    return result;
  }
  throw new TypeError(`${path} contains a non-JSON value`);
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const nested of Object.values(value as Record<string, unknown>)) {
      deepFreeze(nested);
    }
    Object.freeze(value);
  }
  return value;
}

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

const CanonicalJsonObjectSchema = z
  .unknown()
  .transform((value, ctx): Record<string, JsonValue> => {
    try {
      const cloned = cloneCanonicalJson(value);
      if (
        cloned === null
        || typeof cloned !== 'object'
        || Array.isArray(cloned)
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'value must be a canonical JSON object',
        });
        return z.NEVER;
      }
      return cloned;
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error instanceof Error ? error.message : 'invalid JSON value',
      });
      return z.NEVER;
    }
  });

function normalizeAthenaOwnedKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function findAthenaOwnedKey(value: unknown, path = 'master_sales_script'): string | null {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const found = findAthenaOwnedKey(value[index], `${path}[${index}]`);
      if (found) return found;
    }
    return null;
  }
  if (value !== null && typeof value === 'object') {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (AthenaOwnedOutputKeys.has(normalizeAthenaOwnedKey(key))) return `${path}.${key}`;
      const found = findAthenaOwnedKey(item, `${path}.${key}`);
      if (found) return found;
    }
  }
  return null;
}

const ClaimProvenanceV3Schema = z
  .object({
    source_url: z.string().default(''),
    quote_span: z.string().default(''),
    observed_at: z.string().default(''),
  })
  .strict();

export const AresSpeakerSlotV3InputSchema = z
  .object({
    role: NonBlankString,
    subject_id: NonBlankString,
    display_name: NonBlankString,
    voice_id: NonBlankString.nullable().default(null),
    face_id: NonBlankString.nullable().default(null),
    identity_binding_digest: DigestSchema.nullable().default(null),
  })
  .strict()
  .superRefine((value, ctx) => {
    const error = characterIdentityBindingErrorV1(value);
    if (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error,
        path: ['identity_binding_digest'],
      });
    }
  });

const AresIdentitySealedV3InputSchema = z
  .object({
    identity_lock_digest: DigestSchema,
    cast_sheet_digest: DigestSchema,
    speakers: z.array(AresSpeakerSlotV3InputSchema).min(1),
    voice_spec: VoiceSpecV1Schema.nullable().default(null),
    locale: NonBlankString.default('ko'),
    audience_lock: NonBlankString.nullable().default(null),
  })
  .strict()
  .superRefine((value, ctx) => {
    const roles = value.speakers.map((speaker) => speaker.role);
    if (new Set(roles).size !== roles.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'speakers roles must be unique',
        path: ['speakers'],
      });
    }
    if (value.voice_spec) {
      if (value.speakers.length !== 1) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'voice_spec requires exactly one sealed speaker',
          path: ['voice_spec'],
        });
      } else if (value.voice_spec.subject_id !== value.speakers[0].subject_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'voice_spec.subject_id must match the sealed speaker',
          path: ['voice_spec', 'subject_id'],
        });
      }
    }
  });

const AresProductFactsSealedV3InputSchema = z
  .object({
    product_truth_digest: DigestSchema,
    brand_slug: NonBlankString,
    brand_display_name: NonBlankString,
    product_name: NonBlankString,
    listing_slug: NonBlankString.nullable().default(null),
    listing_pitch: NonBlankString.nullable().default(null),
    price_text: NonBlankString.nullable().default(null),
    refund_policy_text: NonBlankString.nullable().default(null),
    usp_lines: z.array(NonBlankString).default([]),
    regulation_notes: NonBlankString.nullable().default(null),
    facts_block: CanonicalJsonObjectSchema.default({}),
  })
  .strict();

const AresClaimRefV3InputSchema = z
  .object({
    claim_id: NonBlankString,
    text: NonBlankString,
    claim_kind: NonBlankString.default('product_fact'),
    provenance: ClaimProvenanceV3Schema.nullable().default(null),
    evidence_ref: NonBlankString.nullable().default(null),
  })
  .strict();

const AresEvidenceAndClaimsSealedV3InputSchema = z
  .object({
    evidence_bundle_digest: DigestSchema,
    claims: z.array(AresClaimRefV3InputSchema).min(1),
    voc_quotes: z.array(NonBlankString).default([]),
    allowed_claim_ids: z.array(NonBlankString).default([]),
  })
  .strict()
  .superRefine((value, ctx) => {
    const ids = value.claims.map((claim) => claim.claim_id);
    if (new Set(ids).size !== ids.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'claims claim_id values must be unique',
        path: ['claims'],
      });
    }
    if (value.allowed_claim_ids.length > 0) {
      const allowed = new Set(value.allowed_claim_ids);
      if (value.claims.some((claim) => !allowed.has(claim.claim_id))) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'claims must appear in allowed_claim_ids',
          path: ['claims'],
        });
      }
    }
  });

const AresHookDirectiveV3InputSchema = z
  .object({
    directive_digest: DigestSchema,
    archetype_id: NonBlankString,
    hook_line: NonBlankString.nullable().default(null),
    hook_register: NonBlankString.nullable().default(null),
    experiment_id: NonBlankString.nullable().default(null),
    rationale: NonBlankString.nullable().default(null),
  })
  .strict();

const AresCreativeConstraintsV3InputSchema = z
  .object({
    n_beats: z.number().int().min(1).max(64),
    target_duration_sec: z.number().int().min(1).max(180).nullable().default(null),
    format_mode: NonBlankString.nullable().default(null),
    style_mode: NonBlankString.nullable().default(null),
    vertical_mode: NonBlankString.nullable().default(null),
    goal: NonBlankString.nullable().default(null),
    fixed_hook: NonBlankString.nullable().default(null),
    human_instruction: z.string().default(''),
    prior_script_package_digest: DigestSchema.nullable().default(null),
    banned_phrases: z.array(NonBlankString).default([]),
    required_phrases: z.array(NonBlankString).default([]),
  })
  .strict();

const MasterSalesScriptV3Schema = CanonicalJsonObjectSchema.refine(
  (value) => Object.keys(value).length > 0,
  'master_sales_script must not be empty',
);

export function authorityRefReceiptDigestV3(args: {
  receipt_id: string;
  producer: string;
  artifact_type: string;
  artifact_digest: string;
  source_output_digest: string;
  payload_digest: string;
  workspace_id: string;
  run_id: string;
}): string {
  return sha256Digest({
    contract_version: 'AresAuthorityArtifactRefReceipt.v3',
    receipt_id: args.receipt_id,
    producer: args.producer,
    artifact_type: args.artifact_type,
    artifact_digest: args.artifact_digest,
    source_output_digest: args.source_output_digest,
    payload_digest: args.payload_digest,
    workspace_id: args.workspace_id,
    run_id: args.run_id,
  });
}

export const AresRequestScopeV3Schema = z
  .object({
    workspace_id: NonBlankString,
    run_id: NonBlankString,
    operation_id: NonBlankString,
    idempotency_key: NonBlankString,
  })
  .strict()
  .transform(deepFreeze);

export const AresAuthorityArtifactRefV3Schema = z
  .object({
    producer: z.enum(['parzifal', 'janus', 'artemis', 'metis', 'karma']),
    artifact_type: z.enum([
      'identity_lock',
      'product_truth',
      'evidence_bundle',
      'hook_directive',
      'p2a_receipt',
    ]),
    artifact_digest: DigestSchema,
    source_output_digest: DigestSchema,
    payload_digest: DigestSchema,
    receipt_id: NonBlankString,
    receipt_digest: DigestSchema,
    workspace_id: NonBlankString,
    run_id: NonBlankString,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.artifact_type === 'p2a_receipt') return;
    if (value.receipt_digest !== authorityRefReceiptDigestV3(value)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'receipt_digest must bind the canonical authority reference',
        path: ['receipt_digest'],
      });
    }
  })
  .transform(deepFreeze);

export const AresP2ATargetProjectionV3Schema = z
  .object({
    contract_version: z.literal('AresP2ATargetProjection.v3'),
    scope: AresRequestScopeV3Schema,
    command_source_output_digest: DigestSchema,
    identity_ref: AresAuthorityArtifactRefV3Schema,
    product_ref: AresAuthorityArtifactRefV3Schema,
    evidence_ref: AresAuthorityArtifactRefV3Schema,
    hook_ref: AresAuthorityArtifactRefV3Schema,
    creative_constraints: AresCreativeConstraintsV3InputSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const expected = {
      identity_ref: ['parzifal', 'identity_lock'],
      product_ref: ['janus', 'product_truth'],
      evidence_ref: ['artemis', 'evidence_bundle'],
      hook_ref: ['metis', 'hook_directive'],
    } as const;
    for (const [field, [producer, artifactType]] of Object.entries(expected)) {
      const ref = value[field as keyof typeof expected];
      if (ref.producer !== producer || ref.artifact_type !== artifactType) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field} must be issued by ${producer} as ${artifactType}`,
          path: [field],
        });
      }
      if (
        ref.workspace_id !== value.scope.workspace_id
        || ref.run_id !== value.scope.run_id
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field} must match the projection scope`,
          path: [field],
        });
      }
    }
  })
  .transform(deepFreeze);

export function aresP2ATargetProjectionV3SchemaDescriptor(): Record<string, unknown> {
  const nonblank = {
    type: 'string',
    minLength: 1,
    invariant: 'trim_nonblank',
  };
  const digest = {
    type: 'string',
    pattern: '^sha256:[0-9a-f]{64}$',
  };
  const refShape = {
    type: 'object',
    additionalProperties: false,
    required: [
      'producer',
      'artifact_type',
      'artifact_digest',
      'source_output_digest',
      'payload_digest',
      'receipt_id',
      'receipt_digest',
      'workspace_id',
      'run_id',
    ],
    properties: {
      producer: { enum: ['parzifal', 'janus', 'artemis', 'metis', 'karma'] },
      artifact_type: {
        enum: [
          'identity_lock',
          'product_truth',
          'evidence_bundle',
          'hook_directive',
          'p2a_receipt',
        ],
      },
      artifact_digest: digest,
      source_output_digest: digest,
      payload_digest: digest,
      receipt_id: nonblank,
      receipt_digest: digest,
      workspace_id: nonblank,
      run_id: nonblank,
    },
    invariants: [
      'receipt_digest=canonical_ref_subject',
      'source_output_digest=producer_planet_output.output_digest',
      'workspace_id/run_id=scope',
    ],
  };
  const constraintsShape = {
    type: 'object',
    additionalProperties: false,
    required: [
      'n_beats',
      'target_duration_sec',
      'format_mode',
      'style_mode',
      'vertical_mode',
      'goal',
      'fixed_hook',
      'human_instruction',
      'prior_script_package_digest',
      'banned_phrases',
      'required_phrases',
    ],
    properties: {
      n_beats: { type: 'integer', minimum: 1, maximum: 64 },
      target_duration_sec: {
        oneOf: [
          { type: 'integer', minimum: 1, maximum: 180 },
          { type: 'null' },
        ],
      },
      format_mode: { oneOf: [nonblank, { type: 'null' }] },
      style_mode: { oneOf: [nonblank, { type: 'null' }] },
      vertical_mode: { oneOf: [nonblank, { type: 'null' }] },
      goal: { oneOf: [nonblank, { type: 'null' }] },
      fixed_hook: { oneOf: [nonblank, { type: 'null' }] },
      human_instruction: { type: 'string' },
      prior_script_package_digest: { oneOf: [digest, { type: 'null' }] },
      banned_phrases: { type: 'array', items: nonblank },
      required_phrases: { type: 'array', items: nonblank },
    },
    invariants: ['all_fields_bound_in_target_input_digest'],
  };
  return {
    $id: 'hiob.AresP2ATargetProjection.v3',
    type: 'object',
    additionalProperties: false,
    required: [
      'contract_version',
      'scope',
      'command_source_output_digest',
      'identity_ref',
      'product_ref',
      'evidence_ref',
      'hook_ref',
      'creative_constraints',
    ],
    properties: {
      contract_version: { const: 'AresP2ATargetProjection.v3' },
      scope: {
        type: 'object',
        additionalProperties: false,
        required: [
          'workspace_id',
          'run_id',
          'operation_id',
          'idempotency_key',
        ],
        properties: {
          workspace_id: nonblank,
          run_id: nonblank,
          operation_id: nonblank,
          idempotency_key: nonblank,
        },
      },
      command_source_output_digest: digest,
      identity_ref: refShape,
      product_ref: refShape,
      evidence_ref: refShape,
      hook_ref: refShape,
      creative_constraints: constraintsShape,
    },
    invariants: [
      'identity_ref=parzifal/identity_lock',
      'product_ref=janus/product_truth',
      'evidence_ref=artemis/evidence_bundle',
      'hook_ref=metis/hook_directive',
      'target_input=canonical_projection',
      'source_output_digests_cover_four_authority_outputs_and_command',
    ],
  };
}

export function aresP2ATargetProjectionV3SchemaDigest(): string {
  return sha256Digest(aresP2ATargetProjectionV3SchemaDescriptor());
}

export const AresAuthorityBundleV3Schema = z
  .object({
    identity_ref: AresAuthorityArtifactRefV3Schema,
    product_ref: AresAuthorityArtifactRefV3Schema,
    evidence_ref: AresAuthorityArtifactRefV3Schema,
    hook_ref: AresAuthorityArtifactRefV3Schema,
    p2a_ref: AresAuthorityArtifactRefV3Schema,
    accepted_p2a_receipt: KarmaEdgeReceiptSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const expected = [
      ['identity_ref', 'parzifal', 'identity_lock'],
      ['product_ref', 'janus', 'product_truth'],
      ['evidence_ref', 'artemis', 'evidence_bundle'],
      ['hook_ref', 'metis', 'hook_directive'],
      ['p2a_ref', 'karma', 'p2a_receipt'],
    ] as const;
    for (const [field, producer, artifactType] of expected) {
      const ref = value[field];
      if (ref.producer !== producer || ref.artifact_type !== artifactType) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field} must be issued by ${producer} as ${artifactType}`,
          path: [field],
        });
      }
    }

    const receipt = value.accepted_p2a_receipt;
    if (receipt.edge_id !== 'p2a') {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "accepted_p2a_receipt.edge_id must be 'p2a'",
        path: ['accepted_p2a_receipt', 'edge_id'],
      });
    }
    if (receipt.decision !== 'accepted') {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "accepted_p2a_receipt.decision must be 'accepted'",
        path: ['accepted_p2a_receipt', 'decision'],
      });
    }
    if (receipt.target_contract.name !== 'AresP2ATargetProjection') {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "accepted_p2a_receipt target contract must be 'AresP2ATargetProjection'",
        path: ['accepted_p2a_receipt', 'target_contract', 'name'],
      });
    }
    if (
      receipt.target_contract.version !== 'v3'
      || receipt.target_contract.schema_digest
        !== aresP2ATargetProjectionV3SchemaDigest()
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'accepted_p2a_receipt target schema must match projection v3',
        path: ['accepted_p2a_receipt', 'target_contract'],
      });
    }
    if (value.p2a_ref.receipt_id !== receipt.receipt_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'p2a_ref.receipt_id must match Karma receipt',
        path: ['p2a_ref', 'receipt_id'],
      });
    }
    if (value.p2a_ref.receipt_digest !== sha256Digest(receipt)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'p2a_ref.receipt_digest must match canonical Karma receipt payload',
        path: ['p2a_ref', 'receipt_digest'],
      });
    }
    if (
      receipt.target_input_digest === null
      || value.p2a_ref.artifact_digest !== receipt.target_input_digest
      || value.p2a_ref.payload_digest !== receipt.target_input_digest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'p2a_ref digests must match Karma target_input_digest',
        path: ['p2a_ref'],
      });
    }
  })
  .transform(deepFreeze);

export const AresCreateScriptRequestV3Schema = z
  .object({
    contract_version: z.literal('AresCreateScriptRequest.v3'),
    scope: AresRequestScopeV3Schema,
    authority: AresAuthorityBundleV3Schema,
    identity: AresIdentitySealedV3InputSchema,
    product_facts: AresProductFactsSealedV3InputSchema,
    evidence_and_claims: AresEvidenceAndClaimsSealedV3InputSchema,
    hook_directive: AresHookDirectiveV3InputSchema,
    creative_constraints: AresCreativeConstraintsV3InputSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const refs = [
      value.authority.identity_ref,
      value.authority.product_ref,
      value.authority.evidence_ref,
      value.authority.hook_ref,
      value.authority.p2a_ref,
    ];
    for (const ref of refs) {
      if (
        ref.workspace_id !== value.scope.workspace_id
        || ref.run_id !== value.scope.run_id
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'authority ref scope must match request scope',
          path: ['authority'],
        });
      }
    }
    const receipt = value.authority.accepted_p2a_receipt;
    if (
      receipt.workspace_id !== value.scope.workspace_id
      || receipt.run_id !== value.scope.run_id
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Karma receipt scope must match request scope',
        path: ['authority', 'accepted_p2a_receipt'],
      });
    }

    const parsedReceiptProjection = AresP2ATargetProjectionV3Schema.safeParse(
      receipt.target_input,
    );
    if (!parsedReceiptProjection.success) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Karma receipt target_input must be AresP2ATargetProjection.v3',
        path: ['authority', 'accepted_p2a_receipt', 'target_input'],
      });
      return;
    }
    const projection = {
      contract_version: 'AresP2ATargetProjection.v3' as const,
      scope: value.scope,
      command_source_output_digest:
        parsedReceiptProjection.data.command_source_output_digest,
      identity_ref: value.authority.identity_ref,
      product_ref: value.authority.product_ref,
      evidence_ref: value.authority.evidence_ref,
      hook_ref: value.authority.hook_ref,
      creative_constraints: value.creative_constraints,
    };
    const projectionDigest = sha256Digest(projection);
    if (
      receipt.target_input === null
      || sha256Digest(receipt.target_input) !== projectionDigest
      || receipt.target_input_digest !== projectionDigest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Karma receipt must bind canonical AresP2ATargetProjection.v3',
        path: ['authority', 'accepted_p2a_receipt', 'target_input'],
      });
    }
    if (
      value.authority.p2a_ref.artifact_digest !== projectionDigest
      || value.authority.p2a_ref.payload_digest !== projectionDigest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'p2a_ref digests must bind canonical projection v3',
        path: ['authority', 'p2a_ref'],
      });
    }
    const sourceDigests = new Set(receipt.source_output_digests);
    const requiredSources = [
      value.authority.identity_ref.source_output_digest,
      value.authority.product_ref.source_output_digest,
      value.authority.evidence_ref.source_output_digest,
      value.authority.hook_ref.source_output_digest,
      projection.command_source_output_digest,
    ];
    if (requiredSources.some((digest) => !sourceDigests.has(digest))) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Karma receipt must cover four authority outputs and the Star command output',
        path: ['authority', 'accepted_p2a_receipt', 'source_output_digests'],
      });
    }

    const bindings = [
      [
        value.authority.identity_ref,
        value.identity,
        value.identity.identity_lock_digest,
        'identity_ref',
      ],
      [
        value.authority.product_ref,
        value.product_facts,
        value.product_facts.product_truth_digest,
        'product_ref',
      ],
      [
        value.authority.evidence_ref,
        value.evidence_and_claims,
        value.evidence_and_claims.evidence_bundle_digest,
        'evidence_ref',
      ],
      [
        value.authority.hook_ref,
        value.hook_directive,
        value.hook_directive.directive_digest,
        'hook_ref',
      ],
    ] as const;
    for (const [ref, payload, artifactDigest, field] of bindings) {
      if (ref.artifact_digest !== artifactDigest) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field}.artifact_digest must match sealed artifact digest`,
          path: ['authority', field, 'artifact_digest'],
        });
      }
      if (ref.payload_digest !== sha256Digest(payload)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${field}.payload_digest must match sealed payload`,
          path: ['authority', field, 'payload_digest'],
        });
      }
    }
  })
  .transform(deepFreeze);

const ScriptSegmentV3Schema = z
  .object({
    beat_index: NonNegativeInt,
    text: z.string(),
  })
  .strict();

export const ScriptPackageV3Schema = z
  .object({
    contract_version: z.literal('AresScriptPackage.v3'),
    master_sales_script: MasterSalesScriptV3Schema,
    voice_script: z.array(ScriptSegmentV3Schema).min(1),
    caption_script: z.array(ScriptSegmentV3Schema).min(1),
    pronunciation_overrides: z.record(NonBlankString, NonBlankString).default({}),
    package_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const athenaOwnedPath = findAthenaOwnedKey(value.master_sales_script);
    if (athenaOwnedPath) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${athenaOwnedPath} is owned by Athena, not Ares`,
        path: ['master_sales_script'],
      });
    }
    const expectedIndices = value.voice_script.map((_, index) => index);
    const voiceIndices = value.voice_script.map((segment) => segment.beat_index);
    const captionIndices = value.caption_script.map((segment) => segment.beat_index);
    if (
      Object.keys(value.master_sales_script).length === 0
      || value.caption_script.length !== value.voice_script.length
      || JSON.stringify(voiceIndices) !== JSON.stringify(expectedIndices)
      || JSON.stringify(captionIndices) !== JSON.stringify(expectedIndices)
      || value.voice_script.some((segment) => !segment.text.trim())
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'script package segments must be non-empty and indexed 0..N-1',
      });
    }
    const masterBeats = value.master_sales_script.beats;
    if (!Array.isArray(masterBeats) || masterBeats.length !== value.voice_script.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'master_sales_script.beats must match script segment count',
        path: ['master_sales_script', 'beats'],
      });
    } else {
      for (let index = 0; index < masterBeats.length; index += 1) {
        const beat = masterBeats[index];
        if (
          beat === null
          || typeof beat !== 'object'
          || Array.isArray(beat)
          || beat.beat_index !== index
          || beat.text !== value.voice_script[index].text
          || beat.caption !== value.caption_script[index].text
        ) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: 'master beat must bind voice/caption segments exactly',
            path: ['master_sales_script', 'beats', index],
          });
        }
      }
    }
    const { package_digest: _digest, ...payload } = value;
    if (value.package_digest !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'package_digest does not match ScriptPackageV3 payload',
        path: ['package_digest'],
      });
    }
  })
  .transform(deepFreeze);

export const AresSemanticBeatV3Schema = z
  .object({
    beat_index: NonNegativeInt,
    text: NonBlankString,
    caption: z.string().default(''),
    scene_intent: NonBlankString,
    role_intents: z.array(NonBlankString).min(1),
  })
  .strict()
  .transform(deepFreeze);

export const SemanticBeatPlanV3Schema = z
  .object({
    contract_version: z.literal('AresSemanticBeatPlan.v3'),
    script_package_digest: DigestSchema,
    beats: z.array(AresSemanticBeatV3Schema).min(1),
    plan_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const indices = value.beats.map((beat) => beat.beat_index);
    const expected = value.beats.map((_, index) => index);
    if (JSON.stringify(indices) !== JSON.stringify(expected)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'semantic beat indices must be exactly 0..N-1',
      });
    }
    const { plan_digest: _digest, ...payload } = value;
    if (value.plan_digest !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'plan_digest does not match SemanticBeatPlanV3 payload',
        path: ['plan_digest'],
      });
    }
  })
  .transform(deepFreeze);

export const AresQualityFindingV3Schema = z
  .object({
    code: NonBlankString,
    severity: z.enum(['info', 'warn', 'error']),
    message: NonBlankString,
    beat_index: NonNegativeInt.nullable().default(null),
    gate: NonBlankString.nullable().default(null),
  })
  .strict()
  .transform(deepFreeze);

export const AresGenerateProvenanceV3Schema = z
  .object({
    producer: z.literal('ares').default('ares'),
    contract_version: z
      .literal('AresCreateScriptResult.v3')
      .default('AresCreateScriptResult.v3'),
    request_content_digest: DigestSchema,
    model_id: NonBlankString.nullable().default(null),
    prompt_digest: DigestSchema.nullable().default(null),
    produced_at: UtcTimestampSchema.nullable().default(null),
  })
  .strict()
  .transform(deepFreeze);

export const AresGenerateUsageV3Schema = z
  .object({
    input_tokens: NonNegativeInt.default(0),
    output_tokens: NonNegativeInt.default(0),
    total_tokens: NonNegativeInt.default(0),
    cost_cents: NonNegativeInt.default(0),
    model_id: NonBlankString.nullable().default(null),
  })
  .strict()
  .transform(deepFreeze);

export const AresCreateScriptResultV3Schema = z
  .object({
    contract_version: z.literal('AresCreateScriptResult.v3'),
    status: z.enum(['ok', 'blocked', 'needs_human']).default('ok'),
    script_package: ScriptPackageV3Schema.nullable().default(null),
    semantic_beat_plan: SemanticBeatPlanV3Schema.nullable().default(null),
    quality_findings: z.array(AresQualityFindingV3Schema).default([]),
    provenance: AresGenerateProvenanceV3Schema,
    usage: AresGenerateUsageV3Schema.default({}),
    content_digest: DigestSchema,
    block_reason: NonBlankString.nullable().default(null),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.status === 'ok') {
      if (!value.script_package || !value.semantic_beat_plan) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'ok result requires script_package and semantic_beat_plan',
        });
      } else if (
        value.semantic_beat_plan.script_package_digest
        !== value.script_package.package_digest
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'semantic plan must bind the script package digest',
        });
      } else if (
        value.semantic_beat_plan.beats.length !== value.script_package.voice_script.length
        || value.semantic_beat_plan.beats.some((beat, index) => (
          beat.text !== value.script_package?.voice_script[index]?.text
          || beat.caption !== value.script_package?.caption_script[index]?.text
        ))
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'semantic beats must bind package voice/caption segments',
          path: ['semantic_beat_plan', 'beats'],
        });
      }
      if (value.block_reason != null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'ok result must not carry block_reason',
        });
      }
    } else {
      if (value.script_package != null || value.semantic_beat_plan != null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${value.status} result must not carry generated artifacts`,
        });
      }
      if (!value.block_reason) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${value.status} result requires block_reason`,
        });
      }
    }
    const { content_digest: _digest, ...payload } = value;
    if (value.content_digest !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'content_digest does not match AresCreateScriptResultV3 payload',
        path: ['content_digest'],
      });
    }
  })
  .transform(deepFreeze);

export function aresCreateScriptRequestV3SchemaDescriptor() {
  return {
    contract_version: 'AresCreateScriptRequest.v3',
    fields: [
      'authority',
      'contract_version',
      'creative_constraints',
      'evidence_and_claims',
      'hook_directive',
      'identity',
      'product_facts',
      'scope',
    ].sort(compareLocaleStrings),
    scope_fields: [
      'idempotency_key',
      'operation_id',
      'run_id',
      'workspace_id',
    ].sort(compareLocaleStrings),
    authority_fields: [
      'accepted_p2a_receipt',
      'evidence_ref',
      'hook_ref',
      'identity_ref',
      'p2a_ref',
      'product_ref',
    ].sort(compareLocaleStrings),
    authority_ref_fields: [
      'artifact_digest',
      'artifact_type',
      'payload_digest',
      'producer',
      'receipt_digest',
      'receipt_id',
      'run_id',
      'source_output_digest',
      'workspace_id',
    ].sort(compareLocaleStrings),
    ...aresSharedRequestSchemaDescriptorV2(),
    ...aresIdentitySchemaDescriptorV2(),
  };
}

export function aresCreateScriptRequestV3SchemaDigest(): string {
  return sha256Digest(aresCreateScriptRequestV3SchemaDescriptor());
}

export function aresCreateScriptResultV3SchemaDigest(): string {
  return sha256Digest({
    contract_version: 'AresCreateScriptResult.v3',
    fields: [
      'block_reason',
      'content_digest',
      'contract_version',
      'provenance',
      'quality_findings',
      'script_package',
      'semantic_beat_plan',
      'status',
      'usage',
    ].sort(compareLocaleStrings),
    ...aresSharedResultSchemaDescriptorV2(),
    semantic_plan_fields: [
      'beats',
      'contract_version',
      'plan_digest',
      'script_package_digest',
    ].sort(compareLocaleStrings),
    semantic_beat_fields: [
      'beat_index',
      'caption',
      'role_intents',
      'scene_intent',
      'text',
    ].sort(compareLocaleStrings),
  });
}

export type AresRequestScopeV3 = z.infer<typeof AresRequestScopeV3Schema>;
export type AresAuthorityArtifactRefV3 = z.infer<
  typeof AresAuthorityArtifactRefV3Schema
>;
export type AresP2ATargetProjectionV3 = z.infer<
  typeof AresP2ATargetProjectionV3Schema
>;
export type AresAuthorityBundleV3 = z.infer<typeof AresAuthorityBundleV3Schema>;
export type AresCreateScriptRequestV3 = z.infer<
  typeof AresCreateScriptRequestV3Schema
>;
export type ScriptPackageV3 = z.infer<typeof ScriptPackageV3Schema>;
export type AresSemanticBeatV3 = z.infer<typeof AresSemanticBeatV3Schema>;
export type SemanticBeatPlanV3 = z.infer<typeof SemanticBeatPlanV3Schema>;
export type AresQualityFindingV3 = z.infer<typeof AresQualityFindingV3Schema>;
export type AresGenerateProvenanceV3 = z.infer<
  typeof AresGenerateProvenanceV3Schema
>;
export type AresGenerateUsageV3 = z.infer<typeof AresGenerateUsageV3Schema>;
export type AresCreateScriptResultV3 = z.infer<
  typeof AresCreateScriptResultV3Schema
>;
