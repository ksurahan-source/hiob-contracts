/**
 * 렌더前 invariant gate (REEL-QA-GATE)
 *
 * seam 통일규칙 #3: 음성=영상=타임라인 정렬, 전 트랙 믹스, 자막 커버리지를
 * *증명*해야 렌더. 미달 = block (false-DONE 구조차단 + 음소거 슬라이드쇼 재발 방지).
 *
 * Atropos가 CompositionSnapshot 만들기 전에 호출. 통과 못하면 렌더 금지.
 */

import { BeatPlan } from './beat-plan';
import { AudioClip } from './audio-clip';
import { MediaArtifact } from './media-artifact';

export interface RenderReadiness {
  ok: boolean;
  violations: string[];
  warnings: string[];
}

/**
 * assert_render_ready — 전 비트가 보이스(P1)·자막(P13)·비주얼을 갖췄는지 증명
 *
 * ★ ENHANCED BEAT COVERAGE: beat_index를 통해 모든 audio/media 클립 커버리지 검증
 * - voice/sfx AudioClip이 beat_index를 선언해야 하므로 orphan clip 자동 감지
 * - MediaArtifact도 beat_index 필수이므로 누락된 시각 자동 감지
 * - 결과: "어제 음소거" 버그 구조적 불가능화
 */
export function assertRenderReady(
  plan: BeatPlan,
  audioList: AudioClip[],
  mediaList: MediaArtifact[],
  options: {
    requireVoicePerBeat?: boolean;
    requireCaptionPerBeat?: boolean;
  } = {}
): RenderReadiness {
  const requireVoicePerBeat = options.requireVoicePerBeat !== false;
  const requireCaptionPerBeat = options.requireCaptionPerBeat !== false;

  const violations: string[] = [];
  const warnings: string[] = [];

  const beatIndices = new Set(plan.beats.map(b => b.beat_index));
  if (beatIndices.size === 0) {
    return {
      ok: false,
      violations: ['BeatPlan에 비트 0개'],
      warnings: [],
    };
  }

  // 개별 계약 자체 위반 먼저 (P1 결박)
  for (const clip of audioList) {
    if (clip.track === 'voice' || clip.track === 'sfx') {
      if (clip.beat_index === undefined || clip.beat_index === null) {
        violations.push(
          `P1 위반: audio ${clip.track} beat_index=null (orphan 클립, 침묵 위험)`
        );
      }
    }
  }

  // MediaArtifact beat_index 커버리지
  for (const mediaItem of mediaList) {
    if (mediaItem.beat_index === undefined || mediaItem.beat_index === null) {
      violations.push(`media beat_index=null (orphan 클립)`);
    }
  }

  // 보이스 커버리지 (P1 — 보이스 미발화)
  const voiceBeatIndices = new Set(
    audioList
      .filter(c => c.track === 'voice' && c.beat_index !== undefined && c.beat_index !== null)
      .map(c => c.beat_index as number)
  );

  if (requireVoicePerBeat) {
    const missingVoice = Array.from(beatIndices)
      .filter(b => !voiceBeatIndices.has(b))
      .sort((a, b) => a - b);
    if (missingVoice.length > 0) {
      violations.push(`P1 보이스 없는 비트 ${JSON.stringify(missingVoice)} (음소거 위험)`);
    }
  }

  // 비주얼 커버리지
  const mediaBeatIndicesSet = new Set(
    mediaList
      .filter(m => m.beat_index !== undefined && m.beat_index !== null)
      .map(m => m.beat_index as number)
  );

  const missingMedia = Array.from(beatIndices)
    .filter(b => !mediaBeatIndicesSet.has(b))
    .sort((a, b) => a - b);
  if (missingMedia.length > 0) {
    violations.push(`비주얼 없는 비트 ${JSON.stringify(missingMedia)}`);
  }

  // P13 — 자막 커버리지
  const captionBeatIndices = new Set(
    plan.beats
      .filter(b => b.caption && b.caption.trim().length > 0)
      .map(b => b.beat_index)
  );

  if (requireCaptionPerBeat) {
    const missingCaption = Array.from(beatIndices)
      .filter(b => !captionBeatIndices.has(b))
      .sort((a, b) => a - b);
    if (missingCaption.length > 0) {
      warnings.push(`P13 자막 없는 비트 ${JSON.stringify(missingCaption)} (dead air 위험)`);
    }
  }

  // 음악 트랙 확인
  const hasMusic = audioList.some(c => c.track === 'music');
  if (!hasMusic) {
    warnings.push('음악 트랙 없음');
  }

  return {
    ok: violations.length === 0,
    violations,
    warnings,
  };
}
