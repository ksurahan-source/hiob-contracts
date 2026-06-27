"""Test suite for hiob_contracts — 7+3 계약 검증."""
import pytest
from dataclasses import FrozenInstanceError

from hiob_contracts import (
    Intake13Q, JanusBrief,
    Beat, BeatPlan,
    MediaArtifact, AudioClip,
    KlingVideo, Heroine, FeedbackSignal,
    EditDecision, EditDecisionList,
    CompositionSnapshot, ReelMetric,
    RenderReadiness, assert_render_ready,
)


# ============================================================================
# Test: Core 7 Contracts (기존 — 회귀 테스트)
# ============================================================================

class TestAudioClip:
    """AudioClip — P1 봉쇄 테스트."""

    def test_voice_beat_index_required(self):
        """voice clip에 beat_index=None → validate() error."""
        clip = AudioClip(track="voice", beat_index=None, url="http://example.com/voice.mp3")
        errs = clip.validate()
        assert any("beat_index" in e for e in errs), "beat_index 없음 감지 실패"

    def test_sfx_beat_index_required(self):
        """sfx clip에 beat_index=None → validate() error."""
        clip = AudioClip(track="sfx", beat_index=None, url="http://example.com/sfx.mp3")
        errs = clip.validate()
        assert any("beat_index" in e for e in errs), "beat_index 없음 감지 실패"

    def test_music_beat_index_optional(self):
        """music clip은 beat_index=None 허용(run-level)."""
        clip = AudioClip(track="music", beat_index=None, url="http://example.com/music.mp3")
        errs = clip.validate()
        assert not any("beat_index" in e for e in errs), "music의 beat_index는 옵션이어야 함"

    def test_url_or_storage_required(self):
        """url/storage_key 하나는 필수."""
        clip = AudioClip(track="voice", beat_index=0, url=None, storage_key=None)
        errs = clip.validate()
        assert any("url/storage_key" in e for e in errs), "url/storage_key 필수 감지 실패"

    def test_frozen_immutable(self):
        """frozen dataclass → 변형 불가."""
        clip = AudioClip(track="voice", beat_index=0, url="http://example.com/voice.mp3")
        with pytest.raises(FrozenInstanceError):
            clip.beat_index = 1  # type: ignore

    def test_from_dict_and_to_dict(self):
        """dict ↔ AudioClip roundtrip."""
        # slot row carries track/beat_index; the artifact row carries
        # url/storage_key/duration_ms (real DB model mapping).
        slot = {"track": "voice", "beat_index": 0}
        artifact = {"url": "http://example.com/voice.mp3", "duration_ms": 1000}
        clip = AudioClip.from_slot_artifact(slot, artifact)
        result = clip.to_dict()
        assert result["beat_index"] == 0
        assert result["track"] == "voice"
        assert result["url"] == "http://example.com/voice.mp3"


class TestBeatPlan:
    """BeatPlan — 대본 척추."""

    def test_beat_index_duplicate_detection(self):
        """beat_index 중복 → validate() error."""
        beats = [
            Beat(beat_index=0, text="Line 1"),
            Beat(beat_index=0, text="Line 2"),
        ]
        plan = BeatPlan(beats=tuple(beats), spine="Test spine")
        errs = plan.validate()
        assert any("중복" in e for e in errs), "beat_index 중복 감지 실패"

    def test_beat_index_continuity(self):
        """beat_index 연속성 깨짐 → validate() error."""
        beats = [
            Beat(beat_index=0, text="Line 1"),
            Beat(beat_index=2, text="Line 3"),  # 1 빠짐
        ]
        plan = BeatPlan(beats=tuple(beats), spine="Test spine")
        errs = plan.validate()
        assert any("연속" in e for e in errs), "beat_index 연속성 깨짐 감지 실패"

    def test_valid_beat_plan(self):
        """정상 BeatPlan → validate() OK."""
        beats = [
            Beat(beat_index=0, text="Line 1"),
            Beat(beat_index=1, text="Line 2"),
            Beat(beat_index=2, text="Line 3"),
        ]
        plan = BeatPlan(beats=tuple(beats), spine="Test spine")
        errs = plan.validate()
        assert not errs, f"정상 plan이 error: {errs}"


