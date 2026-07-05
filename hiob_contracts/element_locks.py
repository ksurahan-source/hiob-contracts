"""ElementLocks — 정체성 도면 락 계약 (D-56, Element Lock 제안 2026-07-04 E-1).

목적: 인물·복색·제품·배경 정체성을 텍스트 락에서 **이미지 참조 락(단일 히어로컷)**으로 승격.
릴 전편·전 런에서 얼굴·착장·제품·배경이 흔들리지 않게, 각 element의 '깨끗한 단일 히어로컷'을
비트 이미지 생성의 다중참조(3-ref edit)로 건다.

★ V2 원칙(참고 워크플로 실증): 멀티패널 마스터시트를 통째로 락에 걸면 정체성 전이가 흔들린다.
→ 마스터시트(sheet)는 사람 검토용, **락 소스는 각 대상의 단일 히어로컷(hero_cut) 1장.**

저장: `listing.attributes.element_locks`(기존 JSONB, 신규 테이블 0·리스팅 스코프·버전드).
status="approved"만 소비(draft는 byte-identical no-op). D-51: 원료 read-only, 구현=Athena·star·studio.

소비 시그니처(Athena 비트 edit):
    refs = locks.approved_refs(persona_id)   # [character, product, background] hero_cut 중 존재분
    prompt += locks.constraint_prompt(persona_id)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

LOCK_STATUSES = ("draft", "approved")
ELEMENT_KINDS = ("character", "product", "background")


def _s(v: Any) -> str:
    return str(v or "").strip()


@dataclass(frozen=True)
class ElementRef:
    """단일 히어로컷 참조(락 소스). storage_key=durable R2 키, url=서명/공개."""
    kind: str                                 # character | product | background
    storage_key: Optional[str] = None
    url: Optional[str] = None
    artifact_id: Optional[str] = None
    derived_from: Optional[str] = None        # 어느 마스터시트 버전에서 파생됐나 (정체성 일치 근거)

    def has_image(self) -> bool:
        return bool(self.storage_key or self.url)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.kind not in ELEMENT_KINDS:
            errs.append(f"ElementRef.kind 미지원: {self.kind}")
        return errs

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()}


@dataclass(frozen=True)
class CharacterLock:
    """인물 element. persona_id=named persona 결박. hero_cut=락 소스, sheet=검토용."""
    persona_id: str
    hero_cut: Optional[ElementRef] = None
    voice_persona: Optional[str] = None       # 기존 voice_face_lock과 이중 락
    sheet: dict = field(default_factory=dict)
    wardrobe: dict = field(default_factory=dict)   # {outfit, palette, forbidden[]}

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.persona_id:
            errs.append("CharacterLock.persona_id 없음")
        if self.hero_cut is not None:
            errs.extend(self.hero_cut.validate())
        return errs


@dataclass(frozen=True)
class ProductLock:
    """제품 element. 실물 히어로샷. constraints=AI 발명 금지·라벨 가독 명문."""
    hero_cut: Optional[ElementRef] = None
    sheet: dict = field(default_factory=dict)
    constraints: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        return self.hero_cut.validate() if self.hero_cut is not None else []


@dataclass(frozen=True)
class BackgroundLock:
    """배경 element. hero_cut(참조 이미지) + text_lock(기존 environment_lock, 이중 락)."""
    hero_cut: Optional[ElementRef] = None
    text_lock: str = ""
    sheet: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        return self.hero_cut.validate() if self.hero_cut is not None else []


@dataclass(frozen=True)
class ElementLocks:
    """리스팅 스코프 정체성 락 묶음. status='approved'만 소비."""
    version: int = 0
    status: str = "draft"                       # draft | approved
    authored_by: str = ""
    characters: dict = field(default_factory=dict)   # {persona_id: CharacterLock}
    product: Optional[ProductLock] = None
    background: Optional[BackgroundLock] = None
    version_history: tuple[dict, ...] = ()

    # ── 소비 API (Athena) ──────────────────────────────────────────────
    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    def character(self, persona_id: str) -> Optional[CharacterLock]:
        c = self.characters.get(persona_id)
        if c is None and self.characters:
            # 단일 히로인 폴백: persona_id 미스매치여도 유일 캐릭터 사용
            if len(self.characters) == 1:
                return next(iter(self.characters.values()))
        return c

    def approved_refs(self, persona_id: str = "") -> list[ElementRef]:
        """승인된 [character, product, background] 히어로컷(존재분만). 미승인=빈 리스트.

        3-ref edit 소스. 순서 = character(base 후보)·product·background.
        """
        if not self.is_approved:
            return []
        out: list[ElementRef] = []
        ch = self.character(persona_id)
        if ch and ch.hero_cut and ch.hero_cut.has_image():
            out.append(ch.hero_cut)
        if self.product and self.product.hero_cut and self.product.hero_cut.has_image():
            out.append(self.product.hero_cut)
        if self.background and self.background.hero_cut and self.background.hero_cut.has_image():
            out.append(self.background.hero_cut)
        return out

    def constraint_prompt(self, persona_id: str = "") -> str:
        """승인 락의 프롬프트 제약 블록(비주얼 edit 최후미 주입). 미승인=''."""
        if not self.is_approved:
            return ""
        parts: list[str] = []
        ch = self.character(persona_id)
        if ch:
            forb = [x for x in (ch.wardrobe.get("forbidden") or []) if _s(x)]
            outfit = _s(ch.wardrobe.get("outfit"))
            if outfit:
                parts.append(f"복색 락: {outfit} 착장을 유지.")
            if forb:
                parts.append("금지 착장: " + ", ".join(_s(x) for x in forb) + ".")
        if self.product:
            cons = [x for x in (self.product.constraints or ()) if _s(x)]
            if self.product.hero_cut and self.product.hero_cut.has_image():
                parts.append("제품 락: 참조 제품 이미지의 실물을 그대로 유지 — 형태·라벨·색을 발명하거나 변형하지 말 것.")
            if cons:
                parts.append("제품 제약: " + "; ".join(_s(x) for x in cons) + ".")
        if self.background:
            if self.background.hero_cut and self.background.hero_cut.has_image():
                parts.append("배경 락: 참조 배경 이미지의 장소·조명·톤과 일치시킬 것(경쟁사·타 브랜드 요소 금지).")
            elif _s(self.background.text_lock):
                parts.append(f"배경 락: {_s(self.background.text_lock)}")
        return (" " + " ".join(parts)) if parts else ""

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.status not in LOCK_STATUSES:
            errs.append(f"status 미지원: {self.status}")
        if not isinstance(self.version, int) or self.version < 0:
            errs.append(f"version 정수(>=0) 아님: {self.version!r}")
        for pid, c in (self.characters or {}).items():
            if isinstance(c, CharacterLock):
                errs.extend(c.validate())
        if self.product is not None:
            errs.extend(self.product.validate())
        if self.background is not None:
            errs.extend(self.background.validate())
        # 승인본은 최소 1개 element 히어로컷을 가져야 의미가 있다
        if self.is_approved and not (
            any(isinstance(c, CharacterLock) and c.hero_cut and c.hero_cut.has_image()
                for c in (self.characters or {}).values())
            or (self.product and self.product.hero_cut and self.product.hero_cut.has_image())
            or (self.background and self.background.hero_cut and self.background.hero_cut.has_image())
        ):
            errs.append("approved인데 히어로컷 이미지 0 (락 소스 부재)")
        return errs

    # ── 직렬화 ─────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ElementLocks":
        d = d or {}
        chars: dict = {}
        for pid, cd in (d.get("characters") or {}).items():
            cd = cd or {}
            chars[pid] = CharacterLock(
                persona_id=_s(pid),
                hero_cut=_ref_from(cd.get("hero_cut"), "character"),
                voice_persona=_s(cd.get("voice_persona")) or None,
                sheet=dict(cd.get("sheet") or {}),
                wardrobe=dict((cd.get("sheet") or {}).get("wardrobe") or cd.get("wardrobe") or {}),
            )
        prod = None
        if d.get("product"):
            pd = d["product"]
            prod = ProductLock(
                hero_cut=_ref_from(pd.get("hero_cut"), "product"),
                sheet=dict(pd.get("sheet") or {}),
                constraints=tuple(x for x in ((pd.get("sheet") or {}).get("constraints") or pd.get("constraints") or ()) if _s(x)),
            )
        bg = None
        if d.get("background"):
            bd = d["background"]
            bg = BackgroundLock(
                hero_cut=_ref_from(bd.get("hero_cut"), "background"),
                text_lock=_s(bd.get("text_lock")),
                sheet=dict(bd.get("sheet") or {}),
            )
        return cls(
            version=int(d.get("version") or 0),
            status=_s(d.get("status")) or "draft",
            authored_by=_s(d.get("authored_by")),
            characters=chars,
            product=prod,
            background=bg,
            version_history=tuple(d.get("version_history") or ()),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "status": self.status,
            "authored_by": self.authored_by,
            "characters": {
                pid: {
                    "hero_cut": c.hero_cut.to_dict() if c.hero_cut else None,
                    "voice_persona": c.voice_persona,
                    "sheet": c.sheet,
                    "wardrobe": c.wardrobe,
                }
                for pid, c in self.characters.items() if isinstance(c, CharacterLock)
            },
            "product": None if self.product is None else {
                "hero_cut": self.product.hero_cut.to_dict() if self.product.hero_cut else None,
                "sheet": self.product.sheet,
                "constraints": list(self.product.constraints),
            },
            "background": None if self.background is None else {
                "hero_cut": self.background.hero_cut.to_dict() if self.background.hero_cut else None,
                "text_lock": self.background.text_lock,
                "sheet": self.background.sheet,
            },
            "version_history": list(self.version_history),
        }


def _ref_from(d: Any, kind: str) -> Optional[ElementRef]:
    if not d:
        return None
    if isinstance(d, ElementRef):
        return d
    if not isinstance(d, dict):
        return None
    return ElementRef(
        kind=kind,
        storage_key=_s(d.get("storage_key")) or None,
        url=_s(d.get("url")) or None,
        artifact_id=_s(d.get("artifact_id")) or None,
        derived_from=_s(d.get("derived_from")) or None,
    )
