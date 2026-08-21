import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';

import {
  AresAuthorityArtifactRefV3Schema,
  AresCreateScriptRequestV3Schema,
  AresCreateScriptResultV3Schema,
  AresP2ATargetProjectionV3Schema,
  AresRequestScopeV3Schema,
  AresSemanticBeatV3Schema,
  AresSpeakerSlotV3InputSchema,
  ScriptPackageV3Schema,
  aresCreateScriptRequestV3SchemaDigest,
  aresCreateScriptResultV3SchemaDigest,
  aresP2ATargetProjectionV3SchemaDescriptor,
  aresP2ATargetProjectionV3SchemaDigest,
  authorityRefReceiptDigestV3,
} from './ares-create-script-v3.js';
import { deriveCharacterIdentityBindingDigestV1 } from './character-identity-v1.js';
import { deriveVoiceSpecDigestV1 } from './voice-spec-v1.js';

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`);
    return `{${entries.join(',')}}`;
  }
  return JSON.stringify(value);
}

function digest(value: unknown): string {
  return `sha256:${createHash('sha256').update(canonical(value)).digest('hex')}`;
}

const workspaceId = 'ws-v3-1';
const runId = 'run-v3-1';
const identityDigest = digest({ identity: 'lock-1' });
const productDigest = digest({ product: 'truth-1' });
const evidenceDigest = digest({ evidence: 'approved-1' });
const hookDigest = digest({ hook: 'metis-1' });
const starCommandOutputDigest = digest({ star: 'ares-v3-command-1' });
const karmaOutputDigest = digest({ karma: 'p2a-output-1' });

function authorityRef(
  producer: string,
  artifactType: string,
  artifactDigest: string,
  payload: unknown,
) {
  const body = {
    producer,
    artifact_type: artifactType,
    artifact_digest: artifactDigest,
    source_output_digest: digest({
      producer_output: `${producer}-${artifactType}-1`,
    }),
    payload_digest: digest(payload),
    receipt_id: `${producer}-${artifactType}-receipt-1`,
    workspace_id: workspaceId,
    run_id: runId,
  };
  return {
    ...body,
    receipt_digest: authorityRefReceiptDigestV3(body),
  };
}

function sampleRequest() {
  const identity = {
    identity_lock_digest: identityDigest,
    cast_sheet_digest: digest({ cast: 'sheet-1' }),
    speakers: [{
      role: 'lead',
      subject_id: 'mom',
      display_name: '정원이',
      voice_id: null,
      face_id: null,
      identity_binding_digest: null,
    }],
    voice_spec: null,
    locale: 'ko',
    audience_lock: null,
  };
  const product = {
    product_truth_digest: productDigest,
    brand_slug: 'viewok',
    brand_display_name: '뷰옥',
    product_name: 'XL 세럼',
    listing_slug: null,
    listing_pitch: null,
    price_text: null,
    refund_policy_text: null,
    usp_lines: [],
    regulation_notes: null,
    facts_block: {},
  };
  const evidence = {
    evidence_bundle_digest: evidenceDigest,
    claims: [{
      claim_id: 'c1',
      text: '빠른 흡수',
      claim_kind: 'product_fact',
      provenance: null,
      evidence_ref: null,
    }],
    voc_quotes: [],
    allowed_claim_ids: ['c1'],
  };
  const hook = {
    directive_digest: hookDigest,
    archetype_id: 'gossip_reveal',
    hook_line: null,
    hook_register: null,
    experiment_id: null,
    rationale: null,
  };
  const creativeConstraints = {
    n_beats: 2,
    target_duration_sec: null,
    format_mode: null,
    style_mode: null,
    vertical_mode: null,
    goal: null,
    fixed_hook: null,
    human_instruction: '',
    prior_script_package_digest: null,
    banned_phrases: [],
    required_phrases: [],
  };
  const scope = {
    workspace_id: workspaceId,
    run_id: runId,
    operation_id: 'op-script-v3-1',
    idempotency_key: 'ares-script-v3:ws-v3-1:run-v3-1:op-script-v3-1',
  };
  const identityRef = authorityRef(
    'parzifal', 'identity_lock', identityDigest, identity,
  );
  const productRef = authorityRef(
    'janus', 'product_truth', productDigest, product,
  );
  const evidenceRef = authorityRef(
    'artemis', 'evidence_bundle', evidenceDigest, evidence,
  );
  const hookRef = authorityRef(
    'metis', 'hook_directive', hookDigest, hook,
  );
  const targetInput = {
    contract_version: 'AresP2ATargetProjection.v3' as const,
    scope,
    command_source_output_digest: starCommandOutputDigest,
    identity_ref: identityRef,
    product_ref: productRef,
    evidence_ref: evidenceRef,
    hook_ref: hookRef,
    creative_constraints: creativeConstraints,
  };
  const receipt = {
    receipt_id: 'karma-p2a-rcpt-1',
    edge_id: 'p2a',
    run_id: runId,
    factory_revision: 3,
    workspace_id: workspaceId,
    source_output_digests: [
      identityRef.source_output_digest,
      productRef.source_output_digest,
      evidenceRef.source_output_digest,
      hookRef.source_output_digest,
      starCommandOutputDigest,
    ],
    target_contract: {
      name: 'AresP2ATargetProjection',
      version: 'v3',
      schema_digest: aresP2ATargetProjectionV3SchemaDigest(),
    },
    decision: 'accepted' as const,
    target_input: targetInput,
    target_input_digest: digest(targetInput),
    transform_log: [],
    violations: [],
    waiver_receipt_refs: [],
    mapper: {
      planet: 'karma' as const,
      node_id: 'karma.edge.refine',
      revision: 'r3',
      policy_digest: digest({ policy: 'p2a-r3' }),
    },
    created_at: '2026-07-26T00:00:00Z',
  };
  return {
    contract_version: 'AresCreateScriptRequest.v3' as const,
    scope,
    authority: {
      identity_ref: identityRef,
      product_ref: productRef,
      evidence_ref: evidenceRef,
      hook_ref: hookRef,
      p2a_ref: {
        ...authorityRef('karma', 'p2a_receipt', receipt.target_input_digest, targetInput),
        receipt_id: receipt.receipt_id,
        receipt_digest: digest(receipt),
        source_output_digest: karmaOutputDigest,
      },
      accepted_p2a_receipt: receipt,
    },
    identity,
    product_facts: product,
    evidence_and_claims: evidence,
    hook_directive: hook,
    creative_constraints: creativeConstraints,
  };
}

test('V3 speaker requires the atomic face and voice binding', () => {
  const speaker = {
    role: 'lead',
    subject_id: 'mom',
    display_name: '정원이',
    face_id: 'face-mom-1',
    voice_id: 'voice-mom-1',
    identity_binding_digest: deriveCharacterIdentityBindingDigestV1({
      subject_id: 'mom',
      face_id: 'face-mom-1',
      voice_id: 'voice-mom-1',
    }),
  };
  assert.equal(AresSpeakerSlotV3InputSchema.safeParse(speaker).success, true);
  assert.equal(
    AresSpeakerSlotV3InputSchema.safeParse({
      ...speaker,
      identity_binding_digest: digest({ wrong: true }),
    }).success,
    false,
  );
});

test('projection schema rejects cross-scope and wrong-owner refs directly', () => {
  const base = sampleRequest().authority.accepted_p2a_receipt.target_input;
  const mutations: Array<[string, (value: any) => void]> = [
    ['cross-workspace identity', value => {
      value.identity_ref.workspace_id = 'ws-other';
    }],
    ['cross-run product', value => {
      value.product_ref.run_id = 'run-other';
    }],
    ['wrong evidence producer', value => {
      value.evidence_ref.producer = 'janus';
    }],
    ['wrong hook artifact type', value => {
      value.hook_ref.artifact_type = 'product_truth';
    }],
  ];

  for (const [label, mutate] of mutations) {
    const value = structuredClone(base);
    mutate(value);
    for (const field of [
      'identity_ref',
      'product_ref',
      'evidence_ref',
      'hook_ref',
    ] as const) {
      value[field].receipt_digest = authorityRefReceiptDigestV3(value[field]);
    }
    assert.equal(
      AresP2ATargetProjectionV3Schema.safeParse(value).success,
      false,
      label,
    );
  }
});

function blockedResult() {
  const payload = {
    contract_version: 'AresCreateScriptResult.v3' as const,
    status: 'blocked' as const,
    script_package: null,
    semantic_beat_plan: null,
    quality_findings: [],
    provenance: {
      producer: 'ares' as const,
      contract_version: 'AresCreateScriptResult.v3' as const,
      request_content_digest: digest({ request: 1 }),
      model_id: null,
      prompt_digest: null,
      produced_at: null,
    },
    usage: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_cents: 0,
      model_id: null,
    },
    block_reason: 'upstream authority missing',
  };
  return { ...payload, content_digest: digest(payload) };
}

function scriptPackage(
  masterText = '대사',
  voiceText = '대사',
  masterCaption = '자막',
  captionText = '자막',
) {
  const payload = {
    contract_version: 'AresScriptPackage.v3' as const,
    master_sales_script: {
      title: 'XL',
      beats: [{ beat_index: 0, text: masterText, caption: masterCaption }],
    },
    voice_script: [{ beat_index: 0, text: voiceText }],
    caption_script: [{ beat_index: 0, text: captionText }],
    pronunciation_overrides: {},
  };
  return { ...payload, package_digest: digest(payload) };
}

function semanticPlan(packageDigest: string, caption = '자막') {
  const payload = {
    contract_version: 'AresSemanticBeatPlan.v3' as const,
    script_package_digest: packageDigest,
    beats: [{
      beat_index: 0,
      text: '대사',
      caption,
      scene_intent: '제품 효용 발견',
      role_intents: ['lead'],
    }],
  };
  return { ...payload, plan_digest: digest(payload) };
}

function okResultWithCaption(caption = '자막') {
  const pkg = scriptPackage();
  const payload = {
    contract_version: 'AresCreateScriptResult.v3' as const,
    status: 'ok' as const,
    script_package: pkg,
    semantic_beat_plan: semanticPlan(pkg.package_digest, caption),
    quality_findings: [],
    provenance: {
      producer: 'ares' as const,
      contract_version: 'AresCreateScriptResult.v3' as const,
      request_content_digest: digest({ request: 1 }),
      model_id: null,
      prompt_digest: null,
      produced_at: null,
    },
    usage: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_cents: 0,
      model_id: null,
    },
    block_reason: null,
  };
  return { ...payload, content_digest: digest(payload) };
}

function voiceSpec(subjectId = 'mom') {
  const body = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: subjectId,
    rhythm: 'short and quick',
    vocabulary: ['근데'],
    forbidden_phrases: ['혁신적인'],
    approved_examples: ['첫 문장', '둘째 문장', '셋째 문장'],
  };
  return { ...body, voice_spec_digest: deriveVoiceSpecDigestV1(body) };
}

function rehashPackage(value: ReturnType<typeof scriptPackage>) {
  const { package_digest: _digest, ...payload } = value;
  value.package_digest = digest(payload);
  return value;
}

function rehashPlan(value: ReturnType<typeof semanticPlan>) {
  const { plan_digest: _digest, ...payload } = value;
  value.plan_digest = digest(payload);
  return value;
}

function rehashResult<T extends Record<string, any> & { content_digest: string }>(value: T): T {
  const { content_digest: _digest, ...payload } = value;
  value.content_digest = digest(payload);
  return value;
}

test('V3 accepts five producer-issued refs and full scope', () => {
  const parsed = AresCreateScriptRequestV3Schema.parse(sampleRequest());
  assert.equal(parsed.authority.identity_ref.producer, 'parzifal');
  assert.equal(parsed.scope.operation_id, 'op-script-v3-1');
});

test('V3 rejects Star-minted identity authority', () => {
  const body = sampleRequest();
  body.authority.identity_ref.producer = 'star';
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 rejects cross-workspace ref and payload digest tamper', () => {
  const crossScope = sampleRequest();
  crossScope.authority.product_ref.workspace_id = 'other';
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(crossScope).success, false);

  const tampered = sampleRequest();
  tampered.product_facts.product_name = 'tampered';
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(tampered).success, false);
});

test('V3 rejects non-canonical Karma receipt digest', () => {
  const body = sampleRequest();
  body.authority.p2a_ref.receipt_digest = digest({ fake: true });
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 keeps Karma output and receipt digests distinct', () => {
  const body = AresCreateScriptRequestV3Schema.parse(sampleRequest());
  assert.equal(body.authority.p2a_ref.source_output_digest, karmaOutputDigest);
  assert.notEqual(
    body.authority.p2a_ref.source_output_digest,
    body.authority.p2a_ref.receipt_digest,
  );
});

test('V3 authority receipt subject rejects source output digest drift', () => {
  const ref = structuredClone(sampleRequest().authority.identity_ref);
  ref.source_output_digest = digest({ forged: 'producer-output' });

  assert.equal(AresAuthorityArtifactRefV3Schema.safeParse(ref).success, false);
});

test('V3 source coverage does not accept artifact digests', () => {
  const body = sampleRequest();
  body.authority.accepted_p2a_receipt.source_output_digests = [
    identityDigest,
    productDigest,
    evidenceDigest,
    hookDigest,
    starCommandOutputDigest,
  ];
  const receiptDigest = digest(body.authority.accepted_p2a_receipt);
  body.authority.p2a_ref.receipt_digest = receiptDigest;
  body.authority.p2a_ref.source_output_digest = receiptDigest;
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 rejects missing Star command source output', () => {
  const body = sampleRequest();
  body.authority.accepted_p2a_receipt.source_output_digests =
    body.authority.accepted_p2a_receipt.source_output_digests.filter(
      item => item !== starCommandOutputDigest,
    );
  const receiptDigest = digest(body.authority.accepted_p2a_receipt);
  body.authority.p2a_ref.receipt_digest = receiptDigest;
  body.authority.p2a_ref.source_output_digest = receiptDigest;
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 rejects generic authority receipt subject drift', () => {
  const body = sampleRequest();
  body.authority.identity_ref.receipt_id = 'different-receipt-id';
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 freezes embedded Karma projection and preserves its request digest', () => {
  const request = AresCreateScriptRequestV3Schema.parse(sampleRequest());
  const before = digest(request);
  const targetInput = request.authority.accepted_p2a_receipt.target_input;
  assert.ok(targetInput);
  assert.equal(Object.isFrozen(targetInput), true);
  assert.equal(Object.isFrozen(targetInput.scope), true);
  assert.throws(() => {
    (targetInput.scope as Record<string, unknown>).operation_id = 'replayed';
  });
  assert.equal(digest(request), before);
});

test('V3 rejects p2a projection replay across operations', () => {
  const body = sampleRequest();
  body.scope.operation_id = 'op-script-v3-replayed';
  body.scope.idempotency_key = 'ares-script-v3:replayed';
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 rejects a fully rehashed incomplete p2a projection', () => {
  const body = sampleRequest();
  const receipt = body.authority.accepted_p2a_receipt;
  const targetInput = {
    ...(receipt.target_input as Record<string, unknown>),
  };
  delete targetInput.hook_ref;
  const targetDigest = digest(targetInput);
  receipt.target_input = targetInput as typeof receipt.target_input;
  receipt.target_input_digest = targetDigest;
  body.authority.p2a_ref.artifact_digest = targetDigest;
  body.authority.p2a_ref.payload_digest = targetDigest;
  const receiptDigest = digest(receipt);
  body.authority.p2a_ref.receipt_digest = receiptDigest;
  body.authority.p2a_ref.source_output_digest = receiptDigest;
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
});

test('V3 rejects creative-constraint replay against the Karma projection', () => {
  for (const [field, value] of [
    ['n_beats', 3],
    ['human_instruction', '다른 지시'],
  ] as const) {
    const body = sampleRequest();
    body.creative_constraints[field] = value as never;
    assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
  }
});

test('semantic beat rejects Athena-owned shot/camera/render fields', () => {
  for (const field of [
    'shot',
    'camera',
    'camera_mode',
    'cameraAngle',
    'shot_plan',
    'render_mode',
    'visual_prompt',
  ]) {
    const beat = {
      beat_index: 0,
      text: '엄마, 이건 꼭 보세요.',
      caption: '꼭 보세요',
      scene_intent: '엄마가 제품의 핵심 효용을 발견한다',
      role_intents: ['lead', 'product'],
      [field]: 'handheld',
    };
    assert.equal(AresSemanticBeatV3Schema.safeParse(beat).success, false);
  }
});

test('script package rejects nested authority and visual-production aliases', () => {
  for (const alias of [
    'camera_mode',
    'cameraAngle',
    'shot_plan',
    'visual_prompt',
    'persona_cast',
    'cast',
    'scene_direction',
    'visual_context',
  ]) {
    const valid = scriptPackage();
    const master = valid.master_sales_script as {
      title: string;
      beats: Array<Record<string, unknown>>;
    };
    master.beats[0][alias] = 'forbidden';
    const { package_digest: _digest, ...payload } = valid;
    valid.package_digest = digest(payload);
    assert.equal(ScriptPackageV3Schema.safeParse(valid).success, false);
  }
});

test('script package binds master beats to voice and caption segments', () => {
  assert.equal(ScriptPackageV3Schema.safeParse(scriptPackage()).success, true);
  assert.equal(
    ScriptPackageV3Schema.safeParse(scriptPackage('다른 대사', '대사')).success,
    false,
  );
  assert.equal(
    ScriptPackageV3Schema.safeParse(
      scriptPackage('대사', '대사', '다른 자막', '자막'),
    ).success,
    false,
  );
});

test('result binds semantic beat text and caption to package segments', () => {
  assert.equal(AresCreateScriptResultV3Schema.safeParse(okResultWithCaption()).success, true);
  assert.equal(
    AresCreateScriptResultV3Schema.safeParse(okResultWithCaption('다른 자막')).success,
    false,
  );
});

test('result content_digest binds the fully defaulted Zod payload', () => {
  const valid = blockedResult();
  assert.equal(
    valid.content_digest,
    'sha256:c202627e893f27d9da7931b9db969255601c2a01cf7144dc503f5ec24ecd1419',
  );
  assert.equal(AresCreateScriptResultV3Schema.safeParse(valid).success, true);

  const tampered = { ...valid, block_reason: 'different reason' };
  assert.equal(AresCreateScriptResultV3Schema.safeParse(tampered).success, false);
});

test('master_sales_script accepts canonical JSON only and safeParse never throws', () => {
  class ScriptClass {
    value = 'not plain JSON';
  }
  const sparse: unknown[] = [];
  sparse.length = 2;
  sparse[1] = 'x';
  const invalidValues: unknown[] = [
    Number.NaN,
    Number.POSITIVE_INFINITY,
    1.5,
    Number.MAX_SAFE_INTEGER + 1,
    sparse,
    new ScriptClass(),
  ];

  for (const invalid of invalidValues) {
    const body = {
      contract_version: 'AresScriptPackage.v3' as const,
      master_sales_script: { beats: invalid },
      voice_script: [{ beat_index: 0, text: '대사' }],
      caption_script: [{ beat_index: 0, text: '자막' }],
      pronunciation_overrides: {},
      package_digest: digest({ placeholder: true }),
    };
    let result: ReturnType<typeof ScriptPackageV3Schema.safeParse> | undefined;
    assert.doesNotThrow(() => {
      result = ScriptPackageV3Schema.safeParse(body);
    });
    assert.equal(result?.success, false);
  }
});

test('NonBlank fields preserve surrounding whitespace', () => {
  const scope = AresRequestScopeV3Schema.parse({
    workspace_id: ' ws ',
    run_id: ' run ',
    operation_id: ' op ',
    idempotency_key: ' key ',
  });
  assert.equal(scope.operation_id, ' op ');

  const beat = AresSemanticBeatV3Schema.parse({
    beat_index: 0,
    text: ' 대사 ',
    caption: ' 자막 ',
    scene_intent: ' 장면 의도 ',
    role_intents: [' lead '],
  });
  assert.equal(beat.text, ' 대사 ');
  assert.equal(beat.role_intents[0], ' lead ');
});

test('parsed V3 contracts are deeply frozen', () => {
  const request = AresCreateScriptRequestV3Schema.parse(sampleRequest());
  assert.equal(Object.isFrozen(request), true);
  assert.equal(Object.isFrozen(request.authority), true);
  assert.equal(Object.isFrozen(request.identity.speakers), true);
  assert.equal(Object.isFrozen(request.product_facts.facts_block), true);
  assert.throws(() => {
    (request.scope as { operation_id: string }).operation_id = 'other';
  });

  const result = AresCreateScriptResultV3Schema.parse(blockedResult());
  assert.equal(Object.isFrozen(result), true);
  assert.equal(Object.isFrozen(result.provenance), true);
  assert.equal(Object.isFrozen(result.quality_findings), true);
});

test('produced_at requires a real ISO-8601 UTC timestamp', () => {
  const original = blockedResult();
  const body = {
    ...original,
    provenance: {
      ...original.provenance,
      produced_at: '2026-02-30T00:00:00Z',
    },
  };
  assert.equal(AresCreateScriptResultV3Schema.safeParse(body).success, false);
});

test('result only accepts script package plus semantic beat plan', () => {
  const body = {
    contract_version: 'AresCreateScriptResult.v3' as const,
    status: 'blocked' as const,
    script_package: null,
    semantic_beat_plan: null,
    quality_findings: [],
    provenance: {
      producer: 'ares' as const,
      contract_version: 'AresCreateScriptResult.v3' as const,
      request_content_digest: digest({ request: 1 }),
    },
    usage: {},
    content_digest: digest({ result: 1 }),
    block_reason: 'upstream authority missing',
    render_job_id: 'render-1',
  };
  assert.equal(AresCreateScriptResultV3Schema.safeParse(body).success, false);
});

test('Python and TS schema shape digests are stable', () => {
  const requestDigest = aresCreateScriptRequestV3SchemaDigest();
  const resultDigest = aresCreateScriptResultV3SchemaDigest();
  assert.equal(
    requestDigest,
    'sha256:18087f9d1af7646a0dbbbb0a399f65a32a3a72767a26a03520f81e6083de948f',
  );
  assert.equal(
    resultDigest,
    'sha256:72a50c6d3305b158441328e024d630a9cdd0fe3f974d76bce7ab80d9d52c8de0',
  );
  assert.equal(
    aresP2ATargetProjectionV3SchemaDigest(),
    'sha256:3f535adb7c18e0bafd9a48adfb79e3bd4d33236fc711fcf3f6d5583c457b5510',
  );
  assert.notEqual(requestDigest, resultDigest);
});

test('projection schema digest binds nested types and invariants', () => {
  const descriptor = aresP2ATargetProjectionV3SchemaDescriptor();
  const baseline = digest(descriptor);
  const driftedRange = structuredClone(descriptor) as {
    properties: {
      creative_constraints: {
        properties: { n_beats: { maximum: number } };
      };
    };
  };
  driftedRange.properties.creative_constraints.properties.n_beats.maximum = 65;
  assert.notEqual(digest(driftedRange), baseline);

  const driftedInvariant = structuredClone(descriptor) as {
    invariants: string[];
  };
  driftedInvariant.invariants = driftedInvariant.invariants.filter(
    (item) => item
      !== 'source_output_digests_cover_four_authority_outputs_and_command',
  );
  assert.notEqual(digest(driftedInvariant), baseline);
});

test('canonical JSON rejects symbols, exotic arrays, accessors, nonobjects, and unpaired text', () => {
  const invalidMasters: unknown[] = [];
  invalidMasters.push({ beats: [], [Symbol('hidden')]: true });
  const namedArray = [1];
  Object.defineProperty(namedArray, 'named', { enumerable: true, value: 2 });
  invalidMasters.push({ beats: namedArray });
  const accessorArray = [1];
  Object.defineProperty(accessorArray, '0', { enumerable: true, get: () => 1 });
  invalidMasters.push({ beats: accessorArray });
  const hidden = { beats: [] as unknown[] };
  Object.defineProperty(hidden, 'secret', { enumerable: false, value: 1 });
  invalidMasters.push(hidden);
  invalidMasters.push({ beats: [{ text: '\ud800' }] });
  invalidMasters.push({ beats: [{ callback: () => true }] });
  invalidMasters.push(null, [], 'text-only');

  for (const masterSalesScript of invalidMasters) {
    const pkg = scriptPackage();
    pkg.master_sales_script = masterSalesScript as typeof pkg.master_sales_script;
    assert.doesNotThrow(() => ScriptPackageV3Schema.safeParse(pkg));
    assert.equal(ScriptPackageV3Schema.safeParse(pkg).success, false);
  }

  const canonicalPackage = scriptPackage();
  (canonicalPackage.master_sales_script as Record<string, unknown>).metadata = {
    nullable: null,
    enabled: false,
  };
  rehashPackage(canonicalPackage);
  assert.equal(ScriptPackageV3Schema.safeParse(canonicalPackage).success, true);
});

test('identity and evidence reject duplicate roles, VoiceSpec scope, and claim authority drift', () => {
  const duplicateRoles = sampleRequest();
  duplicateRoles.identity.speakers.push({
    role: 'lead', subject_id: 'guest', display_name: 'Guest',
    voice_id: null, face_id: null, identity_binding_digest: null,
  });
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(duplicateRoles).success, false);

  const multiSpeaker = sampleRequest();
  multiSpeaker.identity.speakers.push({
    role: 'guest', subject_id: 'guest', display_name: 'Guest',
    voice_id: null, face_id: null, identity_binding_digest: null,
  });
  (multiSpeaker.identity as Record<string, any>).voice_spec = voiceSpec();
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(multiSpeaker).success, false);

  const wrongVoiceSubject = sampleRequest();
  (wrongVoiceSubject.identity as Record<string, any>).voice_spec = voiceSpec('other');
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(wrongVoiceSubject).success, false);

  const duplicateClaims = sampleRequest();
  duplicateClaims.evidence_and_claims.claims.push({
    ...structuredClone(duplicateClaims.evidence_and_claims.claims[0]),
    text: 'different text',
  });
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(duplicateClaims).success, false);

  const disallowedClaim = sampleRequest();
  disallowedClaim.evidence_and_claims.allowed_claim_ids = ['other'];
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(disallowedClaim).success, false);
});

test('authority bundle rejects every producer and Karma receipt binding drift', () => {
  const mutations: Array<(value: ReturnType<typeof sampleRequest>) => void> = [
    value => {
      value.authority.identity_ref.producer = 'janus';
      value.authority.identity_ref.receipt_digest = authorityRefReceiptDigestV3(
        value.authority.identity_ref,
      );
    },
    value => { value.authority.accepted_p2a_receipt.edge_id = 'j2p'; },
    value => { value.authority.accepted_p2a_receipt.target_contract.name = 'OtherProjection'; },
    value => { value.authority.accepted_p2a_receipt.target_contract.version = 'v2'; },
    value => { value.authority.p2a_ref.receipt_id = 'other-receipt'; },
    value => { value.authority.p2a_ref.artifact_digest = digest({ other: 'target' }); },
  ];
  for (const mutate of mutations) {
    const body = sampleRequest();
    mutate(body);
    body.authority.p2a_ref.receipt_digest = digest(body.authority.accepted_p2a_receipt);
    assert.equal(AresCreateScriptRequestV3Schema.safeParse(body).success, false);
  }

  const blocked = sampleRequest();
  const blockedReceipt = blocked.authority.accepted_p2a_receipt as Record<string, any>;
  blockedReceipt.decision = 'blocked';
  blockedReceipt.target_input = null;
  blockedReceipt.target_input_digest = null;
  blocked.authority.p2a_ref.receipt_digest = digest(blocked.authority.accepted_p2a_receipt);
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(blocked).success, false);
});

test('request rejects Karma scope, canonical projection, p2a digest, and sealed artifact drift', () => {
  const authorityRefScope = sampleRequest();
  authorityRefScope.authority.product_ref = structuredClone(
    authorityRefScope.authority.product_ref,
  );
  authorityRefScope.authority.product_ref.workspace_id = 'ws-other';
  authorityRefScope.authority.product_ref.receipt_digest = authorityRefReceiptDigestV3(
    authorityRefScope.authority.product_ref,
  );
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(authorityRefScope).success, false);

  const receiptScope = sampleRequest();
  receiptScope.authority.accepted_p2a_receipt.workspace_id = 'ws-other';
  receiptScope.authority.p2a_ref.receipt_digest = digest(
    receiptScope.authority.accepted_p2a_receipt,
  );
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(receiptScope).success, false);

  const projectionDrift = sampleRequest();
  projectionDrift.authority.accepted_p2a_receipt.target_input = structuredClone(
    projectionDrift.authority.accepted_p2a_receipt.target_input,
  );
  projectionDrift.authority.accepted_p2a_receipt.target_input.creative_constraints.n_beats = 3;
  const targetDigest = digest(projectionDrift.authority.accepted_p2a_receipt.target_input);
  projectionDrift.authority.accepted_p2a_receipt.target_input_digest = targetDigest;
  projectionDrift.authority.p2a_ref.artifact_digest = targetDigest;
  projectionDrift.authority.p2a_ref.payload_digest = targetDigest;
  projectionDrift.authority.p2a_ref.receipt_digest = digest(
    projectionDrift.authority.accepted_p2a_receipt,
  );
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(projectionDrift).success, false);

  const p2aDrift = sampleRequest();
  p2aDrift.authority.p2a_ref.payload_digest = digest({ wrong: 'projection' });
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(p2aDrift).success, false);

  const artifactDrift = sampleRequest();
  artifactDrift.identity.identity_lock_digest = digest({ wrong: 'identity artifact' });
  assert.equal(AresCreateScriptRequestV3Schema.safeParse(artifactDrift).success, false);
});

test('script package rejects sequence, master beat, and terminal digest drift independently', () => {
  const invalidPackages: Array<ReturnType<typeof scriptPackage>> = [];
  const unequal = scriptPackage();
  unequal.caption_script = [];
  invalidPackages.push(rehashPackage(unequal));
  const voiceOrder = scriptPackage();
  voiceOrder.voice_script[0].beat_index = 1;
  invalidPackages.push(rehashPackage(voiceOrder));
  const captionOrder = scriptPackage();
  captionOrder.caption_script[0].beat_index = 1;
  invalidPackages.push(rehashPackage(captionOrder));
  const blankVoice = scriptPackage();
  blankVoice.voice_script[0].text = '   ';
  invalidPackages.push(rehashPackage(blankVoice));
  const missingMasterBeats = scriptPackage();
  delete (missingMasterBeats.master_sales_script as Record<string, unknown>).beats;
  invalidPackages.push(rehashPackage(missingMasterBeats));
  const wrongCount = scriptPackage();
  (wrongCount.master_sales_script.beats as unknown[]).push({
    beat_index: 1, text: 'extra', caption: 'extra',
  });
  invalidPackages.push(rehashPackage(wrongCount));
  const nullBeat = scriptPackage();
  nullBeat.master_sales_script.beats[0] = null as never;
  invalidPackages.push(rehashPackage(nullBeat));
  const arrayBeat = scriptPackage();
  arrayBeat.master_sales_script.beats[0] = [] as never;
  invalidPackages.push(rehashPackage(arrayBeat));
  const wrongIndex = scriptPackage();
  wrongIndex.master_sales_script.beats[0].beat_index = 1;
  invalidPackages.push(rehashPackage(wrongIndex));
  for (const pkg of invalidPackages) {
    assert.equal(ScriptPackageV3Schema.safeParse(pkg).success, false);
  }
  assert.equal(ScriptPackageV3Schema.safeParse({
    ...scriptPackage(), package_digest: digest({ wrong: 'package' }),
  }).success, false);
});

test('semantic plan and result enforce indices, digests, artifacts, segments, and terminal reason', () => {
  const pkg = scriptPackage();
  const badIndex = semanticPlan(pkg.package_digest);
  badIndex.beats[0].beat_index = 1;
  rehashPlan(badIndex);
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(),
    script_package: pkg,
    semantic_beat_plan: badIndex,
  })).success, false);
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(),
    semantic_beat_plan: {
      ...semanticPlan(pkg.package_digest),
      plan_digest: digest({ wrong: 'plan' }),
    },
  })).success, false);

  const base = okResultWithCaption();
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...base, script_package: null, semantic_beat_plan: null,
  })).success, false);

  const differentPackageDigest = semanticPlan(digest({ other: 'package' }));
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(), semantic_beat_plan: differentPackageDigest,
  })).success, false);

  const extraBeatPlan = semanticPlan(base.script_package.package_digest);
  extraBeatPlan.beats.push({
    beat_index: 1, text: 'extra', caption: 'extra', scene_intent: 'extra', role_intents: ['lead'],
  });
  rehashPlan(extraBeatPlan);
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(), semantic_beat_plan: extraBeatPlan,
  })).success, false);

  const textDriftPlan = semanticPlan(base.script_package.package_digest);
  textDriftPlan.beats[0].text = 'different text';
  rehashPlan(textDriftPlan);
  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(), semantic_beat_plan: textDriftPlan,
  })).success, false);

  assert.equal(AresCreateScriptResultV3Schema.safeParse(rehashResult({
    ...okResultWithCaption(), block_reason: 'not allowed',
  })).success, false);

  const blocked = blockedResult();
  assert.equal(AresCreateScriptResultV3Schema.safeParse({
    ...blocked,
    script_package: scriptPackage(),
    content_digest: digest({ placeholder: 'blocked artifacts' }),
  }).success, false);
  const { content_digest: _blockedDigest, ...blockedPayload } = blocked;
  const noReasonPayload = { ...blockedPayload, block_reason: null };
  assert.equal(AresCreateScriptResultV3Schema.safeParse({
    ...noReasonPayload, content_digest: digest(noReasonPayload),
  }).success, false);
});

test('V3 UTC validation rejects malformed and year-zero timestamps without throwing', () => {
  for (const producedAt of ['not-a-timestamp', '0000-01-01T00:00:00Z']) {
    const value = blockedResult();
    (value.provenance as Record<string, any>).produced_at = producedAt;
    assert.doesNotThrow(() => AresCreateScriptResultV3Schema.safeParse(value));
    assert.equal(AresCreateScriptResultV3Schema.safeParse(value).success, false);
  }
});
