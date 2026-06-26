/**
 * AudioClip — 청각 계약 (Orpheus voice/music, Apollo sfx)
 *
 * ★ P1 봉쇄: voice·sfx 클립은 beat_index 결박이 *필수*. 계약이 강제하므로
 * "비트에 안 붙어 침묵"(어젯밤 음소거 슬라이드쇼)이 구조적으로 불가능해진다.
 *
 * grounding: slot(track∈{voiceover,sfx,music}, beat_index) + artifact(duration_ms, storage_key).
 * music은 run-level 허용(slot.beat_index nullable).
 */

import { z } from 'zod';

export const AudioTrackType = z.enum(['voice', 'sfx', 'music']);
export type AudioTrackType = z.infer<typeof AudioTrackType>;

/**
 * AudioClip — 청각 아티팩트
 */
export const AudioClipSchema = z.object({
  track: AudioTrackType,
  beat_index: z.number().int().min(0).optional().nullable(),
  url: z.string().url().optional().nullable(),
  storage_key: z.string().optional().nullable(),
  duration_ms: z.number().int().positive().optional().nullable(),
  voice_concept: z.string().optional().nullable(),
  affinity: z.string().optional().nullable(),
}).strict()
  .refine(
    (data) => data.url || data.storage_key,
    { message: 'url/storage_key 둘 다 없음 (재생 불가)' }
  )
  .refine(
    // voice/sfx는 beat_index 필수
    (data) => {
      if (data.track === 'voice' || data.track === 'sfx') {
        return data.beat_index !== undefined && data.beat_index !== null;
      }
      return true;
    },
    { message: 'voice/sfx 클립에 beat_index 없음 (P1 침묵 위험)' }
  );

export type AudioClip = z.infer<typeof AudioClipSchema>;

/**
 * AudioClip 유효성 검사 함수
 * 추가 처리가 필요한 경우 사용 (Zod schema 보완용)
 */
export function validateAudioClip(clip: AudioClip): string[] {
  const errors: string[] = [];

  // Zod validation already covers the main cases, but we keep this for explicit documentation
  if (clip.track === 'voice' || clip.track === 'sfx') {
    if (clip.beat_index === undefined || clip.beat_index === null) {
      errors.push(`${clip.track} 클립에 beat_index 없음 (P1 침묵 위험)`);
    }
  }

  if (!clip.url && !clip.storage_key) {
    errors.push('url/storage_key 둘 다 없음 (재생 불가)');
  }

  return errors;
}
