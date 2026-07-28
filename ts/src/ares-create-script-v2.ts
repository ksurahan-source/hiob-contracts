/**
 * TypeScript/Zod mirror of Python ares_create_script_v2.py.
 *
 * Python is authoritative. This mirror enforces the public generate envelope
 * shape: sealed authority + facts in → ScriptPackageV2 + BeatPlanV2 out.
 * No job/approval/visual-seal/dispatch fields are accepted (strict objects).
 */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';
import {characterIdentityBindingErrorV1} from './character-identity-v1.js';
import {VoiceSpecV1Schema} from './voice-spec-v1.js';

const NonEmptyString = z.string().trim().min(1);
const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const NonNegativeInt = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);

const ClaimProvenanceSchema = z
  .object({
    source_url: z.string().default(''),
    quote_span: z.string().default(''),
    observed_at: z.string().default(''),
  })
  .strict();

const ContractRefSchema = z
  .object({
    name: NonEmptyString,
    version: NonEmptyString,
    schema_digest: DigestSchema,
  })
  .strict();

const MapperRefSchema = z
  .object({
    planet: z.literal('karma'),
    node_id: NonEmptyString,
    revision: NonEmptyString,
    policy_digest: DigestSchema,
  })
  .strict();

export const KarmaEdgeReceiptLooseSchema = z
  .object({
    receipt_id: NonEmptyString,
    edge_id: NonEmptyString,
    run_id: NonEmptyString,
    factory_revision: NonNegativeInt,
    workspace_id: NonEmptyString,
    source_output_digests: z.array(DigestSchema).min(1),
    target_contract: ContractRefSchema,
    decision: z.enum(['accepted', 'blocked', 'needs_human']),
    target_input: z.record(z.string(), z.unknown()).nullable().optional(),
    target_input_digest: DigestSchema.nullable().optional(),
    transform_log: z.array(z.unknown()).optional(),
    violations: z.array(z.unknown()).optional(),
    waiver_receipt_refs: z.array(z.string()).optional(),
    mapper: MapperRefSchema,
    created_at: NonEmptyString,
  })
  .strict();

export const AresAuthorityV2Schema = z
  .object({
    accepted_p2a_receipt: KarmaEdgeReceiptLooseSchema,
    identity_lock_digest: DigestSchema,
    product_truth_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
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
    if (receipt.target_contract.name !== 'AresScriptInput') {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "target_contract.name must be 'AresScriptInput'",
        path: ['accepted_p2a_receipt', 'target_contract', 'name'],
      });
    }
    if (!receipt.source_output_digests.includes(value.identity_lock_digest)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'identity_lock_digest must appear in source_output_digests',
        path: ['identity_lock_digest'],
      });
    }
  });

export const AresSpeakerSlotV2Schema = z
  .object({
    role: NonEmptyString,
    subject_id: NonEmptyString,
    display_name: NonEmptyString,
    voice_id: NonEmptyString.nullable().optional(),
    face_id: NonEmptyString.nullable().optional(),
    identity_binding_digest: DigestSchema.nullable().optional(),
    voice_spec: VoiceSpecV1Schema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (
      !value.face_id
      && !value.voice_id
      && !value.identity_binding_digest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          'Ares speaker requires sealed face_id + voice_id + identity_binding_digest',
        path: ['identity_binding_digest'],
      });
      return;
    }
    const bindingError = characterIdentityBindingErrorV1(value);
    if (bindingError) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: bindingError,
        path: ['identity_binding_digest'],
      });
    }
    if (value.voice_spec.subject_id !== value.subject_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'voice_spec.subject_id must match speaker subject_id',
        path: ['voice_spec', 'subject_id'],
      });
    }
  });

export const AresIdentitySealedV2Schema = z
  .object({
    identity_lock_digest: DigestSchema,
    cast_sheet_digest: DigestSchema,
    speakers: z.array(AresSpeakerSlotV2Schema).min(1),
    locale: NonEmptyString.default('ko'),
    audience_lock: NonEmptyString.nullable().optional(),
  })
  .strict();

