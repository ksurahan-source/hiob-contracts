import assert from 'node:assert/strict';
import test from 'node:test';

import * as PublicContracts from './index.js';
import {
  ExperimentHypothesisV1Schema,
  StoryMapV1Schema,
  VariantSetV1Schema,
  deriveExperimentHypothesisDigestV1,
  deriveStoryMapDigestV1,
  deriveVariantSetDigestV1,
} from './storymap-v1.js';
import { sha256Digest } from './factory/digest.js';

const proofADigest = sha256Digest({
  source: 'ugc-before-after-01', fact: '사용자 7일 기록',
});
const proofBDigest = sha256Digest({
  source: 'ingredient-panel-01', fact: '전성분 공개',
});
const storyPolicyDigest = sha256Digest({ policy: 'viewok-story-v1' });

function storyMapPayload(): Record<string, any> {
  const body = {
    contract_version: 'StoryMap.v1' as const,
    customer_scene: '퇴근 뒤 10분, 거울 앞에서 급하게 피부를 확인한다.',
    bad_alternative_tension: '또 다른 자극적인 제품으로 가리고 싶지만, 반복되는 붉음이 두렵다.',
    urgent_moment: '내일 중요한 약속 전 오늘 밤',
    emotional_stake: '민낯을 숨기지 않고 싶다',
    proof_references: [
      { proof_ref_id: 'ugc-before-after-01', proof_fact_digest: proofADigest },
      { proof_ref_id: 'ingredient-panel-01', proof_fact_digest: proofBDigest },
    ],
    objection: '민감 피부에도 자극적이지 않을까?',
    offer: '7일 안심 체험 키트',
    cta: '지금 체험 키트 보기',
    target_metric: 'landing_click_through_rate',
    content_mode: 'ugc' as const,
    story_policy_digest: storyPolicyDigest,
  };
  return { ...body, story_map_digest: deriveStoryMapDigestV1(body) };
}

function hypothesisPayload(storyMapDigest: string): Record<string, any> {
  const body = {
    contract_version: 'ExperimentHypothesis.v1' as const,
    story_map_digest: storyMapDigest,
    hypothesis: '고객 장면을 첫 2초에 보여주면 랜딩 클릭률이 오른다.',
  };
  return {
    ...body,
    experiment_hypothesis_digest: deriveExperimentHypothesisDigestV1(body),
  };
}

function variantSetPayload(): Record<string, any> {
  const storyMap = storyMapPayload();
  const experimentHypothesis = hypothesisPayload(storyMap.story_map_digest);
  const body = {
    contract_version: 'VariantSet.v1' as const,
    story_map: storyMap,
    story_map_digest: storyMap.story_map_digest,
    experiment_hypothesis: experimentHypothesis,
    variants: [
      {
        variant_id: 'scene-first', story_map_digest: storyMap.story_map_digest,
        hook: '퇴근 후 거울을 피하게 되나요?',
        proof_order: ['ugc-before-after-01', 'ingredient-panel-01'],
        framing: '공감 장면에서 시작한다.', cta: '7일 체험 키트 보기',
      },
      {
        variant_id: 'proof-first', story_map_digest: storyMap.story_map_digest,
        hook: '7일 기록을 먼저 보여드릴게요.',
        proof_order: ['ingredient-panel-01', 'ugc-before-after-01'],
        framing: '증거를 먼저 보여준다.', cta: '성분과 체험 키트 보기',
      },
    ],
  };
  return { ...body, variant_set_digest: deriveVariantSetDigestV1(body) };
}

function rebindVariantSet(value: Record<string, any>): void {
  value.variant_set_digest = deriveVariantSetDigestV1(value);
}

