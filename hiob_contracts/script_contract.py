"""ARES-SCRIPT-V3 — 편들기 대본 계약 (2026-07-02).

master_sales_script(dict)의 V3 확장 필드 스키마. 현 파이프는 dict 기반이므로 이
dataclass들은 (1) 스키마의 단일 진실 기록(SCHEMA-FIRST LAW) (2) 점진적 채택용
파서/검증 헬퍼 역할을 한다. 프롬프트 정본: hiob-deploy/apps/modal/prompts/
master_sales_script_candidate.txt · 검증기: hiob_star.orchestration._v3_contract_flags.

원칙 (founder 2026-07-02):
- 단 하나의 아픈 글: 여러 VoC 합성 금지 — 실제 글 ONE을 편든다. 소수의 팬 전략.
- 업계 문법: 매크로 단위는 5부(훅-문제-해결-증거-CTA), 훅=성과 분산 60-80%.
- 날조 금지 · 실명/신상 특정 금지 · 공포 과장 금지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# story_function 어휘 (비트 서사 기능) — 5부 구조의 세분화.
STORY_FUNCTIONS = (
    "훅", "배경", "사건", "인과", "전환", "처방", "증거", "신뢰", "변신", "CTA",
)

# n_beats >= 9(스토리텔링 45-60초)일 때의 최소 서사 예산.
STORY_BUDGET_MIN = {"훅": 1, "배경": 2, "사건": 1, "인과": 1, "증거": 1, "CTA": 1}

TRAUMA_GRADES = ("A", "B", "C")  # A=타겟 전용 기억+관계 · B=감각 장면 · C=범용 경고


@dataclass
class AnchorVocPost:
    """단 하나의 아픈 글 — 릴 전체가 편드는 실제 VoC 원문."""

    quote: str = ""            # 원문 발췌 (있는 그대로 — 창작 금지)
    source: str = ""           # 출처 표기 (제공된 것만)
    why: str = ""              # 왜 이 글이 가장 아픈가

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AnchorVocPost":
        d = d or {}
        return cls(quote=str(d.get("quote") or ""), source=str(d.get("source") or ""), why=str(d.get("why") or ""))

    @property
    def is_grounded(self) -> bool:
        return bool(self.quote.strip())


@dataclass
class TargetGrounding:
    """타겟 실체화 — 앵커 글쓴이의 상황(신상 특정 금지, 상황만)."""

    who: str = ""              # 어디 사는 어떤 사람 (무명 실루엣)
    where: str = ""            # 구체 장소·시간
    moment: str = ""           # 무슨 일이 벌어지던 순간
    failure: str = ""          # 고통의 기반이 된 큰 실패 장면
    why: str = ""              # 왜 이런 일이 일어났는지 (인과)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "TargetGrounding":
        d = d or {}
        return cls(**{k: str(d.get(k) or "") for k in ("who", "where", "moment", "failure", "why")})

    def missing_fields(self) -> list[str]:
        return [k for k in ("who", "where", "moment", "failure", "why") if not getattr(self, k).strip()]


@dataclass
class HookLogic:
    """첫 장면 후킹 논리 — 만든 사람이 움찔해야 A."""

    stop_reason: str = ""      # 왜 스크롤이 멈추나
    pain_mirror: str = ""      # 타겟이 "내 얘기"라고 느끼는 지점
    trauma_grade: str = ""     # "A|B|C — 근거"

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "HookLogic":
        d = d or {}
        return cls(stop_reason=str(d.get("stop_reason") or ""), pain_mirror=str(d.get("pain_mirror") or ""), trauma_grade=str(d.get("trauma_grade") or ""))

    @property
    def grade(self) -> str:
        g = self.trauma_grade.strip().upper()
        return g[0] if g and g[0] in TRAUMA_GRADES else ""


@dataclass
class BeatDirection:
    """연출컷 — 아트디렉터·편집자가 이것만 보고 같은 장면을 만들 수 있게."""

    setting: str = ""          # 장소·시간대
    shot: str = ""             # 구도·카메라
    subject: str = ""          # 인물·표정·행동 (또는 무인물 피사체)
    overlay: str = ""          # 화면 텍스트

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "BeatDirection":
        d = d or {}
        return cls(**{k: str(d.get(k) or "") for k in ("setting", "shot", "subject", "overlay")})


@dataclass
class TrustSlots:
    """신뢰 비트 필수 슬롯 — 13Q identity/history/proof에서만."""

    brand_why: str = ""        # 왜 이 제품을 만들었나
    b2b_proof: str = ""        # 납품처·인증 등 신뢰 근거

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "TrustSlots":
        d = d or {}
        return cls(brand_why=str(d.get("brand_why") or ""), b2b_proof=str(d.get("b2b_proof") or ""))


def story_function_counts(beat_personas: Optional[list]) -> dict[str, int]:
    """beat_personas[].story_function 분포 집계 (검증기·표면 공용)."""
    counts: dict[str, int] = {}
    for bp in beat_personas or []:
        fn = str((bp or {}).get("story_function") or "").strip()
        if fn:
            counts[fn] = counts.get(fn, 0) + 1
    return counts
