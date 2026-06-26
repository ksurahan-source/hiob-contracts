/**
 * EditDecisionList — 편집 계약 (Artemis)
 *
 * 비트별 컷·전환·자막·타이밍.
 *
 * Editor가 페이싱·다양성·자막완전성을 책임 → Atropos가 그대로 렌더.
 * seam: ≤800ms 서브컷·N이미지 회전·전 비트 자막(P2/P13).
 */

import { z } from 'zod';

/**
 * EditDecision — 단일 비트의 편집 결정
 */
export const EditDecisionSchema = z.object({
  beat_index: z.number().int().min(0),
  cuts_ms: z.array(z.number().int().min(0)).default([]),
  transitions: z.array(z.string()).default([]),
  captions: z.array(z.string()).default([]),
  start_ms: z.number().int().min(0).optional().nullable(),
  duration_ms: z.number().int().positive().optional().nullable(),
}).strict();

export type EditDecision = z.infer<typeof EditDecisionSchema>;

/**
 * EditDecisionList — 편집 결정 시퀀스
 */
export const EditDecisionListSchema = z.object({
  decisions: z.array(EditDecisionSchema).default([]),
}).strict();

export type EditDecisionList = z.infer<typeof EditDecisionListSchema>;

/**
 * EditDecisionList 유효성 검사 함수
 */
export function validateEditDecisionList(list: EditDecisionList): string[] {
  const errors: string[] = [];
  const indices = list.decisions.map(d => d.beat_index);

  // beat_index 중복 체크
  if (indices.length !== new Set(indices).size) {
    errors.push('EditDecision beat_index 중복');
  }

  return errors;
}
