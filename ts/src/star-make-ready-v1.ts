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

const PARZIFAL_PAYLOAD_FIELDS = [
  'contract_version',
  'receipt_id',
  'workspace_id',
  'run_id',
  'subject_id',
  'face_id',
  'voice_id',
  'identity_binding_digest',
  'element_lock_digest',
] as const;
const MAKE_READY_PAYLOAD_FIELDS = [
  'contract_version',
  'workspace_id',
  'run_id',
  'parzifal_record_ref',
  'parzifal_receipt',
  'current_element_lock_digest',
  'provider_call',
] as const;

function digestFields(
  value: Record<string, unknown>,
  fields: readonly string[],
): string {
  return sha256Digest(
    Object.fromEntries(fields.map((field) => [field, value[field]])),
  );
}

export function deriveParzifalIdentityReceiptPayloadDigestV1(
  value: Record<string, unknown>,
): string {
  return digestFields(value, PARZIFAL_PAYLOAD_FIELDS);
}

export function deriveStarMakeReadyReceiptDigestV1(
  value: Record<string, unknown>,
): string {
  return digestFields(value, MAKE_READY_PAYLOAD_FIELDS);
}

export const ParzifalRecordRefV1Schema = z
  .object({
    id: NonBlankString,
    version: z.number().int().positive(),
    digest: DigestSchema,
  })
  .strict();

export const ParzifalIdentityReceiptV1Schema = z
  .object({
    contract_version: z.literal('ParzifalIdentityReceipt.v1'),
    receipt_id: NonBlankString,
    workspace_id: NonBlankString,
    run_id: NonBlankString,
    subject_id: NonBlankString,
    face_id: NonBlankString,
    voice_id: NonBlankString,
    identity_binding_digest: DigestSchema,
    element_lock_digest: DigestSchema,
    payload_digest: DigestSchema,
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
    if (
      value.payload_digest
      !== deriveParzifalIdentityReceiptPayloadDigestV1(value)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          'payload_digest does not match Parzifal identity receipt payload',
        path: ['payload_digest'],
      });
    }
  });

export const StarMakeReadyReceiptV1Schema = z
  .object({
    contract_version: z.literal('StarMakeReadyReceipt.v1'),
    workspace_id: NonBlankString,
    run_id: NonBlankString,
    parzifal_record_ref: ParzifalRecordRefV1Schema,
    parzifal_receipt: ParzifalIdentityReceiptV1Schema,
    current_element_lock_digest: DigestSchema,
    provider_call: z.literal('none'),
    receipt_digest: DigestSchema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const receipt = value.parzifal_receipt;
    const recordRef = value.parzifal_record_ref;
    const issue = (message: string, path: (string | number)[]) => {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message, path });
    };
    if (receipt.workspace_id !== value.workspace_id) {
      issue(
        'parzifal_receipt.workspace_id must match workspace_id',
        ['parzifal_receipt', 'workspace_id'],
      );
    }
    if (receipt.run_id !== value.run_id) {
      issue(
        'parzifal_receipt.run_id must match run_id',
        ['parzifal_receipt', 'run_id'],
      );
    }
    if (recordRef.id !== receipt.receipt_id) {
      issue(
        'parzifal_record_ref.id must match parzifal_receipt.receipt_id',
        ['parzifal_record_ref', 'id'],
      );
    }
    if (recordRef.digest !== receipt.payload_digest) {
      issue(
        'parzifal_record_ref.digest must match parzifal_receipt.payload_digest',
        ['parzifal_record_ref', 'digest'],
      );
    }
    if (value.current_element_lock_digest !== receipt.element_lock_digest) {
      issue(
        'current_element_lock_digest must match parzifal_receipt.element_lock_digest',
        ['current_element_lock_digest'],
      );
    }
    if (
      value.receipt_digest
      !== deriveStarMakeReadyReceiptDigestV1(value)
    ) {
      issue(
        'receipt_digest does not match Star make-ready receipt payload',
        ['receipt_digest'],
      );
    }
  });

export type ParzifalRecordRefV1 = z.infer<
  typeof ParzifalRecordRefV1Schema
>;
export type ParzifalIdentityReceiptV1 = z.infer<
  typeof ParzifalIdentityReceiptV1Schema
>;
export type StarMakeReadyReceiptV1 = z.infer<
  typeof StarMakeReadyReceiptV1Schema
>;