class TestMediaArtifact:
    """MediaArtifact — 비주얼."""

    def test_beat_index_required(self):
        """beat_index 필수."""
        artifact = MediaArtifact(kind="still", beat_index=None, url="http://example.com/img.jpg")
        errs = artifact.validate()
        assert any("beat_index" in e for e in errs), "beat_index 필수 감지 실패"

    def test_url_or_storage_required(self):
        """url/storage_key 하나는 필수."""
        artifact = MediaArtifact(kind="still", beat_index=0, url=None, storage_key=None)
        errs = artifact.validate()
        assert any("url/storage_key" in e for e in errs), "url/storage_key 필수 감지 실패"


class TestJanusBrief:
    """JanusBrief — 인테이크."""

    def test_style_validation(self):
        """style 허용값 검증."""
        brief = JanusBrief(brand_slug="test", style="invalid_style")
        errs = brief.validate()
        assert any("style" in e for e in errs), "style 검증 실패"

    def test_valid_brief(self):
        """정상 brief."""
        brief = JanusBrief(brand_slug="test_brand", style="photoreal")
        errs = brief.validate()
        assert not errs, f"정상 brief이 error: {errs}"


# ============================================================================
# Test: 신설 3종 계약
# ============================================================================

class TestKlingVideo:
    """KlingVideo — 여성 아바타 입술싱크."""

    def test_beat_index_required(self):
        """beat_index 필수."""
        video = KlingVideo(
            beat_index=None,  # type: ignore
            style="photoreal",
            script_line="Hello world",
            url="http://example.com/video.mp4",
        )
        errs = video.validate()
        assert any("beat_index" in e for e in errs), "beat_index 필수 감지 실패"

    def test_script_line_required(self):
        """script_line 필수(비어있으면 안 됨)."""
        video = KlingVideo(
            beat_index=0,
            style="photoreal",
            script_line="",  # 빈 문자열
            url="http://example.com/video.mp4",
        )
        errs = video.validate()
        assert any("script_line" in e for e in errs), "script_line 비어있음 감지 실패"

    def test_style_validation(self):
        """style 허용값만."""
        video = KlingVideo(
            beat_index=0,
            style="invalid",  # type: ignore
            script_line="Hello",
            url="http://example.com/video.mp4",
        )
        errs = video.validate()
        assert any("style" in e for e in errs), "style 검증 실패"

    def test_url_or_storage_required(self):
        """url/storage_key 하나는 필수."""
        video = KlingVideo(
            beat_index=0,
            style="photoreal",
            script_line="Hello",
            url=None,
            storage_key=None,
        )
        errs = video.validate()
        assert any("url/storage_key" in e for e in errs), "url/storage_key 필수 감지 실패"

    def test_lip_sync_confidence_range(self):
        """lip_sync_confidence 0-1 범위."""
        video = KlingVideo(
            beat_index=0,
            style="photoreal",
            script_line="Hello",
            url="http://example.com/video.mp4",
            lip_sync_confidence=1.5,  # 범위 초과
        )
        errs = video.validate()
        assert any("lip_sync_confidence" in e for e in errs), "lip_sync_confidence 범위 검증 실패"

    def test_valid_klingvideo(self):
        """정상 KlingVideo."""
        video = KlingVideo(
            beat_index=0,
            style="photoreal",
            script_line="Hello world",
            emotion="urgency",
            duration_ms=2000,
            url="http://example.com/video.mp4",
            lip_sync_confidence=0.95,
        )
        errs = video.validate()
        assert not errs, f"정상 KlingVideo이 error: {errs}"

    def test_frozen(self):
        """frozen dataclass."""
        video = KlingVideo(
            beat_index=0,
            style="photoreal",
            script_line="Hello",
            url="http://example.com/video.mp4",
        )
        with pytest.raises(FrozenInstanceError):
            video.beat_index = 1  # type: ignore

    def test_from_dict_and_to_dict(self):
        """dict ↔ KlingVideo roundtrip."""
        data = {
            "beat_index": 0,
            "style": "photoreal",
            "script_line": "Hello world",
            "emotion": "joy",
            "duration_ms": 1500,
            "url": "http://example.com/video.mp4",
            "lip_sync_confidence": 0.85,
        }
        video = KlingVideo.from_dict(data)
        result = video.to_dict()
        assert result["beat_index"] == 0
        assert result["script_line"] == "Hello world"
        assert result["lip_sync_confidence"] == 0.85


