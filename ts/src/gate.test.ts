/**
 * Gate validation tests for TypeScript
 */

import { BeatPlanSchema } from './beat-plan.js';
import { AudioClipSchema } from './audio-clip.js';
import { MediaArtifactSchema } from './media-artifact.js';
import { assertRenderReady } from './gate.js';

// ============================================================================
// Test: Gate Validation (렌더전 invariant 검증)
// ============================================================================

function test(name: string, fn: () => void | Promise<void>) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }
}

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

// Test: Zod schema validation blocks invalid voice clip
test('Zod: voice clip with beat_index=null fails schema validation', () => {
  const result = AudioClipSchema.safeParse({
    track: 'voice',
    beat_index: null,
    url: 'http://example.com/voice.mp3',
  });
  assert(!result.success, 'Should fail Zod validation when voice has beat_index=null');
});

// Test: Valid complete composition passes all checks
test('Gate: Valid composition passes all checks', () => {
  const plan = BeatPlanSchema.parse({
    beats: [
      { beat_index: 0, text: 'Line 1', caption: 'Caption 1' },
      { beat_index: 1, text: 'Line 2', caption: 'Caption 2' },
    ],
    spine: 'Test spine',
  });
  const audio = [
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 0,
      url: 'http://example.com/voice0.mp3',
    }),
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 1,
      url: 'http://example.com/voice1.mp3',
    }),
    AudioClipSchema.parse({
      track: 'music',
      beat_index: null,
      url: 'http://example.com/music.mp3',
    }),
  ];
  const media = [
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 0,
      url: 'http://example.com/image0.jpg',
    }),
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 1,
      url: 'http://example.com/image1.jpg',
    }),
  ];

  const result = assertRenderReady(plan, audio, media);
  assert(result.ok, 'Should pass valid composition');
  assert(result.violations.length === 0, 'Should have no violations');
});

// Test: Missing caption generates warning but not violation
test('Gate: Missing caption generates warning but not violation', () => {
  const plan = BeatPlanSchema.parse({
    beats: [
      { beat_index: 0, text: 'Line 1', caption: 'Caption 1' },
      { beat_index: 1, text: 'Line 2' }, // No caption
    ],
  });
  const audio = [
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 0,
      url: 'http://example.com/voice0.mp3',
    }),
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 1,
      url: 'http://example.com/voice1.mp3',
    }),
    AudioClipSchema.parse({
      track: 'music',
      beat_index: null,
      url: 'http://example.com/music.mp3',
    }),
  ];
  const media = [
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 0,
      url: 'http://example.com/image0.jpg',
    }),
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 1,
      url: 'http://example.com/image1.jpg',
    }),
  ];

  const result = assertRenderReady(plan, audio, media);
  assert(result.ok, 'Should pass (caption is warning, not violation)');
  assert(
    result.warnings.some(w => w.includes('자막')),
    'Should warn about missing caption'
  );
});

// Test: Missing voice is violation
test('Gate: Missing voice generates violation', () => {
  const plan = BeatPlanSchema.parse({
    beats: [
      { beat_index: 0, text: 'Line 1' },
      { beat_index: 1, text: 'Line 2' },
    ],
  });
  const audio = [
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 0,
      url: 'http://example.com/voice0.mp3',
    }),
    // Missing voice for beat_index 1
    AudioClipSchema.parse({
      track: 'music',
      beat_index: null,
      url: 'http://example.com/music.mp3',
    }),
  ];
  const media = [
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 0,
      url: 'http://example.com/image0.jpg',
    }),
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 1,
      url: 'http://example.com/image1.jpg',
    }),
  ];

  const result = assertRenderReady(plan, audio, media);
  assert(!result.ok, 'Should fail when voice is missing');
  assert(
    result.violations.some(v => v.includes('보이스')),
    'Should mention missing voice'
  );
});

// Test: Missing media is violation
test('Gate: Missing media generates violation', () => {
  const plan = BeatPlanSchema.parse({
    beats: [
      { beat_index: 0, text: 'Line 1' },
      { beat_index: 1, text: 'Line 2' },
    ],
  });
  const audio = [
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 0,
      url: 'http://example.com/voice0.mp3',
    }),
    AudioClipSchema.parse({
      track: 'voice',
      beat_index: 1,
      url: 'http://example.com/voice1.mp3',
    }),
    AudioClipSchema.parse({
      track: 'music',
      beat_index: null,
      url: 'http://example.com/music.mp3',
    }),
  ];
  const media = [
    MediaArtifactSchema.parse({
      kind: 'still',
      beat_index: 0,
      url: 'http://example.com/image0.jpg',
    }),
    // Missing media for beat_index 1
  ];

  const result = assertRenderReady(plan, audio, media);
  assert(!result.ok, 'Should fail when media is missing');
  assert(
    result.violations.some(v => v.includes('비주얼')),
    'Should mention missing media'
  );
});

// Test: No beats is violation
test('Gate: Empty beat plan generates violation', () => {
  const plan = BeatPlanSchema.parse({
    beats: [],
  });
  const audio: any[] = [];
  const media: any[] = [];

  const result = assertRenderReady(plan, audio, media);
  assert(!result.ok, 'Should fail when no beats');
  assert(
    result.violations.some(v => v.includes('비트 0개')),
    'Should mention zero beats'
  );
});

console.log('\nAll tests passed!');
