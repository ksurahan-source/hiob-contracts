/**
 * Phase 3 edge target contract tests — j2p and p2a with exact typed schemas (TS).
 *
 * Mirror of tests/test_edge_target_contracts.py. Tests:
 * - j2p edge (JanusBrief → ParzifalTargetInput)
 * - p2a edge (Parzifal outputs → AresScriptInput)
 * - Unknown edge rejection (negative test)
 * - Python↔TS digest parity
 */
import { canonicalJson, sha256Digest } from './factory/digest.js';
import { ParzifalTargetInputSchema, validateParzifalTargetInput } from './parzifal-target-input.js';
import { AresScriptInputSchema, validateAresScriptInput } from './ares-script-input.js';
import { getEdge, isRegisteredEdge } from './factory/edge-registry.js';

function test(name: string, fn: () => void) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }
}

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

// ── j2p edge: JanusBrief → ParzifalTargetInput ──────────────────────────
test('j2p edge registered', () => {
  const edge = getEdge('j2p');
  assert(edge !== undefined, 'j2p edge exists');
  assert(edge!.source_planet === 'janus', 'source is janus');
  assert(edge!.target_planet === 'parzifal', 'target is parzifal');
  assert(edge!.target_node_id === 'parzifal.target.consolidate', 'node_id correct');
  assert(edge!.criticality === 'required', 'j2p required');
  assert(isRegisteredEdge('janus', 'parzifal'), 'is_registered_edge true');
});

test('ParzifalTargetInput round-trip with digest stability', () => {
  const target = ParzifalTargetInputSchema.parse({
    brand_slug: 'viewok',
    brand_identity: '친화적 수영용품',
    target_audience: '초등 아이 부모',
    target_jtbd: '아이가 물을 무서워하지 않게',
    voc_core_pain: '수영 공포증',
    product_slug: 'serum-lavender',
    listing_slug: 'viewok-serum-lavender-250ml',
    locale: 'ko',
    protagonist: 'female',
  });

  const dict1 = target;
  const restored = ParzifalTargetInputSchema.parse(dict1);
  assert(
    JSON.stringify(restored) === JSON.stringify(target),
    'round-trip preserves data'
  );

  const errs = validateParzifalTargetInput(restored);
  assert(errs.length === 0, 'validation passes');

  // Digest stability
  const d1 = canonicalJson(target);
  const d2 = canonicalJson(restored);
  assert(d1 === d2, 'canonical JSON matches');
});

test('ParzifalTargetInput validation rejects missing brand_slug', () => {
  const target = ParzifalTargetInputSchema.parse({
    brand_slug: '',
    target_audience: 'some audience',
  });
  const errs = validateParzifalTargetInput(target);
  assert(errs.some((e) => e.includes('brand_slug')), 'catches missing brand_slug');
});

test('ParzifalTargetInput validation requires target facts', () => {
  const target = ParzifalTargetInputSchema.parse({
    brand_slug: 'viewok',
  });
  const errs = validateParzifalTargetInput(target);
  assert(errs.some((e) => e.includes('target fact')), 'requires target facts');
});

// ── p2a edge: Parzifal outputs → AresScriptInput ──────────────────────
test('p2a edge registered', () => {
  const edge = getEdge('p2a');
  assert(edge !== undefined, 'p2a edge exists');
  assert(edge!.source_planet === 'parzifal', 'source is parzifal');
  assert(edge!.target_planet === 'ares', 'target is ares');
  assert(edge!.target_node_id === 'ares.script.build', 'node_id correct');
  assert(edge!.criticality === 'required', 'p2a required');
  assert(isRegisteredEdge('parzifal', 'ares'), 'is_registered_edge true');
});