class TestHeroine:
    """Heroine — 여성 주연 캐스팅."""

    def test_female_protagonist_only(self):
        """여성만 Heroine 가능."""
        heroine = Heroine(
            brief_protagonist="남",
            visual_archetype="everywoman",
            voice_concept="female1",
            visual_style="photoreal",
            locale="ko",
        )
        errs = heroine.validate()
        assert any("non-female" in e for e in errs), "female only 제약 감지 실패"

    def test_valid_archetype(self):
        """archetype 허용값."""
        heroine = Heroine(
            brief_protagonist="여",
            visual_archetype="invalid",  # type: ignore
            voice_concept="female1",
            visual_style="photoreal",
            locale="ko",
        )
        errs = heroine.validate()
        assert any("archetype" in e for e in errs), "archetype 검증 실패"

    def test_valid_voice_concept(self):
        """voice_concept 허용값."""
        heroine = Heroine(
            brief_protagonist="여",
            visual_archetype="everywoman",
            voice_concept="invalid",  # type: ignore
            visual_style="photoreal",
            locale="ko",
        )
        errs = heroine.validate()
        assert any("voice_concept" in e for e in errs), "voice_concept 검증 실패"

    def test_valid_heroine(self):
        """정상 Heroine."""
        heroine = Heroine(
            brief_protagonist="여",
            visual_archetype="mentor",
            voice_concept="female2",
            visual_style="cute_illustration",
            locale="ko",
            age_range="30s",
            name="Park Min-hee",
        )
        errs = heroine.validate()
        assert not errs, f"정상 Heroine이 error: {errs}"

    def test_frozen(self):
        """frozen dataclass."""
        heroine = Heroine(
            brief_protagonist="여",
            visual_archetype="everywoman",
            voice_concept="female1",
            visual_style="photoreal",
            locale="ko",
        )
        with pytest.raises(FrozenInstanceError):
            heroine.visual_archetype = "witness"  # type: ignore

    def test_from_dict_and_to_dict(self):
        """dict ↔ Heroine roundtrip."""
        data = {
            "brief_protagonist": "여",
            "visual_archetype": "everywoman",
            "voice_concept": "female1",
            "visual_style": "photoreal",
            "locale": "ko",
            "age_range": "20s",
            "name": "Lee Ji-won",
        }
        heroine = Heroine.from_dict(data)
        result = heroine.to_dict()
        assert result["brief_protagonist"] == "여"
        assert result["visual_archetype"] == "everywoman"
        assert result["age_range"] == "20s"


class TestFeedbackSignal:
    """FeedbackSignal — 측정 루프 피드백."""

    def test_run_id_required(self):
        """run_id 필수."""
        signal = FeedbackSignal(
            run_id="",
            metric_date="2026-06-25",
            roas=1.5,
            ctr=0.02,
        )
        errs = signal.validate()
        assert any("run_id" in e for e in errs), "run_id 필수 감지 실패"

    def test_metric_date_format(self):
        """metric_date YYYY-MM-DD 형식."""
        signal = FeedbackSignal(
            run_id="run_001",
            metric_date="06-25-2026",  # 잘못된 형식
            roas=1.5,
            ctr=0.02,
        )
        errs = signal.validate()
        assert any("metric_date" in e for e in errs), "metric_date 형식 검증 실패"

    def test_roas_non_negative(self):
        """roas < 0 불가."""
        signal = FeedbackSignal(
            run_id="run_001",
            metric_date="2026-06-25",
            roas=-0.5,
            ctr=0.02,
        )
        errs = signal.validate()
        assert any("roas" in e for e in errs), "roas < 0 감지 실패"

    def test_ctr_range(self):
        """ctr 0-1 범위."""
        signal = FeedbackSignal(
            run_id="run_001",
            metric_date="2026-06-25",
            roas=1.5,
            ctr=1.5,  # 범위 초과
        )
        errs = signal.validate()
        assert any("ctr" in e for e in errs), "ctr 범위 검증 실패"

    def test_valid_signal(self):
        """정상 FeedbackSignal."""
        signal = FeedbackSignal(
            run_id="run_abc123",
            metric_date="2026-06-25",
            roas=2.3,
            ctr=0.045,
            learned_constraints={
                "hook_emotion": "urgency",
                "tone_preference": "direct",
            },
            spend_krw=50000.0,
            impressions=1000,
            conversions=45,
        )
        errs = signal.validate()
        assert not errs, f"정상 FeedbackSignal이 error: {errs}"

    def test_frozen(self):
        """frozen dataclass."""
        signal = FeedbackSignal(
            run_id="run_001",
            metric_date="2026-06-25",
            roas=1.5,
            ctr=0.02,
        )
        with pytest.raises(FrozenInstanceError):
            signal.roas = 2.0  # type: ignore

    def test_from_dict_and_to_dict(self):
        """dict ↔ FeedbackSignal roundtrip."""
        data = {
            "run_id": "run_xyz",
            "metric_date": "2026-06-24",
            "roas": 1.8,
            "ctr": 0.03,
            "learned_constraints": {"hook_emotion": "joy"},
            "spend_krw": 100000,
            "impressions": 2000,
            "conversions": 60,
        }
        signal = FeedbackSignal.from_dict(data)
        result = signal.to_dict()
        assert result["run_id"] == "run_xyz"
        assert result["roas"] == 1.8
        assert result["learned_constraints"]["hook_emotion"] == "joy"


