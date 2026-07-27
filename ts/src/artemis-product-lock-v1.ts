/**
 * TypeScript/Zod mirror of Python artemis_product_lock_v1.py.
 *
 * Janus owns immutable observations. Artemis owns grounded claims and may
 * produce a reviewable draft, but a durable approval resolver remains the
 * authority required to seal that draft.
 */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

const TextSchema = z
  .string()
  .transform(value => value.trim())
  .refine(value => value.length > 0, 'string must not be blank');

const OpaqueIdSchema = z
  .string()
  .transform(value => value.trim())
  .refine(
    value => /^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$/.test(value)
      && value.split('/').every(segment => (
        segment !== '' && segment !== '.' && segment !== '..'
      )),
    'technical id must use the opaque id grammar',
  );

const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');

const ObservationKindSchema = z.enum([
  'product_fact',
  'forbidden_claim',
  'social_proof',
]);

const ClaimKindSchema = z.enum(['product_fact', 'social_proof']);

const ArtemisBlockCodeSchema = z.enum([
  'APPROVAL_INVALID',
  'SCOPE_MISMATCH',
  'SOURCE_STALE',
  'DIGEST_MISMATCH',
  'PRODUCT_LOCK_INCOMPLETE',
  'NO_APPROVED_EVIDENCE',
]);

const ProductScopeShape = {
  workspace_id: OpaqueIdSchema,
  run_id: OpaqueIdSchema,
  brand_slug: OpaqueIdSchema,
  listing_slug: OpaqueIdSchema,
  product_id: OpaqueIdSchema,
  product_name: TextSchema,
  product_image_artifact_id: OpaqueIdSchema,
  product_image_storage_key: OpaqueIdSchema,
  product_image_sha256: DigestSchema,
};

export const ObservationProvenanceV1Schema = z
  .object({
    source_record_id: OpaqueIdSchema,
    quote: TextSchema,
  })
  .strict();

const EvidenceItemShape = {
  evidence_artifact_id: OpaqueIdSchema,
  evidence_sha256: DigestSchema,
  provenance: ObservationProvenanceV1Schema,
};

export const JanusProductObservationV1Schema = z
  .object({
    ...EvidenceItemShape,
    observation_id: OpaqueIdSchema,
    kind: ObservationKindSchema,
    text: TextSchema,
  })
  .strict();

const JanusObservationsShape = {
  ...ProductScopeShape,
  contract_version: z.literal('JanusProductObservations.v1'),
  observations: z.array(JanusProductObservationV1Schema).min(1),
};

function observationFingerprint(
  observation: z.infer<typeof JanusProductObservationV1Schema>,
): string {
  return sha256Digest([
    observation.kind,
    observation.text,
    observation.evidence_sha256,
    observation.provenance.source_record_id,
    observation.provenance.quote,
  ]);
}

function addUniqueObservationIssues(
  observations: z.infer<typeof JanusProductObservationV1Schema>[],
  ctx: z.RefinementCtx,
): void {
  const ids = observations.map(observation => observation.observation_id);
  if (new Set(ids).size !== ids.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'observations observation_id values must be unique',
      path: ['observations'],
    });
  }
  const fingerprints = observations.map(observationFingerprint);
  if (new Set(fingerprints).size !== fingerprints.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'duplicate observation content is forbidden',
      path: ['observations'],
    });
  }
}

export const JanusProductObservationsV1Schema = z
  .object({
    ...JanusObservationsShape,
    observations_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    addUniqueObservationIssues(value.observations, ctx);
    const { observations_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'observations_digest does not match payload',
        path: ['observations_digest'],
      });
    }
  });

export const ArtemisCompileRequestV1Schema = z
  .object({
    contract_version: z.literal('ArtemisCompileRequest.v1'),
    observations: JanusProductObservationsV1Schema,
    request_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const { request_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'request_digest does not match payload',
        path: ['request_digest'],
      });
    }
  });

export const ArtemisClaimV1Schema = z
  .object({
    ...EvidenceItemShape,
    claim_id: OpaqueIdSchema,
    text: TextSchema,
    kind: ClaimKindSchema,
    source_observation_ids: z.array(OpaqueIdSchema).length(1),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (
      new Set(value.source_observation_ids).size
      !== value.source_observation_ids.length
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'source_observation_ids must be unique',
        path: ['source_observation_ids'],
      });
    }
  });

const ProductLockDraftContentShape = {
  ...ProductScopeShape,
  contract_version: z.literal('ProductElementLockDraft.v1'),
  claims: z.array(ArtemisClaimV1Schema).min(1),
  forbidden_claims: z.array(TextSchema).default([]),
  source_observations_digest: DigestSchema,
  compile_request_digest: DigestSchema,
};

