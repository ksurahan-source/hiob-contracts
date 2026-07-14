/**
 * Canonical JSON + SHA-256 digests — TS mirror of hiob_contracts/factory/digest.py
 *
 * ⚠️ AUTHORITY: Python 정전 소스. 이 파일은 미러이며 digest는 Python과
 * byte-for-byte 동일해야 한다 (엣지 해시 체인이 Studio(JS)↔Planet(Python) 경계를
 * 넘나들기 때문). factory.test.ts가 Python이 계산한 기대값으로 parity를 증명한다.
 *
 * 규칙 (Python과 일치):
 * - 객체 키는 재귀적으로 정렬.
 * - 공백 없음 (JSON.stringify 기본).
 * - 비ASCII 보존 (JSON.stringify는 유니코드를 그대로 출력 = ensure_ascii=False).
 * - 배열 순서는 유의미하며 보존.
 * - NaN/Inf는 실패(fail closed) — 언어 간 표준 표현이 없음.
 */
import { createHash } from 'node:crypto';

/** ``sha256:<64 lowercase hex>`` — Python `Digest`와 동일한 문자열 형태. */
export type Digest = string;

export const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;

export class DigestError extends Error {}

function assertFinite(value: unknown): void {
  if (typeof value === 'number' && !Number.isFinite(value)) {
    throw new DigestError(`non-finite number cannot be canonically serialized: ${value}`);
  }
  if (Array.isArray(value)) {
    value.forEach(assertFinite);
  } else if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) assertFinite(v);
  }
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      sorted[key] = canonicalize((value as Record<string, unknown>)[key]);
    }
    return sorted;
  }
  return value;
}

/** 결정적 JSON 문자열 (정렬 키, compact, UTF-8, NaN/Inf 금지). */
export function canonicalJson(value: unknown): string {
  assertFinite(value);
  return JSON.stringify(canonicalize(value));
}

/** 임의 JSON 값의 canonical-JSON SHA-256 → ``sha256:<hex>``. */
export function sha256Digest(value: unknown): Digest {
  const canonical = canonicalJson(value);
  const hex = createHash('sha256').update(canonical, 'utf8').digest('hex');
  return `sha256:${hex}`;
}

/** `value`가 올바른 ``sha256:<64 hex>`` 다이제스트면 true. */
export function isDigest(value: string | null | undefined): boolean {
  return DIGEST_RE.test(value ?? '');
}

/** 유효한 다이제스트면 반환, 아니면 DigestError (fail closed). */
export function assertDigest(value: string, field = 'digest'): Digest {
  if (!isDigest(value)) throw new DigestError(`${field} is not a valid sha256 digest: ${value}`);
  return value;
}