export const AresProductFactsSealedV2Schema = z
  .object({
    product_truth_digest: DigestSchema,
    brand_slug: NonEmptyString,
    brand_display_name: NonEmptyString,
    product_name: NonEmptyString,
    listing_slug: NonEmptyString.nullable().optional(),
    listing_pitch: NonEmptyString.nullable().optional(),
    price_text: NonEmptyString.nullable().optional(),
    refund_policy_text: NonEmptyString.nullable().optional(),
    usp_lines: z.array(NonEmptyString).default([]),
    regulation_notes: NonEmptyString.nullable().optional(),
    facts_block: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const AresClaimRefV2Schema = z
  .object({
    claim_id: NonEmptyString,
    text: NonEmptyString,
    claim_kind: NonEmptyString.default('product_fact'),
    provenance: ClaimProvenanceSchema.nullable().optional(),
    evidence_ref: NonEmptyString.nullable().optional(),
  })
  .strict();

export const AresEvidenceAndClaimsSealedV2Schema = z
  .object({
    evidence_bundle_digest: DigestSchema,
    claims: z.array(AresClaimRefV2Schema).min(1),
    voc_quotes: z.array(NonEmptyString).default([]),
    allowed_claim_ids: z.array(NonEmptyString).default([]),
  })
  .strict();

export const AresHookDirectiveV2Schema = z
  .object({
    directive_digest: DigestSchema,
    archetype_id: NonEmptyString,
    hook_line: NonEmptyString.nullable().optional(),
    hook_register: NonEmptyString.nullable().optional(),
    experiment_id: NonEmptyString.nullable().optional(),
    rationale: NonEmptyString.nullable().optional(),
  })
  .strict();

export const AresCreativeConstraintsV2Schema = z
  .object({
    n_beats: z.number().int().min(1).max(64),
    format_mode: NonEmptyString.nullable().optional(),
    style_mode: NonEmptyString.nullable().optional(),
    vertical_mode: NonEmptyString.nullable().optional(),
    goal: NonEmptyString.nullable().optional(),
    fixed_hook: NonEmptyString.nullable().optional(),
    human_instruction: z.string().default(''),
    prior_script_package_digest: DigestSchema.nullable().optional(),
    banned_phrases: z.array(NonEmptyString).default([]),
    required_phrases: z.array(NonEmptyString).default([]),
  })
  .strict();

export const AresCreateScriptRequestV2Schema = z
  .object({
    contract_version: z.literal('AresCreateScriptRequest.v2'),
    authority: AresAuthorityV2Schema,
    identity: AresIdentitySealedV2Schema,
    product_facts: AresProductFactsSealedV2Schema,
    evidence_and_claims: AresEvidenceAndClaimsSealedV2Schema,
    hook_directive: AresHookDirectiveV2Schema,
    creative_constraints: AresCreativeConstraintsV2Schema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.identity.identity_lock_digest !== value.authority.identity_lock_digest) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'identity.identity_lock_digest must equal authority.identity_lock_digest',
        path: ['identity', 'identity_lock_digest'],
      });
    }
    if (
      value.product_facts.product_truth_digest !== value.authority.product_truth_digest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          'product_facts.product_truth_digest must equal authority.product_truth_digest',
        path: ['product_facts', 'product_truth_digest'],
      });
    }
  });

const ScriptSegmentSchema = z
  .object({
    beat_index: NonNegativeInt,
    text: z.string(),
  })
  .strict();

export const ScriptPackageV2Schema = z
  .object({
    contract_version: z.literal('AresScriptPackage.v2'),
    master_sales_script: z.record(z.string(), z.unknown()),
    voice_script: z.array(ScriptSegmentSchema).min(1),
    caption_script: z.array(ScriptSegmentSchema).min(1),
    pronunciation_overrides: z.record(NonEmptyString, NonEmptyString).default({}),
    package_digest: DigestSchema,
  })
  .strict();

const SceneDirectionSchema = z
  .object({
    shot: z.string(),
    subject: z.string(),
    setting: z.string(),
    overlay: z.string(),
  })
  .strict();

const BeatSchema = z
  .object({
    beat_index: NonNegativeInt,
    text: NonEmptyString,
    caption: z.string(),
    scene_direction: SceneDirectionSchema,
  })
  .strict();

export const AresBeatRoleIntentV2Schema = z
  .object({
    beat_index: NonNegativeInt,
    roles: z.array(NonEmptyString).min(1),
    on_camera: z.boolean().default(true),
    notes: z.string().default(''),
  })
  .strict();

export const BeatPlanV2Schema = z
  .object({
    contract_version: z.literal('AresBeatPlan.v2'),
    script_package_digest: DigestSchema,
    beats: z.array(BeatSchema).min(1),
    beat_role_intents: z.array(AresBeatRoleIntentV2Schema).default([]),
    plan_digest: DigestSchema,
  })
  .strict();

export const AresQualityFindingV2Schema = z
  .object({
    code: NonEmptyString,
    severity: z.enum(['info', 'warn', 'error']),
    message: NonEmptyString,
    beat_index: NonNegativeInt.nullable().optional(),
    gate: NonEmptyString.nullable().optional(),
  })
  .strict();

export const AresGenerateProvenanceV2Schema = z
  .object({
    producer: z.literal('ares').default('ares'),
    contract_version: z
      .literal('AresCreateScriptResult.v2')
      .default('AresCreateScriptResult.v2'),
    request_content_digest: DigestSchema,
    model_id: NonEmptyString.nullable().optional(),
    prompt_digest: DigestSchema.nullable().optional(),
    produced_at: z.string().nullable().optional(),
  })
  .strict();

