/**
 * Exact run-level beat coverage and serial fan-in receipt (Python mirror:
 * hiob_contracts/beat_coverage.py).
 */
import { z } from 'zod';

import { sha256Digest } from './factory/digest.js';

export const BEAT_COVERAGE_CONTRACT_VERSION_V1 = 'BeatCoverage.v1' as const;
export const SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1 = 'SerialFanInReceipt.v1' as const;
export const BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1 = 'BeatLaneTerminalReceipt.v1' as const;
export const MAX_BEAT_COVERAGE_BEATS_V1 = 16;
export const DEFAULT_BEAT_COVERAGE_LANES_V1 = ['athena', 'orpheus_vo', 'atropos'] as const;
export const TERMINAL_BEAT_LANE_STATUSES_V1 = [
  'succeeded',
  'failed',
  'cancelled',
  'blocked',
  'needs_human',
] as const;

const DigestSchema = z.string().regex(/^sha256:[0-9a-f]{64}$/, 'digest must be sha256:<64 lowercase hex>');
const NonBlankString = z.string().refine(
  (value) => value.trim().length > 0,
  'string must not be blank',
);
const PositiveInteger = z.number().int().positive().max(MAX_BEAT_COVERAGE_BEATS_V1).safe();

export const BeatLaneTerminalReceiptV1Schema = z.object({
  run_id: NonBlankString,
  workspace_id: NonBlankString,
  package_digest: DigestSchema,
  plan_digest: DigestSchema,
  beat_index: z.number().int().nonnegative().safe(),
  lane: NonBlankString,
  status: z.enum(TERMINAL_BEAT_LANE_STATUSES_V1).default('succeeded'),
  output_digest: DigestSchema.nullable().default(null),
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

const BeatLaneTerminalReceiptV1InputSchema = z.object({
  run_id: NonBlankString,
  workspace_id: NonBlankString,
  package_digest: DigestSchema,
  plan_digest: DigestSchema,
  beat_index: z.number().int().nonnegative().safe(),
  lane: NonBlankString,
  status: z.enum(TERMINAL_BEAT_LANE_STATUSES_V1).optional(),
  output_digest: DigestSchema.nullable().optional(),
  receipt_digest: DigestSchema.optional(),
  contract_version: z.literal(BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1).optional(),
}).strict();

export function beatLaneTerminalReceiptDigestV1(
  receipt: Omit<BeatLaneTerminalReceiptV1, 'receipt_digest'>,
): string {
  return sha256Digest(receipt);
}

export function createBeatLaneTerminalReceiptV1(
  input: BeatLaneTerminalReceiptV1Input,
): BeatLaneTerminalReceiptV1 {
  const parsedInput = BeatLaneTerminalReceiptV1InputSchema.parse(input);
  const { receipt_digest: _ignoredReceiptDigest, ...withoutReceiptDigest } = parsedInput;
  const payload = {
    ...withoutReceiptDigest,
    status: parsedInput.status ?? 'succeeded',
    output_digest: parsedInput.output_digest ?? null,
    contract_version: parsedInput.contract_version ?? BEAT_LANE_TERMINAL_RECEIPT_CONTRACT_VERSION_V1,
  } as Omit<BeatLaneTerminalReceiptV1, 'receipt_digest'>;
  return BeatLaneTerminalReceiptV1Schema.parse({
    ...payload,
    receipt_digest: sha256Digest(payload),
  });
}

const CoverageContractVersionSchema = z.union([
  z.literal(BEAT_COVERAGE_CONTRACT_VERSION_V1),
  z.literal(SERIAL_FAN_IN_RECEIPT_CONTRACT_VERSION_V1),
]);

interface CoverageCandidate {
  run_id: string;
  workspace_id: string;
  package_digest: string;
  plan_digest: string;
  expected_n_beats: number;
  expected_beat_indices: number[];
  lane_receipts: BeatLaneTerminalReceiptV1[];
  required_lanes: string[];
  coverage_digest: string;
  contract_version: string;
}

function appendExpectedIndexIssue(
  coverage: CoverageCandidate,
  expected: number[],
  ctx: z.RefinementCtx,
): void {
  const invalid = coverage.expected_beat_indices.length !== expected.length
    || coverage.expected_beat_indices.some((value, index) => value !== expected[index]);
  if (invalid) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['expected_beat_indices'],
      message: 'expected_beat_indices must be exactly 0..N-1 without duplicates, holes, or out-of-range values',
    });
  }
}

function appendRequiredLaneIssues(coverage: CoverageCandidate, ctx: z.RefinementCtx): void {
  if (new Set(coverage.required_lanes).size !== coverage.required_lanes.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['required_lanes'], message: 'required_lanes contains duplicate lanes' });
  }
  for (const requiredLane of DEFAULT_BEAT_COVERAGE_LANES_V1) {
    if (!coverage.required_lanes.includes(requiredLane)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['required_lanes'], message: `required_lanes must include ${requiredLane}` });
    }
  }
}

