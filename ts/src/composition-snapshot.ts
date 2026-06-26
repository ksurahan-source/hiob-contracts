/**
 * CompositionSnapshot — 조립/렌더 계약 (Atropos → Hephaestus)
 *
 * grounding: composition_snapshot(run_id, selection {slot_id:artifact_id},
 * preview/final_artifact_id, render_status, share_token, rendered_at).
 * + output_url(durable) + gate_passed(렌더前 invariant 증명) = WS06 다리·P1·P10 봉쇄.
 */

import { z } from 'zod';

export const RenderStatusType = z.enum(['pending', 'rendering', 'completed', 'failed']);
export type RenderStatusType = z.infer<typeof RenderStatusType>;

/**
 * CompositionSnapshot — 조립/렌더 스냅샷
 */
export const CompositionSnapshotSchema = z.object({
  run_id: z.string().min(1),
  selection: z.record(z.string()).default({}),
  render_status: RenderStatusType.default('pending'),
  output_url: z.string().url().optional().nullable(),
  preview_artifact_id: z.string().optional().nullable(),
  final_artifact_id: z.string().optional().nullable(),
  share_token: z.string().optional().nullable(),
  gate_passed: z.boolean().default(false),
  rendered_at: z.string().datetime().optional().nullable(),
}).strict()
  .refine(
    // 렌더 시작 전 invariant gate 증명 강제
    (data) => {
      if (data.render_status === 'rendering' || data.render_status === 'completed') {
        return data.gate_passed;
      }
      return true;
    },
    { message: 'gate_passed=false인데 렌더 진행 (invariant 미증명)' }
  )
  .refine(
    // completed이면 output_url 필수
    (data) => {
      if (data.render_status === 'completed') {
        return !!data.output_url;
      }
      return true;
    },
    { message: 'completed인데 output_url 없음 (WS06 배송 다리 끊김)' }
  );

export type CompositionSnapshot = z.infer<typeof CompositionSnapshotSchema>;

/**
 * CompositionSnapshot 유효성 검사 함수
 */
export function validateCompositionSnapshot(snapshot: CompositionSnapshot): string[] {
  const errors: string[] = [];

  if (!snapshot.run_id) {
    errors.push('run_id 없음');
  }

  if (snapshot.render_status === 'rendering' || snapshot.render_status === 'completed') {
    if (!snapshot.gate_passed) {
      errors.push('gate_passed=False인데 렌더 진행 (invariant 미증명)');
    }
  }

  if (snapshot.render_status === 'completed' && !snapshot.output_url) {
    errors.push('completed인데 output_url 없음 (WS06 배송 다리 끊김)');
  }

  return errors;
}
