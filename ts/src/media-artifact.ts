/**
 * MediaArtifact — 시각 계약 (Athena)
 *
 * 비트별 이미지/영상.
 *
 * grounding: artifact(storage_key, mime, duration_ms, width, height) + slot(beat_index).
 */

import { z } from 'zod';

export const MediaKindType = z.enum(['still', 'video', 'avatar', 'carousel']);
export type MediaKindType = z.infer<typeof MediaKindType>;

/**
 * MediaArtifact — 시각 아티팩트
 */
export const MediaArtifactSchema = z.object({
  kind: MediaKindType,
  beat_index: z.number().int().min(0),
  url: z.string().url().optional().nullable(),
  storage_key: z.string().optional().nullable(),
  duration_ms: z.number().int().positive().optional().nullable(),
  width: z.number().int().positive().optional().nullable(),
  height: z.number().int().positive().optional().nullable(),
  mime: z.string().optional().nullable(),
  style: z.enum(['photoreal', 'cute_illustration']).optional().nullable(),
}).strict()
  .refine(
    (data) => data.url || data.storage_key,
    { message: 'url/storage_key 없음' }
  );

export type MediaArtifact = z.infer<typeof MediaArtifactSchema>;

/**
 * MediaArtifact 유효성 검사 함수
 */
export function validateMediaArtifact(artifact: MediaArtifact): string[] {
  const errors: string[] = [];

  if (!artifact.url && !artifact.storage_key) {
    errors.push('url/storage_key 없음');
  }

  return errors;
}