# ============================================================================
# Test: 통합 시나리오 (E2E)
# ============================================================================

class TestIntegration:
    """통합 시나리오 — 행성간 계약 협력."""

    def test_end_to_end_flow(self):
        """E2E: Janus → Ares → Athena → ... → Metis."""
        # 1. Janus가 brief 생산
        brief = JanusBrief(
            brand_slug="viewok",
            intake=Intake13Q(
                identity="안경 렌즈 관리",
                audience="수영하는 사람들",
                proof="물안경 안 김",
            ),
            protagonist="여",
            style="photoreal",
        )
        assert not brief.validate(), "brief validation 실패"

        # 2. Ares가 BeatPlan 생산
        beats = [
            Beat(beat_index=0, text="Hook", voice_concept="female1", duration_ms=1000),
            Beat(beat_index=1, text="Body", voice_concept="female1", duration_ms=2000),
            Beat(beat_index=2, text="CTA", voice_concept="female1", duration_ms=1500, cta={"price": "₩26,820"}),
        ]
        plan = BeatPlan(beats=tuple(beats), spine="물안경 안 버려도 되는 권리")
        assert not plan.validate(), "plan validation 실패"

        # 3. Athena가 KlingVideo 생산
        videos = [
            KlingVideo(beat_index=0, style="photoreal", script_line="Hey, stop throwing them away", url="http://example.com/v0.mp4"),
            KlingVideo(beat_index=1, style="photoreal", script_line="This gel works", url="http://example.com/v1.mp4"),
            KlingVideo(beat_index=2, style="photoreal", script_line="Just ₩26,820", url="http://example.com/v2.mp4"),
        ]
        for v in videos:
            assert not v.validate(), f"video {v.beat_index} validation 실패"

        # 4. Orpheus가 AudioClip 생산
        voices = [
            AudioClip(track="voice", beat_index=0, url="http://example.com/v0.mp3"),
            AudioClip(track="voice", beat_index=1, url="http://example.com/v1.mp3"),
            AudioClip(track="voice", beat_index=2, url="http://example.com/v2.mp3"),
        ]
        for v in voices:
            assert not v.validate(), f"voice {v.beat_index} validation 실패"

        # 5. Metis가 FeedbackSignal 생산
        feedback = FeedbackSignal(
            run_id="run_viewok_001",
            metric_date="2026-06-25",
            roas=2.1,
            ctr=0.045,
            learned_constraints={"hook_emotion": "urgency"},
            spend_krw=50000,
            conversions=105,
        )
        assert not feedback.validate(), "feedback validation 실패"

        # 통합: 모든 계약이 협력하여 전체 흐름 형성
        assert len(videos) == len(beats), "비디오 개수 ≠ 비트 개수"
        assert len(voices) == len(beats), "음성 개수 ≠ 비트 개수"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
