from copy import deepcopy

import pytest

from hiob_contracts.ensemble_story_v1 import EnsembleBriefV1, EnsembleStoryV1
from tests.test_ensemble_story_v1 import brief_value, story_value


def direction_value():
    return dict(direction_id='d1', title='내 선택의 이유', customer_situation='처음 제품을 비교한다',
        motivation='나에게 맞는 것을 고르고 싶다', narrative_approach='비교하며 선택하는 이야기',
        rationale='고객은 제품의 존재보다 선택 조건을 궁금해한다', opening='어느 쪽이 내게 맞을까?',
        product_entry='선택 조건을 확인할 때', proof_plan='공식 용도 자료를 확인한다',
        product_fact_ids=['f1'], missing_evidence=['실제 사용 시연'], cta='제품 조건 확인하기',
        recommended_cast_count=2, character_roles=['선택하는 고객', '질문을 돕는 동료'])


def context_value():
    return dict(vertical='생활용품', audience='비교 중인 고객', awareness='solution_aware',
        desire='내게 맞는 선택', hesitation='조건을 모름', desired_action='제품 조건 확인')


def directed_story():
    value=story_value()
    value['creative_direction']=direction_value()
    for scene in value['scenes']:
        scene['intent']=dict(before='선택 조건을 모른다', after='조건 하나를 이해한다',
            observable_action='고객이 두 선택지를 가리킨다', reason_to_continue='다음 조건이 궁금하다')
    return value


def test_selected_direction_and_scene_intent_survive_round_trip():
    raw={**brief_value(), 'creative_context':context_value(), 'creative_direction':direction_value()}
    brief=EnsembleBriefV1.model_validate(raw)
    value=directed_story()
    assert brief.model_dump(mode='json')==raw
    assert EnsembleStoryV1.model_validate(value).bind_brief(brief).model_dump(mode='json')==value


def test_old_immutable_documents_do_not_gain_default_fields():
    assert EnsembleBriefV1.model_validate(brief_value()).model_dump(mode='json')==brief_value()
    assert EnsembleStoryV1.model_validate(story_value()).model_dump(mode='json')==story_value()


def test_direction_cannot_invent_evidence_or_replace_selected_story():
    raw={**brief_value(), 'creative_context':context_value(), 'creative_direction':direction_value()}
    brief=EnsembleBriefV1.model_validate(raw)
    changed=deepcopy(raw);changed['creative_direction']['product_fact_ids']=['unknown']
    with pytest.raises(ValueError, match='fact'):
        EnsembleBriefV1.model_validate(changed)
    value=directed_story();value['creative_direction']['direction_id']='d2'
    with pytest.raises(ValueError, match='direction'):
        EnsembleStoryV1.model_validate(value).bind_brief(brief)


def test_direction_requires_observable_intent_for_every_scene():
    value=directed_story();value['scenes'][2].pop('intent')
    with pytest.raises(ValueError, match='intent'):
        EnsembleStoryV1.model_validate(value)


@pytest.mark.parametrize('role',['demonstration','comparison','self_expression','workflow','trust'])
def test_product_roles_support_more_than_problem_and_guide(role):
    value=story_value();value['scenes'][0]['product_role']=role
    assert EnsembleStoryV1.model_validate(value).scenes[0].product_role==role
