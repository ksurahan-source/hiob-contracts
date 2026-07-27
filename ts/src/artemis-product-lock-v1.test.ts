import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ArtemisApprovalReceiptV1Schema,
  ArtemisCompileRequestV1Schema,
  ArtemisCompileResultV1Schema,
  ArtemisSealRequestV1Schema,
  ArtemisSealResultV1Schema,
  JanusProductObservationsV1Schema,
  ProductElementLockDraftV1Schema,
  ProductElementLockV1Schema,
  buildArtemisCompiledResultV1,
  buildArtemisSealedResultV1,
} from './artemis-product-lock-v1.js';
import { sha256Digest } from './factory/digest.js';

const PRODUCT_IMAGE_DIGEST =
  'sha256:38c32f891bd492286c2adbe4e5d582675e4e6b9f3e1226804f000628753b19b2';
const EVIDENCE_DIGEST =
  'sha256:74a599b03a2b298085f1cb43063e6440ab53e43c069d9abf7d8db92f5f4e2c4c';
const PYTHON_OBSERVATIONS_DIGEST =
  'sha256:c6c0e6143f4407045055cea286f5cabe906a417cb1d5f7d2e8ada8724f776754';

function observationsPayload() {
  return {
    contract_version: 'JanusProductObservations.v1' as const,
    workspace_id: 'ws-1',
    run_id: 'run-1',
    brand_slug: 'viewok',
    listing_slug: 'nano-mask',
    product_id: 'product-1',
    product_name: 'Nano Mask',
    product_image_artifact_id: 'asset-product-1',
    product_image_sha256: PRODUCT_IMAGE_DIGEST,
    observations: [{
      observation_id: 'obs-1',
      kind: 'product_fact',
      text: '한 장씩 개별 포장',
      evidence_artifact_id: 'asset-detail-1',
      evidence_sha256: EVIDENCE_DIGEST,
      provenance: {
        source_record_id: 'detail-page-1',
        quote: '한 장씩 개별 포장',
      },
    }],
  };
}

function observations() {
  const payload = observationsPayload();
  return {
    ...payload,
    observations_digest: sha256Digest(payload),
  };
}

function compileRequest() {
  const payload = {
    contract_version: 'ArtemisCompileRequest.v1' as const,
    observations: observations(),
  };
  return {
    ...payload,
    request_digest: sha256Digest(payload),
  };
}

function draft() {
  const source = observations();
  const request = compileRequest();
  const payload = {
    contract_version: 'ProductElementLockDraft.v1' as const,
    workspace_id: source.workspace_id,
    run_id: source.run_id,
    brand_slug: source.brand_slug,
    listing_slug: source.listing_slug,
    product_id: source.product_id,
    product_name: source.product_name,
    product_image_artifact_id: source.product_image_artifact_id,
    product_image_sha256: source.product_image_sha256,
    claims: [{
      claim_id: 'claim-1',
      text: '한 장씩 개별 포장',
      kind: 'product_fact',
      source_observation_ids: ['obs-1'],
      evidence_artifact_id: 'asset-detail-1',
      evidence_sha256: EVIDENCE_DIGEST,
      provenance: {
        source_record_id: 'detail-page-1',
        quote: '한 장씩 개별 포장',
      },
    }],
    forbidden_claims: [] as string[],
    source_observations_digest: source.observations_digest,
    compile_request_digest: request.request_digest,
  };
  return {
    ...payload,
    draft_digest: sha256Digest(payload),
  };
}

function rehashDraft(value: ReturnType<typeof draft>) {
  const { draft_digest: _oldDigest, ...payload } = value;
  return {
    ...payload,
    draft_digest: sha256Digest(payload),
  };
}

function approvalReceipt(approvedDraft = draft()) {
  const payload = {
    contract_version: 'ArtemisApprovalReceipt.v1' as const,
    receipt_id: 'approval-receipt-1',
    workspace_id: approvedDraft.workspace_id,
    run_id: approvedDraft.run_id,
    listing_slug: approvedDraft.listing_slug,
    product_id: approvedDraft.product_id,
    compile_request_digest: approvedDraft.compile_request_digest,
    draft_digest: approvedDraft.draft_digest,
    approver_account_id: 'account-1',
    decision: 'approved' as const,
    state_revision: 7,
  };
  return {
    ...payload,
    receipt_digest: sha256Digest(payload),
  };
}

function sealRequest(sealedDraft = draft()) {
  const payload = {
    contract_version: 'ArtemisSealRequest.v1' as const,
    draft: sealedDraft,
    approval_receipt: approvalReceipt(sealedDraft),
  };
  return {
    ...payload,
    request_digest: sha256Digest(payload),
  };
}

