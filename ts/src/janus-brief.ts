/**
 * JanusBrief — 인테이크 계약 (Janus → 전 행성의 단일 입력)
 *
 * grounding: route.js campaign-reels 13Q(identity..proof) + brief 직교축
 * (locale/vertical_mode/protagonist/style/reel_mode). 부재 필드 = None 폴백.
 */

import { z } from 'zod';

/**
 * Intake13Q — 세일즈 인테이크 13문항 (Brand 6 + Customer 7)
 */
export const Intake13QSchema = z.object({
  // Brand 6
  identity: z.string().optional().nullable(),
  usp: z.string().optional().nullable(),
  voice_tone: z.string().optional().nullable(),
  regulation: z.string().optional().nullable(),
  price: z.string().optional().nullable(),
  history: z.string().optional().nullable(),
  // Customer 7
  audience: z.string().optional().nullable(),
  jtbd: z.string().optional().nullable(),
  pain: z.string().optional().nullable(),
  blocker: z.string().optional().nullable(),
  price_sensitivity: z.string().optional().nullable(),
  objection: z.string().optional().nullable(),
  proof: z.string().optional().nullable(),
}).strict();

export type Intake13Q = z.infer<typeof Intake13QSchema>;

/**
 * JanusBrief — Janus가 생산하는 단일 입력 객체
 */
export const JanusBriefSchema = z.object({
  brand_slug: z.string().min(1),
  intake: Intake13QSchema.optional().default({}),
  // 직교축 (새 축 만들지 말고 데이터로 — 부재=byte-identical 폴백)
  locale: z.string().default('ko'),
  vertical_mode: z.string().optional().nullable(),
  protagonist: z.enum(['남', '여', 'everyman']).optional().nullable(),
  style: z.enum(['photoreal', 'cute_illustration']).optional().nullable(),
  reel_mode: z.enum(['PROOF', 'SERIES']).optional().nullable(),
  // 제품/리스팅 그라운딩
  product: z.string().optional().nullable(),
  listing_slug: z.string().optional().nullable(),
  request_text: z.string().optional().nullable(),
  request_interpretation: z.record(z.any()).optional().default({}),
}).strict();

export type JanusBrief = z.infer<typeof JanusBriefSchema>;

/**
 * 유틸 함수: answered_count (Intake13Q의 non-empty 필드 개수)
 */
export function answeredCount(intake: Partial<Intake13Q>): number {
  const fields = [
    'identity', 'usp', 'voice_tone', 'regulation', 'price', 'history',
    'audience', 'jtbd', 'pain', 'blocker', 'price_sensitivity', 'objection', 'proof',
  ] as const;
  return fields.filter(f => {
    const val = intake[f];
    return val && typeof val === 'string' && val.trim().length > 0;
  }).length;
}