test('Story OS has fixed Python-parity digest vectors', () => {
  const storyMap = StoryMapV1Schema.parse(storyMapPayload());
  const hypothesis = ExperimentHypothesisV1Schema.parse(
    hypothesisPayload(storyMap.story_map_digest),
  );
  const variantSet = VariantSetV1Schema.parse(variantSetPayload());

  assert.equal(storyMap.story_map_digest, 'sha256:c83833bf1f9cb1ff95501ba66c6f3feeb9b71dc80361051a06841b82701fa583');
  assert.equal(hypothesis.experiment_hypothesis_digest, 'sha256:677dd8405c093fd7368c148c195ebde09a492022eb9c39ec232b6f9b37bb8bb6');
  assert.equal(variantSet.variant_set_digest, 'sha256:b9cccc2369498f6a2cf78e37fe49b8bb617b85bd38552253b0bee8004daef1c4');
  assert.equal(variantSet.story_map_digest, storyMap.story_map_digest);
  assert.equal(variantSet.experiment_hypothesis.story_map_digest, storyMap.story_map_digest);
  assert.equal(Object.isFrozen(variantSet), true);
  assert.equal(Object.isFrozen(variantSet.variants[0]), true);
  for (const name of [
    'StoryMapV1Schema', 'ExperimentHypothesisV1Schema', 'VariantSetV1Schema',
  ]) assert.equal(name in PublicContracts, true);
});

test('StoryMap preserves nonblank whitespace and rejects stale digest or extras', () => {
  const padded = storyMapPayload();
  padded.cta = '  지금 체험 키트 보기  ';
  padded.story_map_digest = deriveStoryMapDigestV1(padded);
  const parsed = StoryMapV1Schema.parse(padded);
  assert.equal(parsed.cta, '  지금 체험 키트 보기  ');
  assert.equal(parsed.story_map_digest, 'sha256:9c92117b637ea5e17262311a8fba436473c433f0f4da55c85aa7e577c50cfcbf');

  const stale = storyMapPayload();
  stale.cta = '바뀐 CTA';
  assert.equal(StoryMapV1Schema.safeParse(stale).success, false);
  for (const field of ['identity_lock_digest', 'product_truth_digest', 'proof_fact']) {
    const extra = storyMapPayload();
    extra[field] = 'not allowed';
    assert.equal(StoryMapV1Schema.safeParse(extra).success, false);
  }
});

test('StoryMap follows Python whitespace, Unicode scalar, and length parity', () => {
  for (const [customerScene, accepted] of [
    ['\u0085', false],
    ['\u001c', false],
    ['\uFEFF', true],
  ] as const) {
    const value = storyMapPayload();
    value.customer_scene = customerScene;
    value.story_map_digest = deriveStoryMapDigestV1(value);
    assert.equal(StoryMapV1Schema.safeParse(value).success, accepted);
  }

  const boundary = storyMapPayload();
  boundary.customer_scene = '😀'.repeat(1200);
  boundary.story_map_digest = deriveStoryMapDigestV1(boundary);
  assert.equal(StoryMapV1Schema.safeParse(boundary).success, true);

  const malformed = storyMapPayload();
  malformed.customer_scene = '\ud800';
  assert.throws(
    () => deriveStoryMapDigestV1(malformed),
    /Unicode scalar/,
  );
  malformed.story_map_digest = `sha256:${'0'.repeat(64)}`;
  assert.equal(StoryMapV1Schema.safeParse(malformed).success, false);
});

test('VariantSet permits only hook, proof order, framing, and CTA variation', () => {
  for (const field of [
    'identity_lock_digest', 'product_truth_digest', 'proof_fact_digest', 'proof_references',
  ]) {
    const value = variantSetPayload();
    value.variants[0][field] = 'not allowed';
    rebindVariantSet(value);
    assert.equal(VariantSetV1Schema.safeParse(value).success, false);
  }

  const wrongMap = variantSetPayload();
  wrongMap.variants[0].story_map_digest = `sha256:${'9'.repeat(64)}`;
  rebindVariantSet(wrongMap);
  assert.equal(VariantSetV1Schema.safeParse(wrongMap).success, false);

  const wrongOrder = variantSetPayload();
  wrongOrder.variants[0].proof_order = ['ugc-before-after-01', 'ugc-before-after-01'];
  rebindVariantSet(wrongOrder);
  assert.equal(VariantSetV1Schema.safeParse(wrongOrder).success, false);
});