function lock(approvedDraft = draft()) {
  const {
    contract_version: _draftVersion,
    draft_digest,
    ...content
  } = approvedDraft;
  const payload = {
    ...content,
    contract_version: 'ProductElementLock.v1' as const,
    draft_digest,
    approval_receipt: approvalReceipt(approvedDraft),
  };
  return {
    ...payload,
    lock_digest: sha256Digest(payload),
  };
}

test('Janus observations own source atoms, never Artemis claims', () => {
  assert.equal(JanusProductObservationsV1Schema.safeParse(observations()).success, true);

  const withClaims = {
    ...observations(),
    claims: [{
      claim_id: 'claim-forged-by-janus',
      source_observation_ids: ['obs-1'],
    }],
  };
  assert.equal(JanusProductObservationsV1Schema.safeParse(withClaims).success, false);
});

test('all technical IDs use one URL-free allow-listed opaque grammar', () => {
  const unsafeIds = [
    'https://signed.example/asset.png',
    's3://bucket/key',
    'ftp://host/file',
    '//host/path',
    'javascript:alert(1)',
    'asset/../../secret',
    'asset/./secret',
    'asset//secret',
  ];
  for (const unsafeId of unsafeIds) {
    const value = structuredClone(observations());
    value.product_image_artifact_id = unsafeId;
    value.observations_digest = sha256Digest({
      ...value,
      observations_digest: undefined,
    });
    assert.equal(
      JanusProductObservationsV1Schema.safeParse(value).success,
      false,
      unsafeId,
    );
  }

  const technicalIdMutations: Array<(value: ReturnType<typeof observations>) => void> = [
    value => { value.workspace_id = 'https://host/workspace'; },
    value => { value.run_id = 's3://bucket/run'; },
    value => { value.listing_slug = '//host/listing'; },
    value => { value.product_id = 'javascript:product'; },
    value => { value.observations[0].observation_id = 'ftp://host/observation'; },
    value => { value.observations[0].evidence_artifact_id = 'data:image/png;base64,x'; },
    value => { value.observations[0].provenance.source_record_id = 'file:///tmp/source'; },
  ];
  for (const mutate of technicalIdMutations) {
    const value = structuredClone(observations());
    mutate(value);
    assert.equal(JanusProductObservationsV1Schema.safeParse(value).success, false);
  }

  const receipt = approvalReceipt();
  receipt.approver_account_id = 'https://host/account';
  assert.equal(ArtemisApprovalReceiptV1Schema.safeParse(receipt).success, false);

  const unsafeRevision = approvalReceipt();
  unsafeRevision.state_revision = Number.MAX_SAFE_INTEGER + 1;
  unsafeRevision.receipt_digest = sha256Digest({
    ...unsafeRevision,
    receipt_digest: undefined,
  });
  assert.equal(
    ArtemisApprovalReceiptV1Schema.safeParse(unsafeRevision).success,
    false,
  );
});

test('observations match the Python golden digest and reject content drift', () => {
  assert.equal(sha256Digest(observationsPayload()), PYTHON_OBSERVATIONS_DIGEST);
  assert.equal(observations().observations_digest, PYTHON_OBSERVATIONS_DIGEST);
  assert.equal(JanusProductObservationsV1Schema.safeParse(observations()).success, true);

  const drifted = structuredClone(observations());
  drifted.product_name = 'drifted';
  assert.equal(JanusProductObservationsV1Schema.safeParse(drifted).success, false);

  const request = compileRequest();
  assert.equal(ArtemisCompileRequestV1Schema.safeParse(request).success, true);
  request.observations.product_name = 'drifted';
  assert.equal(ArtemisCompileRequestV1Schema.safeParse(request).success, false);
});

test('semantic observation aliases cannot bypass deduplication', () => {
  const payload = observationsPayload();
  const first = payload.observations[0];
  payload.observations.push({
    ...structuredClone(first),
    observation_id: 'obs-2',
    evidence_artifact_id: 'asset-detail-alias',
  });
  assert.equal(
    JanusProductObservationsV1Schema.safeParse({
      ...payload,
      observations_digest: sha256Digest(payload),
    }).success,
    false,
  );
});

test('a draft requires an Artemis claim grounded in at least one source observation', () => {
  assert.equal(ProductElementLockDraftV1Schema.safeParse(draft()).success, true);

  const noClaims = structuredClone(draft());
  noClaims.claims = [];
  assert.equal(ProductElementLockDraftV1Schema.safeParse(noClaims).success, false);

  const ungrounded = structuredClone(draft());
  ungrounded.claims[0].source_observation_ids = [];
  assert.equal(ProductElementLockDraftV1Schema.safeParse(ungrounded).success, false);

  const driftedRequestBinding = structuredClone(draft());
  driftedRequestBinding.compile_request_digest = sha256Digest('other request');
  assert.equal(
    ProductElementLockDraftV1Schema.safeParse(driftedRequestBinding).success,
    false,
  );
});

