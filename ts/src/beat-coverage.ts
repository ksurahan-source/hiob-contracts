/**
 * Exact run-level beat coverage and serial fan-in receipt (Python mirror:
 * hiob_contracts/beat_coverage.py).
 */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

export const BEAT_COVERAGE_CONTRACT_VERSION_V1 = 'BeatCoverage.v1' as const;
export const SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1 = 'SerialFanInReceipt.v1' as const;
export const BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1 = 'BeatLaneTerminalReceipt.v1' as const;
export const DEFAULT_BEAT_COVERAGE_LANES_V1 = ['athena', 'orpheus_vo', 'atropos'] as const;
export const TERMINAL_BEAT_LANE_STATUSES_V1 = [
  'succeeded',
  'failed',
  'cancelled',
  'blocked',
  'needs_human',
] as const;

const DigestSchema = z.string().regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const NonBlankString = z.string().trim().min(1, 'string must not be blank');
const PositiveInteger = z.number().int().positive().safe();

export const BeatLaneTerminalReceiptV1Schema = z.object({
  run_id: NonBlankString,
  workspace_id: NonBlankString,
  package_digest: DigestSchema,
  plan_digest: DigestSchema,
  beat_index: z.number().int().nonnegative().safe(),
  lane: NonBlankString,
  status: z.enum(TERMINAL_BEAT_LANE_STATUSES_V1).default('succeeded'),
  output_digest: DigestSchema.nullable().optional(),
  receipt_digest: DigestSchema,
  contract_version: z.literal(BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1)
    .default(BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1),
}).strict().superRefine((receipt, ctx) => {
  if (receipt.status !== 'succeeded') {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['status'], message: 'lane receipt status must be succeeded' });
  }
  const payload = { ...receipt };
  delete (payload as { receipt_digest?: string }).receipt_digest;
  if (receipt.receipt_digest !== sha256Digest(payload)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['receipt_digest'], message: 'receipt_digest does not match lane receipt payload' });
  }
});

export type BeatLaneTerminalReceiptV1 = z.infer<typeof BeatLaneTerminalReceiptV1Schema>;
export type BeatTerminalReceiptV1 = BeatLaneTerminalReceiptV1;
export type SerialFanInLaneReceiptV1 = BeatLaneTerminalReceiptV1;
export type LaneTerminalReceiptV1 = BeatLaneTerminalReceiptV1;

export type BeatLaneTerminalReceiptV1Input = Pick<
  BeatLaneTerminalReceiptV1,
  'run_id' | 'workspace_id' | 'package_digest' | 'plan_digest' | 'beat_index' | 'lane'
> & Partial<Pick<BeatLaneTerminalReceiptV1, 'status' | 'output_digest' | 'contract_version' | 'receipt_digest'>>;

export function beatLaneTerminalReceiptDigestV1(
  receipt: Omit<BeatLaneTerminalReceiptV1, 'receipt_digest'>,
): string {
  return sha256Digest(receipt);
}

export function createBeatLaneTerminalReceiptV1(
  input: BeatLaneTerminalReceiptV1Input,
): BeatLaneTerminalReceiptV1 {
  const { receipt_digest: _ignoredReceiptDigest, ...withoutReceiptDigest } = input;
  const payload = {
    ...withoutReceiptDigest,
    status: input.status ?? 'succeeded',
    output_digest: input.output_digest ?? null,
    contract_version: input.contract_version ?? BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1,
  } as Omit<BeatLaneTerminalReceiptV1, 'receipt_digest'>;
  return {
    ...payload,
    receipt_digest: sha256Digest(payload),
  };
}

const CoverageContractVersionSchema = z.union([
  z.literal(BEAT_COVERAGE_CONTRACT_VERSION_V1),
  z.literal(SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1),
]);