export type ArtemisClaimV1 = z.infer<typeof ArtemisClaimV1Schema>;

function claimFingerprint(claim: ArtemisClaimV1): string {
  return sha256Digest([
    claim.text,
    claim.kind,
    [...claim.source_observation_ids].sort(),
    claim.evidence_sha256,
    claim.provenance.source_record_id,
    claim.provenance.quote,
  ]);
}

function addUniqueDraftContentIssues(
  value: {
    claims: ArtemisClaimV1[];
    forbidden_claims: string[];
  },
  ctx: z.RefinementCtx,
): void {
  const claimIds = value.claims.map(claim => claim.claim_id);
  if (new Set(claimIds).size !== claimIds.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'claims claim_id values must be unique',
      path: ['claims'],
    });
  }
  const fingerprints = value.claims.map(claimFingerprint);
  if (new Set(fingerprints).size !== fingerprints.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'duplicate claim content is forbidden',
      path: ['claims'],
    });
  }
  if (new Set(value.forbidden_claims).size !== value.forbidden_claims.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'duplicate forbidden_claims are forbidden',
      path: ['forbidden_claims'],
    });
  }
}

export const ProductElementLockDraftV1Schema = z
  .object({
    ...ProductLockDraftContentShape,
    draft_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    addUniqueDraftContentIssues(value, ctx);
    const { draft_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'draft_digest does not match payload',
        path: ['draft_digest'],
      });
    }
  });

const CompiledResultSchema = z
  .object({
    contract_version: z.literal('ArtemisCompileResult.v1'),
    status: z.literal('compiled'),
    request_digest: DigestSchema,
    draft: ProductElementLockDraftV1Schema,
  })
  .strict();

const CompileBlockedResultSchema = z
  .object({
    contract_version: z.literal('ArtemisCompileResult.v1'),
    status: z.literal('blocked'),
    request_digest: DigestSchema,
    error_code: ArtemisBlockCodeSchema,
  })
  .strict();

export const ArtemisCompileResultV1Schema = z
  .discriminatedUnion('status', [
    CompiledResultSchema,
    CompileBlockedResultSchema,
  ])
  .superRefine((value, ctx) => {
    if (
      value.status === 'compiled'
      && value.draft.compile_request_digest !== value.request_digest
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'draft compile_request_digest must match result',
        path: ['draft', 'compile_request_digest'],
      });
    }
  });

const ApprovalReceiptContentShape = {
  contract_version: z.literal('ArtemisApprovalReceipt.v1'),
  receipt_id: OpaqueIdSchema,
  workspace_id: OpaqueIdSchema,
  run_id: OpaqueIdSchema,
  listing_slug: OpaqueIdSchema,
  product_id: OpaqueIdSchema,
  compile_request_digest: DigestSchema,
  draft_digest: DigestSchema,
  approver_account_id: OpaqueIdSchema,
  environment: OpaqueIdSchema,
  decision: z.literal('approved'),
  state_revision: z.number().int().safe().min(1),
};

export const ArtemisApprovalReceiptV1Schema = z
  .object({
    ...ApprovalReceiptContentShape,
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const { receipt_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'receipt_digest does not match payload',
        path: ['receipt_digest'],
      });
    }
  });

export type ProductElementLockDraftV1 =
  z.infer<typeof ProductElementLockDraftV1Schema>;
export type ArtemisApprovalReceiptV1 =
  z.infer<typeof ArtemisApprovalReceiptV1Schema>;

function receiptStructurallyBinds(
  receipt: ArtemisApprovalReceiptV1,
  draft: ProductElementLockDraftV1,
): boolean {
  return receipt.workspace_id === draft.workspace_id
    && receipt.run_id === draft.run_id
    && receipt.listing_slug === draft.listing_slug
    && receipt.product_id === draft.product_id
    && receipt.compile_request_digest === draft.compile_request_digest
    && receipt.draft_digest === draft.draft_digest;
}

export const ArtemisSealRequestV1Schema = z
  .object({
    contract_version: z.literal('ArtemisSealRequest.v1'),
    draft: ProductElementLockDraftV1Schema,
    approval_receipt: ArtemisApprovalReceiptV1Schema,
    request_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (!receiptStructurallyBinds(value.approval_receipt, value.draft)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'approval receipt does not bind draft',
        path: ['approval_receipt'],
      });
    }
    const { request_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'request_digest does not match payload',
        path: ['request_digest'],
      });
    }
  });