test('semantic claim aliases canonicalize source order and ignore artifact aliases', () => {
  const value = draft();
  const first = value.claims[0];
  value.claims.push({
    ...structuredClone(first),
    claim_id: 'claim-2',
    evidence_artifact_id: 'asset-detail-alias',
  });
  assert.equal(
    ProductElementLockDraftV1Schema.safeParse(rehashDraft(value)).success,
    false,
  );
});

test('each Artemis claim projects exactly one source observation', () => {
  const value = draft();
  value.claims[0].source_observation_ids = ['obs-1', 'obs-2'];
  assert.equal(
    ProductElementLockDraftV1Schema.safeParse(rehashDraft(value)).success,
    false,
  );
});

test('compile result binds the request and has exact compiled or blocked JSON', () => {
  const compiled = {
    contract_version: 'ArtemisCompileResult.v1',
    status: 'compiled',
    request_digest: compileRequest().request_digest,
    draft: draft(),
  };
  const blocked = {
    contract_version: 'ArtemisCompileResult.v1',
    status: 'blocked',
    request_digest: compileRequest().request_digest,
    error_code: 'PRODUCT_LOCK_INCOMPLETE',
  };
  assert.equal(ArtemisCompileResultV1Schema.safeParse(compiled).success, true);
  assert.equal(ArtemisCompileResultV1Schema.safeParse(blocked).success, true);

  assert.equal(
    ArtemisCompileResultV1Schema.safeParse({ ...compiled, error_code: null }).success,
    false,
  );
  assert.equal(
    ArtemisCompileResultV1Schema.safeParse({ ...blocked, draft: null }).success,
    false,
  );
  assert.equal(
    ArtemisCompileResultV1Schema.safeParse({
      ...compiled,
      request_digest: sha256Digest('other request'),
    }).success,
    false,
  );
});

test('compiled-result helper grounds scope and every claim in actual request atoms', () => {
  const request = compileRequest();
  const groundedDraft = draft();
  assert.deepEqual(
    buildArtemisCompiledResultV1(request, groundedDraft),
    {
      contract_version: 'ArtemisCompileResult.v1',
      status: 'compiled',
      request_digest: request.request_digest,
      draft: groundedDraft,
    },
  );

  const mutations: Array<[string, (value: ReturnType<typeof draft>) => void]> = [
    ['scope', value => { value.product_name = 'Other Product'; }],
    ['source digest', value => {
      value.source_observations_digest = sha256Digest('other observations');
    }],
    ['compile request', value => {
      value.compile_request_digest = sha256Digest('other compile request');
    }],
    ['observation id', value => {
      value.claims[0].source_observation_ids = ['never-observed'];
    }],
    ['evidence artifact', value => {
      value.claims[0].evidence_artifact_id = 'asset-detail-other';
    }],
    ['evidence digest', value => {
      value.claims[0].evidence_sha256 = sha256Digest('other evidence');
    }],
    ['provenance record', value => {
      value.claims[0].provenance.source_record_id = 'detail-page-other';
    }],
    ['provenance quote', value => {
      value.claims[0].provenance.quote = '다른 인용';
    }],
  ];

  for (const [label, mutate] of mutations) {
    const forged = structuredClone(groundedDraft);
    mutate(forged);
    assert.throws(
      () => buildArtemisCompiledResultV1(request, rehashDraft(forged)),
      /grounded/,
      label,
    );
  }
});

test('compiled-result helper preserves exact claim text and forbidden projection', () => {
  const request = compileRequest();
  const rewritten = structuredClone(draft());
  rewritten.claims[0].text = 'unrelated medical cure';
  assert.throws(
    () => buildArtemisCompiledResultV1(request, rehashDraft(rewritten)),
    /grounded/,
  );

  const sourcePayload = observationsPayload();
  sourcePayload.observations.push({
    observation_id: 'obs-forbidden-1',
    kind: 'forbidden_claim',
    text: '의학적 치료 효과',
    evidence_artifact_id: 'asset-detail-2',
    evidence_sha256: sha256Digest('detail-crop-2'),
    provenance: {
      source_record_id: 'detail-page-2',
      quote: '치료 효과를 보장하지 않습니다',
    },
  });
  const source = {
    ...sourcePayload,
    observations_digest: sha256Digest(sourcePayload),
  };
  const requestPayload = {
    contract_version: 'ArtemisCompileRequest.v1' as const,
    observations: source,
  };
  const forbiddenRequest = {
    ...requestPayload,
    request_digest: sha256Digest(requestPayload),
  };
  const projected = structuredClone(draft());
  projected.source_observations_digest = source.observations_digest;
  projected.compile_request_digest = forbiddenRequest.request_digest;

  assert.throws(
    () => buildArtemisCompiledResultV1(
      forbiddenRequest,
      rehashDraft(projected),
    ),
    /grounded/,
  );

  projected.forbidden_claims = ['의학적 치료 효과'];
  assert.equal(
    buildArtemisCompiledResultV1(
      forbiddenRequest,
      rehashDraft(projected),
    ).status,
    'compiled',
  );
});

