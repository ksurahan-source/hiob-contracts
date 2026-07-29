import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

const DigestSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const UuidSchema = z
  .string()
  .regex(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    'UUID must be canonical lowercase RFC 4122',
  );
const PositiveRevision = z.number().int().safe().positive();
const OpaqueIdSchema = z
  .string()
  .transform((value) => value.trim())
  .refine(
    (value) => (
      /^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$/.test(value)
      && value.split('/').every((segment) => (
        segment !== '' && segment !== '.' && segment !== '..'
      ))
    ),
    'technical id must use the opaque id grammar',
  );

const REQUEST_FIELDS = [
  'contract_version',
  'workspace_id',
  'run_id',
  'run_revision',
] as const;
const COMMAND_ID_FIELDS = [
  'workspace_id',
  'run_id',
  'run_revision',
  'request_digest',
  'character_lock_digest',
  'character_lock_version',
  'product_lock_digest',
  'artemis_approval_receipt_id',
  'artemis_approval_receipt_digest',
  'artemis_approval_state_revision',
] as const;
const RECEIPT_FIELDS = [
  'contract_version',
  'command_id',
  ...COMMAND_ID_FIELDS,
  'state',
  'provider_call',
] as const;

function digestFields(
  value: Record<string, unknown>,
  fields: readonly string[],
): string {
  return sha256Digest(
    Object.fromEntries(fields.map((field) => {
      if (!(field in value) || value[field] === undefined) {
        throw new Error(`${field} is required for digest`);
      }
      return [field, value[field]];
    })),
  );
}

function requireOpaqueReceiptId(value: Record<string, unknown>): void {
  const raw = value.artemis_approval_receipt_id;
  const parsed = OpaqueIdSchema.parse(raw);
  if (parsed !== raw) {
    throw new Error('artemis_approval_receipt_id must be canonical');
  }
}

export function deriveStarMakeReadyRequestDigestV1(
  value: Record<string, unknown>,
): string {
  return digestFields(value, REQUEST_FIELDS);
}

export function deriveStarMakeReadyCommandIdV1(
  value: Record<string, unknown>,
): string {
  requireOpaqueReceiptId(value);
  return sha256Digest({
    command_kind: 'star.make_ready',
    ...Object.fromEntries(COMMAND_ID_FIELDS.map((field) => {
      if (!(field in value) || value[field] === undefined) {
        throw new Error(`${field} is required for command id`);
      }
      return [field, value[field]];
    })),
  });
}

export function deriveStarMakeReadyReceiptDigestV1(
  value: Record<string, unknown>,
): string {
  requireOpaqueReceiptId(value);
  return digestFields(value, RECEIPT_FIELDS);
}

const RequestShape = {
  contract_version: z.literal('StarMakeReadyRequest.v1'),
  workspace_id: UuidSchema,
  run_id: UuidSchema,
  run_revision: PositiveRevision,
};

export const StarMakeReadyRequestV1Schema = z
  .object({
    ...RequestShape,
    request_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    let expected;
    try {
      expected = deriveStarMakeReadyRequestDigestV1(value);
    } catch {
      return;
    }
    if (value.request_digest !== expected) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'request_digest does not match make-ready request',
        path: ['request_digest'],
      });
    }
  })
  .transform((value) => Object.freeze(value));

const ReceiptShape = {
  contract_version: z.literal('StarMakeReadyReceipt.v1'),
  command_id: DigestSchema,
  workspace_id: UuidSchema,
  run_id: UuidSchema,
  run_revision: PositiveRevision,
  request_digest: DigestSchema,
  character_lock_digest: DigestSchema,
  character_lock_version: PositiveRevision,
  product_lock_digest: DigestSchema,
  artemis_approval_receipt_id: OpaqueIdSchema,
  artemis_approval_receipt_digest: DigestSchema,
  artemis_approval_state_revision: PositiveRevision,
  state: z.literal('succeeded'),
  provider_call: z.literal('none'),
  receipt_digest: DigestSchema,
};

export const StarMakeReadyReceiptV1Schema = z
  .object(ReceiptShape)
  .strict()
  .superRefine((value, ctx) => {
    const issue = (message: string, path: string[]) => {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message, path });
    };
    let expectedRequest;
    let expectedCommand;
    let expectedReceipt;
    try {
      expectedRequest = deriveStarMakeReadyRequestDigestV1({
        contract_version: 'StarMakeReadyRequest.v1',
        workspace_id: value.workspace_id,
        run_id: value.run_id,
        run_revision: value.run_revision,
      });
      expectedCommand = deriveStarMakeReadyCommandIdV1(value);
      expectedReceipt = deriveStarMakeReadyReceiptDigestV1(value);
    } catch {
      return;
    }
    if (value.request_digest !== expectedRequest) {
      issue('request_digest does not match make-ready scope', ['request_digest']);
    }
    if (value.command_id !== expectedCommand) {
      issue('command_id does not match make-ready authority', ['command_id']);
    }
    if (value.receipt_digest !== expectedReceipt) {
      issue('receipt_digest does not match make-ready receipt', ['receipt_digest']);
    }
  })
  .transform((value) => Object.freeze(value));

export type StarMakeReadyRequestV1 = z.infer<
  typeof StarMakeReadyRequestV1Schema
>;
export type StarMakeReadyReceiptV1 = z.infer<
  typeof StarMakeReadyReceiptV1Schema
>;

export type StarMakeReadyAuthorityV1 = Readonly<{
  command_id: string;
  workspace_id: string;
  run_id: string;
  run_revision: number;
  character_lock_digest: string;
  character_lock_version: number;
  product_lock_digest: string;
  artemis_approval_receipt_id: string;
  artemis_approval_receipt_digest: string;
  artemis_approval_state_revision: number;
}>;

export interface StarMakeReadyResolverV1 {
  isCurrentMakeReady(authority: StarMakeReadyAuthorityV1): boolean;
}

export function starMakeReadyReceiptAuthorizesV1(
  receipt: StarMakeReadyReceiptV1,
  resolver: StarMakeReadyResolverV1,
): boolean {
  return resolver.isCurrentMakeReady({
    command_id: receipt.command_id,
    workspace_id: receipt.workspace_id,
    run_id: receipt.run_id,
    run_revision: receipt.run_revision,
    character_lock_digest: receipt.character_lock_digest,
    character_lock_version: receipt.character_lock_version,
    product_lock_digest: receipt.product_lock_digest,
    artemis_approval_receipt_id: receipt.artemis_approval_receipt_id,
    artemis_approval_receipt_digest:
      receipt.artemis_approval_receipt_digest,
    artemis_approval_state_revision:
      receipt.artemis_approval_state_revision,
  }) === true;
}