const ProductElementLockShape = {
  ...ProductScopeShape,
  contract_version: z.literal('ProductElementLock.v1'),
  claims: z.array(ArtemisClaimV1Schema).min(1),
  forbidden_claims: z.array(TextSchema).default([]),
  source_observations_digest: DigestSchema,
  compile_request_digest: DigestSchema,
  draft_digest: DigestSchema,
  approval_receipt: ArtemisApprovalReceiptV1Schema,
  lock_digest: DigestSchema,
};

function reconstructedDraftFromLock(
  value: Omit<ProductElementLockDraftV1, 'contract_version'>,
): ProductElementLockDraftV1 {
  return {
    contract_version: 'ProductElementLockDraft.v1',
    workspace_id: value.workspace_id,
    run_id: value.run_id,
    brand_slug: value.brand_slug,
    listing_slug: value.listing_slug,
    product_id: value.product_id,
    product_name: value.product_name,
    product_image_artifact_id: value.product_image_artifact_id,
    product_image_storage_key: value.product_image_storage_key,
    product_image_sha256: value.product_image_sha256,
    claims: value.claims,
    forbidden_claims: value.forbidden_claims,
    source_observations_digest: value.source_observations_digest,
    compile_request_digest: value.compile_request_digest,
    draft_digest: value.draft_digest,
  };
}

export const ProductElementLockV1Schema = z
  .object(ProductElementLockShape)
  .strict()
  .superRefine((value, ctx) => {
    addUniqueDraftContentIssues(value, ctx);
    const reconstructedDraft = reconstructedDraftFromLock(value);
    const { draft_digest: _draftDigest, ...draftPayload } = reconstructedDraft;
    if (value.draft_digest !== sha256Digest(draftPayload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'draft_digest does not match approved draft content',
        path: ['draft_digest'],
      });
    }
    if (!receiptStructurallyBinds(value.approval_receipt, reconstructedDraft)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'approval receipt does not bind product element lock',
        path: ['approval_receipt'],
      });
    }
    const { lock_digest: actual, ...payload } = value;
    if (actual !== sha256Digest(payload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'lock_digest does not match payload',
        path: ['lock_digest'],
      });
    }
  });

const SealedResultSchema = z
  .object({
    contract_version: z.literal('ArtemisSealResult.v1'),
    status: z.literal('sealed'),
    request_digest: DigestSchema,
    lock: ProductElementLockV1Schema,
  })
  .strict();

const SealBlockedResultSchema = z
  .object({
    contract_version: z.literal('ArtemisSealResult.v1'),
    status: z.literal('blocked'),
    request_digest: DigestSchema,
    error_code: ArtemisBlockCodeSchema,
  })
  .strict();

export const ArtemisSealResultV1Schema = z
  .discriminatedUnion('status', [
    SealedResultSchema,
    SealBlockedResultSchema,
  ])
  .superRefine((value, ctx) => {
    if (value.status !== 'sealed') return;
    const draft = reconstructedDraftFromLock(value.lock);
    const requestPayload = {
      contract_version: 'ArtemisSealRequest.v1' as const,
      draft,
      approval_receipt: value.lock.approval_receipt,
    };
    if (value.request_digest !== sha256Digest(requestPayload)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'sealed result does not bind seal request',
        path: ['request_digest'],
      });
    }
  });

/**
 * Construct the successful terminal result only when Artemis claims are
 * grounded in the exact Janus observations carried by the compile request.
 */