test('compiled-result helper rejects dropped required product observations', () => {
  const sourcePayload = observationsPayload();
  sourcePayload.observations.push({
    observation_id: 'obs-2',
    kind: 'social_proof',
    text: '재구매했어요',
    evidence_artifact_id: 'asset-review-2',
    evidence_sha256: sha256Digest('review-2'),
    provenance: {
      source_record_id: 'review-record-2',
      quote: '재구매했어요',
    },
  });
  const source = {
    ...sourcePayload,
    observations_digest: sha256Digest(sourcePayload),
  };
  const requestPayload = {
    contract_version: 'ArtemisCompileRequest.v1' as const,
    observations: source,
  };
  const request = {
    ...requestPayload,
    request_digest: sha256Digest(requestPayload),
  };
  const dropped = structuredClone(draft());
  dropped.source_observations_digest = source.observations_digest;
  dropped.compile_request_digest = request.request_digest;
  assert.throws(
    () => buildArtemisCompiledResultV1(request, rehashDraft(dropped)),
    /grounded/,
  );
});

test('seal request contains only the draft, durable approval receipt, and digest', () => {
  assert.equal(ArtemisApprovalReceiptV1Schema.safeParse(approvalReceipt()).success, true);
  assert.equal(ArtemisSealRequestV1Schema.safeParse(sealRequest()).success, true);

  assert.equal(
    ArtemisSealRequestV1Schema.safeParse({
      ...sealRequest(),
      workspace_id: 'ws-1',
    }).success,
    false,
  );

  const wrongDraft = structuredClone(sealRequest());
  wrongDraft.approval_receipt.draft_digest = sha256Digest('other draft');
  wrongDraft.approval_receipt.receipt_digest = sha256Digest({
    ...wrongDraft.approval_receipt,
    receipt_digest: undefined,
  });
  wrongDraft.request_digest = sha256Digest({
    contract_version: wrongDraft.contract_version,
    draft: wrongDraft.draft,
    approval_receipt: wrongDraft.approval_receipt,
  });
  assert.equal(ArtemisSealRequestV1Schema.safeParse(wrongDraft).success, false);
});

test('sealed lock reconstructs and verifies the exact approved draft content', () => {
  assert.equal(ProductElementLockV1Schema.safeParse(lock()).success, true);

  const drifted = structuredClone(lock());
  drifted.product_name = 'drifted after approval';
  drifted.lock_digest = sha256Digest({
    ...drifted,
    lock_digest: undefined,
  });
  assert.equal(ProductElementLockV1Schema.safeParse(drifted).success, false);
});

test('seal result has exact sealed or blocked JSON with no inactive null key', () => {
  const sealed = {
    contract_version: 'ArtemisSealResult.v1',
    status: 'sealed',
    request_digest: sealRequest().request_digest,
    lock: lock(),
  };
  const blocked = {
    contract_version: 'ArtemisSealResult.v1',
    status: 'blocked',
    request_digest: sealRequest().request_digest,
    error_code: 'APPROVAL_INVALID',
  };
  assert.equal(ArtemisSealResultV1Schema.safeParse(sealed).success, true);
  assert.equal(ArtemisSealResultV1Schema.safeParse(blocked).success, true);

  assert.equal(
    ArtemisSealResultV1Schema.safeParse({ ...sealed, error_code: null }).success,
    false,
  );
  assert.equal(
    ArtemisSealResultV1Schema.safeParse({ ...blocked, lock: null }).success,
    false,
  );
});

test('sealed-result helper requires current authority and exact request-lock binding', () => {
  const requestA = sealRequest();
  const lockA = lock();
  const currentResolver = {
    calls: 0,
    isCurrentApproval() {
      this.calls += 1;
      return true;
    },
  };
  const staleResolver = { isCurrentApproval: () => false };

  assert.throws(
    () => buildArtemisSealedResultV1(requestA, staleResolver),
    /current/,
  );
  assert.throws(
    () => buildArtemisSealedResultV1(requestA, {
      isCurrentApproval: () => 'false' as unknown as boolean,
    }),
    /current/,
  );

  const sealed = buildArtemisSealedResultV1(
    requestA,
    currentResolver,
  );
  assert.equal(currentResolver.calls, 1);
  assert.deepEqual(sealed, {
    contract_version: 'ArtemisSealResult.v1',
    status: 'sealed',
    request_digest: requestA.request_digest,
    lock: lockA,
  });

  assert.equal(
    ArtemisSealResultV1Schema.safeParse({
      ...sealed,
      request_digest: sha256Digest('other request'),
    }).success,
    false,
  );
});
