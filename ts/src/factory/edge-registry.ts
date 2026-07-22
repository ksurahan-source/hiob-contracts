/**
 * Semantic-edge registry — TS mirror of factory/edge_registry.py.
 *
 * ⚠️ AUTHORITY: Python. 엣지 목록·criticality는 Python `EDGES`와 일치해야 한다.
 * FR-2: CI가 미등록 직결 엣지를 거부하고, 런타임 manifest/`.well-known`이 이 표와 일치.
 */

export type Criticality = 'required' | 'optional';

export interface SemanticEdge {
  edge_id: string;
  source_planet: string;
  source_contract: string;
  target_planet: string;
  target_node_id: string;
  target_contract: string;
  policy_id: string;
  timeout_ms: number;
  criticality: Criticality;
  note?: string;
}

export const EDGES: readonly SemanticEdge[] = [
  { edge_id: 'j2p', source_planet: 'janus', source_contract: 'JanusBrief',
    target_planet: 'parzifal', target_node_id: 'parzifal.target.consolidate',
    target_contract: 'ParzifalTargetInput', policy_id: 'policy.j2p', timeout_ms: 30000,
    criticality: 'required' },
  { edge_id: 'p2a', source_planet: 'parzifal', source_contract: 'TargetProfile+IdentityLock+CastSheet',
    target_planet: 'ares', target_node_id: 'ares.script.build',
    target_contract: 'AresScriptInput', policy_id: 'policy.p2a', timeout_ms: 30000,
    criticality: 'required' },
  { edge_id: 'a2athena', source_planet: 'ares', source_contract: 'ScriptPackage+BeatPlan',
    target_planet: 'athena', target_node_id: 'athena.plan',
    target_contract: 'AthenaPlanInput', policy_id: 'policy.a2media', timeout_ms: 30000,
    criticality: 'required' },
  { edge_id: 'a2orpheus', source_planet: 'ares', source_contract: 'ScriptPackage+BeatPlan',
    target_planet: 'orpheus', target_node_id: 'orpheus.plan',
    target_contract: 'OrpheusPlanInput', policy_id: 'policy.a2media', timeout_ms: 30000,
    criticality: 'required' },
  { edge_id: 'a2apollo', source_planet: 'ares', source_contract: 'ScriptPackage+BeatPlan',
    target_planet: 'apollo', target_node_id: 'apollo.plan',
    target_contract: 'ApolloPlanInput', policy_id: 'policy.a2media', timeout_ms: 30000,
    criticality: 'optional' },
  { edge_id: 'media2atropos', source_planet: 'athena+orpheus+apollo',
    source_contract: 'VisualArtifactSet+VoiceMusicArtifactSet+SfxArtifactSet',
    target_planet: 'atropos', target_node_id: 'atropos.draft',
    target_contract: 'AtroposDraftInput', policy_id: 'policy.media2atropos', timeout_ms: 45000,
    criticality: 'required' },
  // SUNSET 2026-07-22: artemis.review HTTP removed (quarantined). Keep optional for registry parity with Python; do not re-require on F1.
  { edge_id: 'atropos2artemis', source_planet: 'atropos', source_contract: 'CompositionSnapshot',
    target_planet: 'artemis', target_node_id: 'artemis.review',
    target_contract: 'ArtemisReviewInput', policy_id: 'policy.atropos2artemis', timeout_ms: 45000,
    criticality: 'optional', note: 'SUNSET — artemis.review 404; not on F1 spine' },
  { edge_id: 'artemis2atropos', source_planet: 'artemis', source_contract: 'EditorialProposal',
    target_planet: 'atropos', target_node_id: 'atropos.apply',
    target_contract: 'AtroposApplyInput', policy_id: 'policy.artemis2atropos', timeout_ms: 30000,
    criticality: 'optional', note: 'SUNSET — not on F1 produce spine' },
  { edge_id: 'atropos2hephaestus', source_planet: 'atropos', source_contract: 'CompositionSnapshot',
    target_planet: 'hephaestus', target_node_id: 'hephaestus.render',
    target_contract: 'HephaestusRenderInput', policy_id: 'policy.atropos2hephaestus', timeout_ms: 60000,
    criticality: 'required' },
];

const BY_ID = new Map(EDGES.map((e) => [e.edge_id, e]));

export function getEdge(edgeId: string): SemanticEdge | undefined {
  return BY_ID.get(edgeId);
}

/** source→target 방향 시맨틱 엣지가 등록됐으면 true (fan-in은 `a+b+c` 성분별 검사). */
export function isRegisteredEdge(sourcePlanet: string, targetPlanet: string): boolean {
  return EDGES.some(
    (e) => e.target_planet === targetPlanet && e.source_planet.split('+').includes(sourcePlanet)
  );
}

export function requiredEdges(): SemanticEdge[] {
  return EDGES.filter((e) => e.criticality === 'required');
}
