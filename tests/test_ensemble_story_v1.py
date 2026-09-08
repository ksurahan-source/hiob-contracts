"""A shared, scene-based story survives review without losing its cast or speech."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts.ensemble_story_v1 import EnsembleStoryV1, EnsembleBriefV1


def story_value():
    cast = [dict(character_id=f"c{i}", name=f"배우{i}", role="친구",
                 relationship="같이 수영하는 친구", appearance=f"성인, 다른 머리 {i}",
                 wardrobe=f"색상 {i} 티셔츠", voice=f"자연스러운 한국어, 음색 {i}")
            for i in range(1, 5)]
    scenes = []
    for i, duration in enumerate((9000, 11000, 11000, 8000, 15000)):
        scenes.append(dict(scene_id=f"s{i+1}", setting=f"장소 {i % 3}",
            cast_ids=[c['character_id'] for c in cast], action="친구의 말을 듣고 멈춘다.",
            emotional_change="혼자라는 생각에서 함께라는 생각으로",
            product_role="none", product_fact_ids=[], source_duration_sec=(duration+999)//1000,
            trim_start_ms=0, duration_ms=duration,
            dialogue=[dict(character_id=f"c{i%4+1}", text="같이 가자.", start_ms=1000, end_ms=2500)],
            caption=""))
    return dict(contract_version="EnsembleStory.v1", title="같이 가자", logline="친구가 속도를 맞춘다.",
                emotional_hypothesis="함께하는 준비가 다음 수영을 기대하게 한다.",
                target_duration_ms=54000, cast=cast, scenes=scenes,
                hook_variants=[dict(label="관계", opening="또 쉬어?", product_entry="중간 질문")],
                cta="용도와 사용법 보기")


def test_four_cast_and_54_seconds_are_preserved():
    value = story_value()
    plan = EnsembleStoryV1.model_validate(value)
    assert plan.model_dump(mode="json") == value
    assert plan.source_duration_sec == 54
    assert len(plan.cast) == 4


@pytest.mark.parametrize("change", [
    lambda p: p['cast'].append(deepcopy(p['cast'][0])),
    lambda p: p['cast'][1].update(character_id="c1"),
    lambda p: p['scenes'][0]['dialogue'][0].update(character_id="stranger"),
    lambda p: p['scenes'][0].update(duration_ms=8000),
    lambda p: p['scenes'][0].update(source_duration_sec=4),
    lambda p: p['scenes'][0]['dialogue'][0].update(end_ms=12000),
    lambda p: p['scenes'][0]['dialogue'].append(dict(character_id="c2", text="응", start_ms=2000, end_ms=2700)),
    lambda p: p['scenes'][0]['dialogue'][0].update(text="아주긴대사를" * 80),
])
def test_invalid_cast_speech_and_timing_fail_before_any_provider(change):
    value = story_value()
    change(value)
    with pytest.raises(ValidationError):
        EnsembleStoryV1.model_validate(value)


def test_cast_must_contribute_and_not_be_an_unassigned_extra():
    value = story_value()
    for scene in value['scenes']:
        for line in scene['dialogue']:
            line['character_id'] = 'c1'
    with pytest.raises(ValidationError, match="contribute"):
        EnsembleStoryV1.model_validate(value)


def test_unverified_observation_cannot_become_a_customer_testimonial():
    raw = dict(contract_version="EnsembleBrief.v1", target_duration_ms=54000, cast_count=4,
        product_name="아이세이프", product_facts=[dict(fact_id="f1", text="수경용 안티포그")],
        intake_13q={}, observation="수경 때문에 친구보다 출발이 늦다", observation_kind="creator_hypothesis",
        observation_source="", emotional_hypothesis="친구가 속도를 맞춰준다", hook_strategy="relationship",
        creative_notes="한국어 대화. 과장된 효과 주장 없음.")
    assert EnsembleBriefV1.model_validate(raw).observation_kind == "creator_hypothesis"
    raw['observation_kind'] = 'verified_customer'
    with pytest.raises(ValidationError):
        EnsembleBriefV1.model_validate(raw)


def brief_value():
    return dict(contract_version='EnsembleBrief.v1',target_duration_ms=54000,cast_count=4,
        product_name='아이세이프',product_facts=[dict(fact_id='f1',text='수경용 안티포그')],
        intake_13q={},observation='친구를 기다린다',observation_kind='creator_hypothesis',observation_source='',
        emotional_hypothesis='함께 준비한다',hook_strategy='relationship',creative_notes='')


@pytest.mark.parametrize('change',[
    lambda p:p['product_facts'].append(dict(fact_id='f1',text='서로 다른 주장')),
    lambda p:p.update(observation_kind='external_observation'),
    lambda p:p.update(intake_13q={str(i):'answer' for i in range(14)}),
    lambda p:p.update(intake_13q={'pain':'a'*4001}),
])
def test_brief_rejects_ambiguous_sources_and_unbounded_intake(change):
    raw=brief_value();change(raw)
    with pytest.raises(ValidationError): EnsembleBriefV1.model_validate(raw)


@pytest.mark.parametrize('change',[
    lambda p:p['scenes'][0].update(cast_ids=['c1','c2','c3','c1']),
    lambda p:p['scenes'][1].update(scene_id='s1'),
    lambda p:p['scenes'][0].update(cast_ids=['c1','c2','c3','unknown']),
    lambda p:[scene.update(setting='변화 없는 하나의 장소') for scene in p['scenes']],
])
def test_scene_identity_and_situation_invariants(change):
    raw=story_value();change(raw)
    with pytest.raises(ValidationError): EnsembleStoryV1.model_validate(raw)


def test_review_binding_requires_same_cast_target_and_known_product_facts():
    story=EnsembleStoryV1.model_validate(story_value())
    brief=EnsembleBriefV1.model_validate(brief_value())
    assert story.bind_brief(brief) is story
    for patch in ({'cast_count':3},{'target_duration_ms':60000}):
        with pytest.raises(ValueError,match='approved brief'):
            story.bind_brief(EnsembleBriefV1.model_validate({**brief_value(),**patch}))
    raw=story_value();raw['scenes'][0]['product_fact_ids']=['not_evidenced']
    with pytest.raises(ValueError,match='approved source'):
        EnsembleStoryV1.model_validate(raw).bind_brief(brief)


@pytest.mark.parametrize('target',[45000,60000])
def test_three_person_story_and_both_duration_boundaries(target):
    raw=story_value();raw['cast'].pop();raw['target_duration_ms']=target
    for scene in raw['scenes']:
        scene['cast_ids'].remove('c4')
        for line in scene['dialogue']:
            if line['character_id']=='c4':line['character_id']='c2'
    raw['scenes'][-1]['duration_ms']+=target-54000
    raw['scenes'][-1]['source_duration_sec']=(raw['scenes'][-1]['duration_ms']+999)//1000
    assert len(EnsembleStoryV1.model_validate(raw).cast)==3
