/**
 * BeatPlan — 대본 계약 (Ares)
 *
 * 대본이 지휘자: 각 비트가 다운스트림(보이스/비주얼/자막/효과음)이 소비할 필드를
 * *모두* 선언한다.
 *
 * grounding: beat dict 키 = beat_index, text, duration_ms, caption, voice_concept,
 * sfx(cue), role, emotion, cta. 부재=폴백.
 */

import { z } from 'zod';

/**
 * Beat — 단일 비트. beat_index는 전 다운스트림 결박의 앵커(필수)
 */
export const BeatSchema = z.object({
  beat_index: z.number().int().min(0),
  text: z.string().default(''),
  emotion: z.string().optional().nullable(),
  shot_type: z.string().optional().nullable(),
  voice_concept: z.string().optional().nullable(),
  sfx_cue: z.string().optional().nullable(),
  caption: z.string().optional().nullable(),
  role: z.enum(['영웅', '가이드', '목격자']).optional().nullable(),
  duration_ms: z.number().int().positive().optional().nullable(),
  cta: z.record(z.any()).optional().nullable(),
}).strict();

export type Beat = z.infer<typeof BeatSchema>;

/**
 * BeatPlan — 비트 시퀀스
 * 척추 = 단일 카테고리 재프레임이 훅~CTA 관통
 */
export const BeatPlanSchema = z.object({
  beats: z.array(BeatSchema).default([]),
  spine: z.string().optional().nullable(),
}).strict();

export type BeatPlan = z.infer<typeof BeatPlanSchema>;

/**
 * BeatPlan 유효성 검사 함수
 * - beat_index 중복 체크
 * - beat_index 연속성 체크 (구멍이 있으면 에러)
 */
export function validateBeatPlan(plan: BeatPlan): string[] {
  const errors: string[] = [];
  const indices = plan.beats.map(b => b.beat_index);

  // 중복 체크
  if (indices.length !== new Set(indices).size) {
    errors.push('beat_index 중복');
  }

  // 연속성 체크
  if (indices.length > 0) {
    const sorted = [...indices].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const expected = Array.from({ length: max - min + 1 }, (_, i) => min + i);
    if (JSON.stringify(sorted) !== JSON.stringify(expected)) {
      errors.push('beat_index 연속성 깨짐(구멍)');
    }
  }

  return errors;
}
