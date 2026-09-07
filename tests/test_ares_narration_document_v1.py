"""A narration selection is immutable evidence, never execution authority."""
from copy import deepcopy

import pytest
from hiob_contracts import canonical_contract_digest_v1

D = 'sha256:' + 'a' * 64


def seal(value, field):
    value = deepcopy(value)
    value.pop(field, None)
    return {**value, field: canonical_contract_digest_v1(value)}


def document():
    segments = [
        {'segment_index': 0, 'source_beat_index': 0, 'source_atom_id': 'hook:primary', 'text': 'A clear hook.'},
        {'segment_index': 1, 'source_beat_index': 5, 'source_atom_id': 'claim:usage', 'text': 'A verified step.'},
        {'segment_index': 2, 'source_beat_index': 15, 'source_atom_id': 'neutral:cta', 'text': 'See the product page.'},
    ]
    text = ' '.join(item['text'] for item in segments)
    return seal({'contract_version': 'AresNarrationDocument.v1',
        'source_request_digest': D, 'source_script_revision_digest': D,
        'source_script_package_digest': D, 'source_catalog_digest': D, 'policy_digest': D,
        'locale': 'en', 'voice_id': 'tc_6837dec48fc46637a9272b88', 'segments': segments,
        'text': text, 'text_digest': canonical_contract_digest_v1({'text': text})}, 'document_digest')


def parse(value):
    from hiob_contracts.ares_narration_document_v1 import AresNarrationDocumentV1
    return AresNarrationDocumentV1.model_validate(value)


def test_selected_voice_count_is_independent_of_source_beat_indices_and_round_trips():
    raw = document()
    result = parse(raw)
    assert result.model_dump(mode='json') == raw
    assert [segment.source_beat_index for segment in result.segments] == [0, 5, 15]
    with pytest.raises((TypeError, ValueError)): result.segments[0].text = 'changed'
    with pytest.raises((TypeError, ValueError)): result.text = 'changed'
    raw['segments'][0]['text'] = 'mutated input'
    assert result.segments[0].text == 'A clear hook.'


@pytest.mark.parametrize('change', [
    lambda x: x.update(text='different approved text'),
    lambda x: x.update(text_digest='sha256:'+'b'*64),
    lambda x: x.update(source_request_digest='invalid'),
    lambda x: x.update(locale='ja'),
    lambda x: x.update(voice_id=''),
    lambda x: x.update(segments=[]),
    lambda x: x['segments'][1].update(segment_index=2),
    lambda x: x['segments'][1].update(source_beat_index=0),
    lambda x: x['segments'][1].update(source_beat_index=16),
    lambda x: x['segments'][1].update(source_beat_index=True),
    lambda x: x['segments'][0].update(source_beat_index=1),
    lambda x: x['segments'][1].update(source_atom_id='hook:primary'),
    lambda x: x['segments'][1].update(text='A clear hook.'),
    lambda x: x['segments'][1].update(text='  '),
    lambda x: x.update(execute=True),
])
def test_resealed_invalid_selection_is_rejected(change):
    raw = document(); change(raw)
    with pytest.raises(ValueError): parse(seal(raw, 'document_digest'))


def test_payload_digest_is_required_even_for_otherwise_valid_document():
    raw = document(); raw['source_request_digest'] = 'sha256:'+'b'*64
    with pytest.raises(ValueError): parse(raw)


def test_segments_are_not_coerced_from_an_unordered_collection():
    raw=document();raw['segments']={'unordered':True}
    with pytest.raises(ValueError): parse(seal(raw,'document_digest'))
