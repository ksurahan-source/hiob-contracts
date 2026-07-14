/**
 * Factory state model + legal transitions — TS mirror of factory/state.py.
 *
 * ⚠️ AUTHORITY: Python. 전이 규칙은 Python `can_transition`과 일치해야 한다.
 */

export enum FactoryState {
  CREATED = 'CREATED',
  PLANNING = 'PLANNING',
  WAITING_SCRIPT_APPROVAL = 'WAITING_SCRIPT_APPROVAL',
  MEDIA_PLANNING = 'MEDIA_PLANNING',
  WAITING_PLAN_APPROVAL = 'WAITING_PLAN_APPROVAL',
  MATERIALIZING = 'MATERIALIZING',
  MEDIA_READY = 'MEDIA_READY',
  DRAFT_ASSEMBLY = 'DRAFT_ASSEMBLY',
  EDITORIAL_REVIEW = 'EDITORIAL_REVIEW',
  WAITING_FINAL_APPROVAL = 'WAITING_FINAL_APPROVAL',
  FINAL_SNAPSHOT_LOCKED = 'FINAL_SNAPSHOT_LOCKED',
  RENDER_QUEUED = 'RENDER_QUEUED',
  RENDERING = 'RENDERING',
  SUCCEEDED = 'SUCCEEDED',
  BLOCKED = 'BLOCKED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
}

export const TERMINAL_STATES: ReadonlySet<FactoryState> = new Set([
  FactoryState.SUCCEEDED,
  FactoryState.FAILED,
  FactoryState.CANCELLED,
]);

const LINEAR: FactoryState[] = [
  FactoryState.CREATED,
  FactoryState.PLANNING,
  FactoryState.WAITING_SCRIPT_APPROVAL,
  FactoryState.MEDIA_PLANNING,
  FactoryState.WAITING_PLAN_APPROVAL,
  FactoryState.MATERIALIZING,
  FactoryState.MEDIA_READY,
  FactoryState.DRAFT_ASSEMBLY,
  FactoryState.EDITORIAL_REVIEW,
  FactoryState.WAITING_FINAL_APPROVAL,
  FactoryState.FINAL_SNAPSHOT_LOCKED,
  FactoryState.RENDER_QUEUED,
  FactoryState.RENDERING,
  FactoryState.SUCCEEDED,
];

const NEXT = new Map<FactoryState, FactoryState>();
for (let i = 0; i < LINEAR.length - 1; i++) NEXT.set(LINEAR[i], LINEAR[i + 1]);

const REJECT_LOOP = new Map<FactoryState, FactoryState>([
  [FactoryState.WAITING_SCRIPT_APPROVAL, FactoryState.PLANNING],
  [FactoryState.WAITING_PLAN_APPROVAL, FactoryState.MEDIA_PLANNING],
  [FactoryState.WAITING_FINAL_APPROVAL, FactoryState.EDITORIAL_REVIEW],
]);

const EXCEPTIONS: ReadonlySet<FactoryState> = new Set([
  FactoryState.BLOCKED,
  FactoryState.FAILED,
  FactoryState.CANCELLED,
]);

/** `src → dst`가 합법 전이면 true (factory/state.py `can_transition`과 동일). */
export function canTransition(src: FactoryState, dst: FactoryState): boolean {
  if (TERMINAL_STATES.has(src)) return false;
  if (EXCEPTIONS.has(dst)) return true;
  if (src === FactoryState.BLOCKED) return !EXCEPTIONS.has(dst) && !TERMINAL_STATES.has(dst);
  if (NEXT.get(src) === dst) return true;
  if (REJECT_LOOP.get(src) === dst) return true;
  return false;
}

/** 불법 전이면 Error (fail closed). */
export function assertTransition(src: FactoryState, dst: FactoryState): void {
  if (!canTransition(src, dst)) throw new Error(`illegal factory transition: ${src} → ${dst}`);
}

export enum StageExecutionState {
  QUEUED = 'queued',
  RUNNING = 'running',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed',
  CANCEL_REQUESTED = 'cancel_requested',
  CANCELLED = 'cancelled',
  SUPERSEDED = 'superseded',
}

export enum EdgeExecutionState {
  PENDING = 'pending',
  REFINING = 'refining',
  ACCEPTED = 'accepted',
  BLOCKED = 'blocked',
  NEEDS_HUMAN = 'needs_human',
  FAILED = 'failed',
  SUPERSEDED = 'superseded',
}