export function buildArtemisCompiledResultV1(
  requestInput: unknown,
  draftInput: unknown,
): ArtemisCompileResultV1 {
  const request = ArtemisCompileRequestV1Schema.parse(requestInput);
  const draft = ProductElementLockDraftV1Schema.parse(draftInput);
  const source = request.observations;
  const scopeMatches = draft.workspace_id === source.workspace_id
    && draft.run_id === source.run_id
    && draft.brand_slug === source.brand_slug
    && draft.listing_slug === source.listing_slug
    && draft.product_id === source.product_id
    && draft.product_name === source.product_name
    && draft.product_image_artifact_id === source.product_image_artifact_id
    && draft.product_image_storage_key === source.product_image_storage_key
    && draft.product_image_sha256 === source.product_image_sha256;
  const observations = new Map(
    source.observations.map(observation => [
      observation.observation_id,
      observation,
    ]),
  );
  const usedObservationIds = new Set<string>();
  const claimsAreGrounded = draft.claims.every((claim) => {
    const observationId = claim.source_observation_ids[0];
    const item = observations.get(observationId);
    if (item === undefined || usedObservationIds.has(observationId)) return false;
    usedObservationIds.add(observationId);
    return item.kind === claim.kind
      && item.text === claim.text
      && item.evidence_artifact_id === claim.evidence_artifact_id
      && item.evidence_sha256 === claim.evidence_sha256
      && item.provenance.source_record_id === claim.provenance.source_record_id
      && item.provenance.quote === claim.provenance.quote;
  });
  const requiredObservationIds = new Set(
    source.observations
      .filter(observation => (
        observation.kind === 'product_fact'
        || observation.kind === 'social_proof'
      ))
      .map(observation => observation.observation_id),
  );
  const allRequiredObservationsUsed =
    usedObservationIds.size === requiredObservationIds.size
    && [...usedObservationIds].every(id => requiredObservationIds.has(id));
  const expectedForbiddenClaims: string[] = [];
  for (const observation of source.observations) {
    if (
      observation.kind === 'forbidden_claim'
      && !expectedForbiddenClaims.includes(observation.text)
    ) {
      expectedForbiddenClaims.push(observation.text);
    }
  }
  const forbiddenProjectionMatches =
    draft.forbidden_claims.length === expectedForbiddenClaims.length
    && draft.forbidden_claims.every(
      (claim, index) => claim === expectedForbiddenClaims[index],
    );
  if (
    draft.compile_request_digest !== request.request_digest
    || draft.source_observations_digest !== source.observations_digest
    || !scopeMatches
    || !claimsAreGrounded
    || !allRequiredObservationsUsed
    || !forbiddenProjectionMatches
  ) {
    throw new Error('draft claims are not grounded in compile request');
  }
  return ArtemisCompileResultV1Schema.parse({
    contract_version: 'ArtemisCompileResult.v1',
    status: 'compiled',
    request_digest: request.request_digest,
    draft,
  });
}

export interface ArtemisApprovalResolverV1 {
  isCurrentApproval(receipt: Readonly<{
    receipt_id: string;
    receipt_digest: string;
    workspace_id: string;
    run_id: string;
    listing_slug: string;
    product_id: string;
    compile_request_digest: string;
    draft_digest: string;
    approver_account_id: string;
    state_revision: number;
  }>): boolean;
}

/**
 * Construct a sealed terminal result only after the exact request/lock pair
 * is verified against current durable approval authority.
 */
export function buildArtemisSealedResultV1(
  requestInput: unknown,
  resolver: ArtemisApprovalResolverV1,
): ArtemisSealResultV1 {
  const request = ArtemisSealRequestV1Schema.parse(requestInput);
  const receipt = request.approval_receipt;
  const isCurrent = resolver.isCurrentApproval({
    receipt_id: receipt.receipt_id,
    receipt_digest: receipt.receipt_digest,
    workspace_id: receipt.workspace_id,
    run_id: receipt.run_id,
    listing_slug: receipt.listing_slug,
    product_id: receipt.product_id,
    compile_request_digest: receipt.compile_request_digest,
    draft_digest: receipt.draft_digest,
    approver_account_id: receipt.approver_account_id,
    state_revision: receipt.state_revision,
  });
  if (isCurrent !== true) {
    throw new Error('seal request approval is not current');
  }
  const {
    contract_version: _draftVersion,
    ...approvedDraft
  } = request.draft;
  const lockPayload = {
    ...approvedDraft,
    contract_version: 'ProductElementLock.v1' as const,
    approval_receipt: request.approval_receipt,
  };
  const lock = ProductElementLockV1Schema.parse({
    ...lockPayload,
    lock_digest: sha256Digest(lockPayload),
  });
  return ArtemisSealResultV1Schema.parse({
    contract_version: 'ArtemisSealResult.v1',
    status: 'sealed',
    request_digest: request.request_digest,
    lock,
  });
}

export type ObservationProvenanceV1 =
  z.infer<typeof ObservationProvenanceV1Schema>;
export type JanusProductObservationV1 =
  z.infer<typeof JanusProductObservationV1Schema>;
export type JanusProductObservationsV1 =
  z.infer<typeof JanusProductObservationsV1Schema>;
export type ArtemisCompileRequestV1 =
  z.infer<typeof ArtemisCompileRequestV1Schema>;
export type ArtemisCompileResultV1 =
  z.infer<typeof ArtemisCompileResultV1Schema>;
export type ArtemisSealRequestV1 =
  z.infer<typeof ArtemisSealRequestV1Schema>;
export type ProductElementLockV1 = z.infer<typeof ProductElementLockV1Schema>;
export type ArtemisSealResultV1 =
  z.infer<typeof ArtemisSealResultV1Schema>;
