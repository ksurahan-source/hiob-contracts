"""DecisionContext / DecisionCallable — 사람↔Fable5 대칭 결정 표면 (Goal D, 2026-07-06).

founder Goal D: "이 모든 행성체계를 관통하는 Fable5를 어떻게 사람 대신 일하게 할 것인가
(ares→artemis로 대변되는, 사람도 AI도 할 수 있는 일들)."

한 창작 결정(대본 감정·비주얼 도면·편집 컷/컬러)을 **사람 UI 레버**와 **Fable5 헤드리스 레버**가
동일 계약 표면으로 통과하게 하는 것이 목표. 각 행성(Ares/Athena/Artemis)이 아래 시그니처의
순수 함수를 노출하면:

    def decide(ctx: DecisionContext, llm: DecisionCallable | None) -> dict

- llm=None → 결정론적 휴리스틱 폴백(byte-identical·비용 0). 사람이 UI에서 정한 값과 동치.
- llm=Fable5 콜러블 → AI가 같은 자리에서 결정(D-56 승인 예외, ~$0.10/리스팅).

Athena `build_element_locks_draft(llm_callable=)`가 이미 이 패턴의 정본(씨앗). 이 계약은 그
패턴을 3행성 공통 타입으로 승격 — 좀비(인터페이스만·소비자 미배선) 방지 위해 소비측이 실제로
`ctx`를 받아 폴백까지 돌도록 최소 API를 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Fable5(또는 어떤 LLM) 주입 시그니처 — prompt(str) → completion(str). 순수 텍스트 계약이라
# 행성이 anthropic/openai 어느 클라이언트에도 결박되지 않는다(god-file/좌초 방지).
DecisionCallable = Callable[[str], str]


@dataclass(frozen=True)
class DecisionContext:
    """한 창작 결정에 필요한 최소 입력 — 사람 에디터가 화면에서 보는 것과 동일 맥락.

    beat_index<0 = 릴 전역 결정(예: 캐릭터 도면). upstream=상류 행성 산출(Ares→Athena→Artemis).
    persona=결박된 인물(persona_id·gender·image 등). brief=리스팅/제품 맥락(request_interpretation
    포함 가능). 전부 평면 dict로 받아 계약 간 순환 import를 피한다.
    """

    stage: str                                  # ares | athena | artemis | <planet>
    decision: str                               # emotion | visual_blueprint | cut_timing | color_grade ...
    beat_index: int = -1                        # -1 = 릴 전역
    brief: dict = field(default_factory=dict)
    upstream: dict = field(default_factory=dict)
    persona: dict = field(default_factory=dict)

    ALLOWED_STAGES = ("ares", "athena", "artemis", "orpheus", "apollo", "atropos", "star")

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.stage:
            errs.append("stage 필수")
        if not self.decision:
            errs.append("decision 필수")
        for k in ("brief", "upstream", "persona"):
            if not isinstance(getattr(self, k), dict):
                errs.append(f"{k}는 dict여야 함")
        return errs

    @property
    def is_reel_global(self) -> bool:
        return self.beat_index < 0

    def to_prompt_context(self) -> str:
        """llm 콜러블에 넘길 맥락 텍스트(사람이 UI에서 읽는 것과 등가). 순수·결정론적."""
        parts = [f"[결정] stage={self.stage} decision={self.decision}"]
        if not self.is_reel_global:
            parts.append(f"beat_index={self.beat_index}")
        pid = self.persona.get("persona_id") or self.persona.get("id")
        if pid:
            parts.append(f"persona={pid}")
        tpn = (self.brief.get("request_interpretation") or {}).get("target_persona_narrow") \
            if isinstance(self.brief.get("request_interpretation"), dict) else None
        if tpn:
            parts.append(f"세부타겟={tpn}")
        return " · ".join(str(p) for p in parts)


def resolve_decision(
    ctx: DecisionContext,
    llm: Optional[DecisionCallable],
    heuristic: Callable[[DecisionContext], Any],
    *,
    parse: Optional[Callable[[str], Any]] = None,
) -> Any:
    """대칭 결정 실행기 — 소비측 행성이 재사용하는 최소 API(좀비 방지·실제 배선 강제).

    llm=None → heuristic(ctx)(사람 값과 동치·byte-identical). llm 주입 → prompt 조립→호출→
    parse(응답). llm 실패/파싱 실패는 heuristic로 fail-soft 폴백(파이프라인 무영향). 순수·주입식.
    """
    if llm is None:
        return heuristic(ctx)
    try:
        raw = llm(ctx.to_prompt_context())
        if parse is not None:
            return parse(raw)
        return raw if raw else heuristic(ctx)
    except Exception:
        return heuristic(ctx)