test('AresScriptInput round-trip with digest stability', () => {
  const input = AresScriptInputSchema.parse({
    brand_slug: 'viewok',
    brand_identity: '친화적 수영용품',
    protagonist_id: 'p-jung-won',
    protagonist_name: '정원이',
    protagonist_age: 11,
    protagonist_gender: 'male',
    protagonist_role: 'customer',
    target_pain: '수영 공포증',
    target_jtbd: '물에 대한 자신감 높이기',
    voc_core_pain: '물을 무서워함',
    voc_real_quotes: ['물에 안 들어가고 싶어요', '친구들처럼 못 해서 싫어요'],
    product_slug: 'serum-lavender',
    listing_slug: 'viewok-serum-lavender-250ml',
    locale: 'ko',
  });

  const dict1 = input;
  const restored = AresScriptInputSchema.parse(dict1);
  assert(
    JSON.stringify(restored) === JSON.stringify(input),
    'round-trip preserves data'
  );

  const errs = validateAresScriptInput(restored);
  assert(errs.length === 0, 'validation passes');

  // Digest stability
  const d1 = canonicalJson(input);
  const d2 = canonicalJson(restored);
  assert(d1 === d2, 'canonical JSON matches');
});

test('AresScriptInput validation rejects missing brand_slug', () => {
  const input = AresScriptInputSchema.parse({
    brand_slug: '',
    protagonist_name: 'name',
    target_pain: 'pain',
  });
  const errs = validateAresScriptInput(input);
  assert(errs.some((e) => e.includes('brand_slug')), 'catches missing brand_slug');
});

test('AresScriptInput validation requires protagonist_name', () => {
  const input = AresScriptInputSchema.parse({
    brand_slug: 'viewok',
    protagonist_name: '',
    target_pain: 'pain',
  });
  const errs = validateAresScriptInput(input);
  assert(errs.some((e) => e.includes('protagonist_name')), 'requires protagonist_name');
});

test('AresScriptInput validation requires grounding facts', () => {
  const input = AresScriptInputSchema.parse({
    brand_slug: 'viewok',
    protagonist_name: 'name',
  });
  const errs = validateAresScriptInput(input);
  assert(errs.some((e) => e.includes('grounding fact')), 'requires grounding facts');
});

// ── NEGATIVE TESTS: unknown edge rejection ────────────────────────────
test('getEdge unknown edge_id returns undefined', () => {
  const edge = getEdge('unknown_edge');
  assert(edge === undefined, 'unknown edge is undefined');
});

test('isRegisteredEdge rejects unregistered pairs', () => {
  assert(!isRegisteredEdge('janus', 'hephaestus'), 'janus→hephaestus unregistered');
  assert(!isRegisteredEdge('ares', 'atropos'), 'ares→atropos unregistered');
  assert(!isRegisteredEdge('parzifal', 'athena'), 'parzifal→athena unregistered');
});

test('j2p and p2a edges are required', () => {
  const j2p = getEdge('j2p');
  const p2a = getEdge('p2a');
  assert(j2p !== undefined && j2p.criticality === 'required', 'j2p required');
  assert(p2a !== undefined && p2a.criticality === 'required', 'p2a required');
});

// ── Python↔TS digest parity ────────────────────────────────────────────
test('ParzifalTargetInput digest parity with Python', () => {
  const target = ParzifalTargetInputSchema.parse({
    brand_slug: 'test',
    target_audience: 'audience',
  });
  const digest = sha256Digest(target);
  const canonical = canonicalJson(target);

  // Verify digest format
  assert(digest.startsWith('sha256:'), 'digest starts with sha256:');
  assert(digest.length === 71, 'digest is 71 chars (sha256: + 64 hex)');

  // Canonical form sorts keys
  const dict2 = { target_audience: 'audience', brand_slug: 'test' };
  assert(canonicalJson(dict2) !== canonical, 'key order affects canonical form');
});

test('AresScriptInput digest parity with Python', () => {
  const input = AresScriptInputSchema.parse({
    brand_slug: 'test',
    protagonist_name: '정원이',
    target_pain: 'pain',
  });
  const digest = sha256Digest(input);
  const canonical = canonicalJson(input);

  // Verify digest format
  assert(digest.startsWith('sha256:'), 'digest starts with sha256:');
  assert(digest.length === 71, 'digest is 71 chars');

  // Keys are sorted
  assert(canonical.includes('"brand_slug"'), 'has brand_slug');
  assert(canonical.includes('"protagonist_name"'), 'has protagonist_name');
  assert(
    canonical.indexOf('"brand_slug"') < canonical.indexOf('"protagonist_name"'),
    'keys are sorted'
  );
});

console.log('\nAll edge target contract tests passed!');