export const BeatCoverageV1Schema = z.object({
  run_id: NonBlankString,
  workspace_id: NonBlankString,
  package_digest: DigestSchema,
  plan_digest: DigestSchema,
  expected_n_beats: PositiveInteger,
  expected_beat_indices: z.array(z.number().int().nonnegative().safe()),
  lane_receipts: z.array(BeatLaneTerminalReceiptV1Schema),
  required_lanes: z.array(NonBlankString).default([...DEFAULT_BEAT_COVERAGE_LANES_V1]),
  coverage_digest: DigestSchema,
  contract_version: CoverageContractVersionSchema.default(BEAT_COVERAGE_CONTRACT_VERSION_V1),
}).strict().superRefine((coverage, ctx) => {
  const expected = Array.from({ length: coverage.expected_n_beats }, (_, index) => index);
  if (coverage.expected_beat_indices.length !== expected.length
      || coverage.expected_beat_indices.some((value, index) => value !== expected[index])) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['expected_beat_indices'],
      message: 'expected_beat_indices must be exactly 0..N-1 without duplicates, holes, or out-of-range values',
    });
  }
  if (new Set(coverage.required_lanes).size !== coverage.required_lanes.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['required_lanes'], message: 'required_lanes contains duplicate lanes' });
  }
  for (const requiredLane of DEFAULT_BEAT_COVERAGE_LANES_V1) {
    if (!coverage.required_lanes.includes(requiredLane)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['required_lanes'], message: `required_lanes must include ${requiredLane}` });
    }
  }

  const seen = new Set<string>();
  for (const receipt of coverage.lane_receipts) {
    const key = `${receipt.beat_index}\u0000${receipt.lane}`;
    if (seen.has(key)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `duplicate lane receipt for ${key}` });
    }
    seen.add(key);
    if (receipt.run_id !== coverage.run_id) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: 'lane receipt run_id does not match coverage' });
    }
    if (receipt.workspace_id !== coverage.workspace_id) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: 'lane receipt workspace_id does not match coverage' });
    }
    if (receipt.package_digest !== coverage.package_digest) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: 'lane receipt package_digest does not match coverage' });
    }
    if (receipt.plan_digest !== coverage.plan_digest) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: 'lane receipt plan_digest does not match coverage' });
    }
    if (receipt.beat_index >= coverage.expected_n_beats) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `lane receipt beat_index ${receipt.beat_index} out of range` });
    }
  }

  const expectedPairs = new Set(
    expected.flatMap((beatIndex) => coverage.required_lanes.map((lane) => `${beatIndex}\u0000${lane}`)),
  );
  const missing = [...expectedPairs].filter((key) => !seen.has(key));
  if (missing.length > 0) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `missing lane receipts: ${missing.join(', ')}` });
  }

  const payload = { ...coverage };
  delete (payload as { coverage_digest?: string }).coverage_digest;
  payload.lane_receipts = [...payload.lane_receipts].sort((left, right) => {
    if (left.beat_index !== right.beat_index) return left.beat_index - right.beat_index;
    return left.lane < right.lane ? -1 : (left.lane > right.lane ? 1 : 0);
  });
  if (coverage.coverage_digest !== sha256Digest(payload)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['coverage_digest'], message: 'coverage_digest does not match coverage payload' });
  }
});

export type BeatCoverageV1 = z.infer<typeof BeatCoverageV1Schema>;
export type SerialFanInReceiptV1 = BeatCoverageV1;

export type BeatCoverageV1Input = Pick<
  BeatCoverageV1,
  'run_id' | 'workspace_id' | 'package_digest' | 'plan_digest'
  | 'expected_n_beats' | 'expected_beat_indices'
> & Partial<Pick<BeatCoverageV1, 'required_lanes' | 'contract_version' | 'coverage_digest'>>
  & { lane_receipts: BeatLaneTerminalReceiptV1Input[] };

export function beatCoverageDigestPayloadV1(
  coverage: Omit<BeatCoverageV1, 'coverage_digest'>,
): Omit<BeatCoverageV1, 'coverage_digest'> {
  return {
    ...coverage,
    // Completion order is not run identity; canonicalize the exact lane set.
    lane_receipts: [...coverage.lane_receipts].sort((left, right) => {
      if (left.beat_index !== right.beat_index) return left.beat_index - right.beat_index;
      return left.lane < right.lane ? -1 : (left.lane > right.lane ? 1 : 0);
    }),
  };
}

export function beatCoverageDigestV1(
  coverage: Omit<BeatCoverageV1, 'coverage_digest'>,
): string {
  return sha256Digest(beatCoverageDigestPayloadV1(coverage));
}

export function createBeatCoverageV1(input: BeatCoverageV1Input): BeatCoverageV1 {
  const lane_receipts = input.lane_receipts.map((receipt) => {
    const payload = {
      ...receipt,
      status: receipt.status ?? 'succeeded',
      contract_version: receipt.contract_version ?? BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1,
    } as BeatLaneTerminalReceiptV1Input;
    return createBeatLaneTerminalReceiptV1(payload);
  });
  const {
    coverage_digest: _ignoredCoverageDigest,
    lane_receipts: _ignoredLaneReceipts,
    ...withoutCoverageDigest
  } = input;
  const payload = {
    ...withoutCoverageDigest,
    lane_receipts,
    required_lanes: input.required_lanes ?? [...DEFAULT_BEAT_COVERAGE_LANES_V1],
    contract_version: input.contract_version ?? BEAT_COVERAGE_CONTRACT_VERSION_V1,
  } as Omit<BeatCoverageV1, 'coverage_digest'>;
  return {
    ...payload,
    coverage_digest: beatCoverageDigestV1(payload),
  };
}

export const SerialFanInReceiptV1Schema = BeatCoverageV1Schema;
export const BeatCoverageSchema = BeatCoverageV1Schema;
export const SerialFanInReceiptSchema = SerialFanInReceiptV1Schema;
export const createSerialFanInReceiptV1 = createBeatCoverageV1;
export const buildBeatCoverageV1 = createBeatCoverageV1;
export const buildSerialFanInReceiptV1 = createBeatCoverageV1;