export const AresGenerateUsageV2Schema = z
  .object({
    input_tokens: NonNegativeInt.default(0),
    output_tokens: NonNegativeInt.default(0),
    total_tokens: NonNegativeInt.default(0),
    cost_cents: NonNegativeInt.default(0),
    model_id: NonEmptyString.nullable().optional(),
  })
  .strict();

export const AresCreateScriptResultV2Schema = z
  .object({
    contract_version: z.literal('AresCreateScriptResult.v2'),
    status: z.enum(['ok', 'blocked', 'needs_human']).default('ok'),
    script_package: ScriptPackageV2Schema.nullable().optional(),
    beat_plan: BeatPlanV2Schema.nullable().optional(),
    quality_findings: z.array(AresQualityFindingV2Schema).default([]),
    provenance: AresGenerateProvenanceV2Schema,
    usage: AresGenerateUsageV2Schema.default({}),
    content_digest: DigestSchema,
    block_reason: NonEmptyString.nullable().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.status === 'ok') {
      if (!value.script_package || !value.beat_plan) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'ok result requires script_package and beat_plan',
        });
      } else if (
        value.beat_plan.script_package_digest !== value.script_package.package_digest
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'beat_plan.script_package_digest must match script_package.package_digest',
        });
      }
      if (value.block_reason != null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'ok result must not carry block_reason',
        });
      }
    } else {
      if (value.script_package != null || value.beat_plan != null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${value.status} result must not carry script_package/beat_plan`,
        });
      }
      if (!value.block_reason) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `${value.status} result requires block_reason`,
        });
      }
    }
  });

/** Field-shape digests — keep keys sorted to match Python schema digests. */
export function aresCreateScriptRequestSchemaDigest(): string {
  return sha256Digest({
    contract_version: 'AresCreateScriptRequest.v2',
    fields: [
      'authority',
      'contract_version',
      'creative_constraints',
      'evidence_and_claims',
      'hook_directive',
      'identity',
      'product_facts',
    ].sort(),
    authority_fields: [
      'accepted_p2a_receipt',
      'identity_lock_digest',
      'product_truth_digest',
    ].sort(),
    identity_fields: [
      'audience_lock',
      'cast_sheet_digest',
      'identity_lock_digest',
      'locale',
      'speakers',
    ].sort(),
    speaker_fields: [
      'display_name',
      'face_id',
      'identity_binding_digest',
      'role',
      'subject_id',
      'voice_id',
      'voice_spec',
    ].sort(),
    voice_spec_fields: [
      'approved_examples',
      'contract_version',
      'forbidden_phrases',
      'rhythm',
      'subject_id',
      'vocabulary',
      'voice_spec_digest',
    ].sort(),
    product_fields: [
      'brand_display_name',
      'brand_slug',
      'facts_block',
      'listing_pitch',
      'listing_slug',
      'price_text',
      'product_name',
      'product_truth_digest',
      'refund_policy_text',
      'regulation_notes',
      'usp_lines',
    ].sort(),
    evidence_fields: [
      'allowed_claim_ids',
      'claims',
      'evidence_bundle_digest',
      'voc_quotes',
    ].sort(),
    hook_fields: [
      'archetype_id',
      'directive_digest',
      'experiment_id',
      'hook_line',
      'hook_register',
      'rationale',
    ].sort(),
    constraints_fields: [
      'banned_phrases',
      'fixed_hook',
      'format_mode',
      'goal',
      'human_instruction',
      'n_beats',
      'prior_script_package_digest',
      'required_phrases',
      'style_mode',
      'vertical_mode',
    ].sort(),
  });
}

export function aresCreateScriptResultSchemaDigest(): string {
  return sha256Digest({
    contract_version: 'AresCreateScriptResult.v2',
    fields: [
      'beat_plan',
      'block_reason',
      'content_digest',
      'contract_version',
      'provenance',
      'quality_findings',
      'script_package',
      'status',
      'usage',
    ].sort(),
    package_fields: [
      'caption_script',
      'contract_version',
      'master_sales_script',
      'package_digest',
      'pronunciation_overrides',
      'voice_script',
    ].sort(),
    plan_fields: [
      'beat_role_intents',
      'beats',
      'contract_version',
      'plan_digest',
      'script_package_digest',
    ].sort(),
  });
}

export type AresCreateScriptRequestV2 = z.infer<typeof AresCreateScriptRequestV2Schema>;
export type AresCreateScriptResultV2 = z.infer<typeof AresCreateScriptResultV2Schema>;
export type ScriptPackageV2 = z.infer<typeof ScriptPackageV2Schema>;
export type BeatPlanV2 = z.infer<typeof BeatPlanV2Schema>;