function appendReceiptBindingIssues(
  receipt: BeatLaneTerminalReceiptV1,
  coverage: CoverageCandidate,
  ctx: z.RefinementCtx,
): void {
  const bindings = [
    [receipt.run_id, coverage.run_id, 'run_id'],
    [receipt.workspace_id, coverage.workspace_id, 'workspace_id'],
    [receipt.package_digest, coverage.package_digest, 'package_digest'],
    [receipt.plan_digest, coverage.plan_digest, 'plan_digest'],
  ];
  for (const [observed, expected, name] of bindings) {
    if (observed !== expected) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `lane receipt ${name} does not match coverage` });
    }
  }
  if (receipt.beat_index >= coverage.expected_n_beats) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `lane receipt beat_index ${receipt.beat_index} out of range` });
  }
}

function collectReceiptKeys(coverage: CoverageCandidate, ctx: z.RefinementCtx): Set<string> {
  const seen = new Set<string>();
  for (const receipt of coverage.lane_receipts) {
    const key = `${receipt.beat_index}\u0000${receipt.lane}`;
    if (seen.has(key)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `duplicate lane receipt for ${key}` });
    }
    seen.add(key);
    appendReceiptBindingIssues(receipt, coverage, ctx);
  }
  return seen;
}

function appendMissingReceiptIssue(
  coverage: CoverageCandidate,
  expected: number[],
  seen: Set<string>,
  ctx: z.RefinementCtx,
): void {
  const expectedPairs = new Set(
    expected.flatMap((beatIndex) => coverage.required_lanes.map((lane) => `${beatIndex}\u0000${lane}`)),
  );
  const missing = [...expectedPairs].filter((key) => !seen.has(key));
  if (missing.length > 0) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lane_receipts'], message: `missing lane receipts: ${missing.join(', ')}` });
  }
}

function appendCoverageDigestIssue(coverage: CoverageCandidate, ctx: z.RefinementCtx): void {
  const payload = { ...coverage };
  delete (payload as { coverage_digest?: string }).coverage_digest;
  payload.lane_receipts = [...payload.lane_receipts].sort((left, right) => {
    if (left.beat_index !== right.beat_index) return left.beat_index - right.beat_index;
    return left.lane < right.lane ? -1 : (left.lane > right.lane ? 1 : 0);
  });
  if (coverage.coverage_digest !== sha256Digest(payload)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['coverage_digest'], message: 'coverage_digest does not match coverage payload' });
  }
}

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
  appendExpectedIndexIssue(coverage, expected, ctx);
  appendRequiredLaneIssues(coverage, ctx);
  const seen = collectReceiptKeys(coverage, ctx);
  appendMissingReceiptIssue(coverage, expected, seen, ctx);
  appendCoverageDigestIssue(coverage, ctx);
});

export type BeatCoverageV1 = z.infer<typeof BeatCoverageV1Schema>;
export type SerialFanInReceiptV1 = BeatCoverageV1;

export type BeatCoverageV1Input = Pick<
  BeatCoverageV1,
  'run_id' | 'workspace_id' | 'package_digest' | 'plan_digest'
  | 'expected_n_beats' | 'expected_beat_indices'
> & Partial<Pick<BeatCoverageV1, 'required_lanes' | 'contract_version' | 'coverage_digest'>>
  & { lane_receipts: BeatLaneTerminalReceiptV1Input[] };

const BeatCoverageV1InputSchema = z.object({
  run_id: NonBlankString,
  workspace_id: NonBlankString,
  package_digest: DigestSchema,
  plan_digest: DigestSchema,
  expected_n_beats: PositiveInteger,
  expected_beat_indices: z.array(z.number().int().nonnegative().safe()),
  lane_receipts: z.array(BeatLaneTerminalReceiptV1InputSchema),
  required_lanes: z.array(NonBlankString).optional(),
  coverage_digest: DigestSchema.optional(),
  contract_version: CoverageContractVersionSchema.optional(),
}).strict();

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
  const parsedInput = BeatCoverageV1InputSchema.parse(input);
  const lane_receipts = parsedInput.lane_receipts.map((receipt) => {
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
  } = parsedInput;
  const payload = {
    ...withoutCoverageDigest,
    lane_receipts,
    required_lanes: parsedInput.required_lanes ?? [...DEFAULT_BEAT_COVERAGE_LANES_V1],
    contract_version: parsedInput.contract_version ?? BEAT_COVERAGE_CONTRACT_VERSION_V1,
  } as Omit<BeatCoverageV1, 'coverage_digest'>;
  return BeatCoverageV1Schema.parse({
    ...payload,
    coverage_digest: beatCoverageDigestV1(payload),
  });
}

export const SerialFanInReceiptV1Schema = BeatCoverageV1Schema;
export const BeatCoverageSchema = BeatCoverageV1Schema;
export const SerialFanInReceiptSchema = SerialFanInReceiptV1Schema;
export const createSerialFanInReceiptV1 = createBeatCoverageV1;
export const buildBeatCoverageV1 = createBeatCoverageV1;
export const buildSerialFanInReceiptV1 = createBeatCoverageV1;
