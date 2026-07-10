"""ParzifalMasterSheet — Higgsfield식 멀티앵글 마스터시트 DB 계약 (D-Parzifal, 2026-07-06).

Parzifal = element lock의 행성 승격. 현 단일 히어로컷(ElementLocks.hero_cut 1장)을 넘어,
등장인물을 **멀티앵글(front/3-4/side/back/full-body/detail) × 표정 매트릭스 × 복장**으로 락하는
'새로운 형태의 등장인물 설명 DB'. 제품은 front/3-4/back/detail/pour, 배경은 참조+텍스트 락.

founder 결정(D-58):
- AI 아바타 전용(PIPA §17 회피). crazy narrow target(Janus NarrowPersona)이 캐릭터 IDENTITY로
  내장 — 기존 Ares '인물묘사 탭' 역할의 승화(Ares 코드 무변경).
- 데이터흐름 Janus→Parzifal. Athena 등 전 행성이 무조건 이 계약을 참조.

소비 호환: Athena 기존 소비자(ElementLocks.approved_refs/constraint_prompt)를 깨지 않도록
approved_refs()/constraint_prompt()를 동형 제공 + to_element_locks() 브릿지. status='approved'만 소비.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .element_locks import ElementLocks, ElementRef, CharacterLock, ProductLock, BackgroundLock

# 마스터시트 앵글·표정 표준 어휘(Higgsfield 시트 형식).
CHARACTER_ANGLES = ("front", "3-4", "side", "back", "full-body", "detail")
PRODUCT_ANGLES = ("front", "3-4", "back", "detail", "pour")
EXPRESSIONS = ("neutral", "happy", "surprised", "focused", "smile")
SHEET_STATUSES = ("draft", "approved")


@dataclass(frozen=True)
class SheetPanel:
    """마스터시트 한 패널 = 한 앵글/표정/복장의 이미지 참조. hero_cut의 멀티 확장."""

    slot: str                                  # angle | expression | wardrobe | detail
    label: str                                 # front | 3-4 | ... | neutral | happy ...
    storage_key: Optional[str] = None          # durable R2 키(락 소스)
    url: Optional[str] = None
    engine: str = ""                            # 다모델 라우팅 결과(qwen-image/gpt-image/...)
    derived_from: str = ""

    @property
    def has_image(self) -> bool:
        return bool(self.storage_key or self.url)

    def to_ref(self, kind: str) -> ElementRef:
        """ElementLocks 소비 호환용 ElementRef 변환(브릿지)."""
        return ElementRef(kind=kind, storage_key=self.storage_key, url=self.url,
                          derived_from=self.derived_from or f"parzifal:{self.slot}:{self.label}")

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.slot not in ("angle", "expression", "wardrobe", "detail"):
            errs.append(f"SheetPanel.slot 미지원: {self.slot}")
        if not self.label:
            errs.append("SheetPanel.label 없음")
        return errs


def _panels(raw) -> list[SheetPanel]:
    out: list[SheetPanel] = []
    for p in raw or []:
        if isinstance(p, SheetPanel):
            out.append(p)
        elif isinstance(p, dict):
            out.append(SheetPanel(
                slot=str(p.get("slot") or "angle"), label=str(p.get("label") or ""),
                storage_key=p.get("storage_key"), url=p.get("url"),
                engine=str(p.get("engine") or ""), derived_from=str(p.get("derived_from") or "")))
    return out


@dataclass(frozen=True)
class CharacterMasterSheet:
    """등장인물 마스터시트 — Ares 인물묘사 승화 + crazy narrow target 내장(아바타 전용)."""

    persona_id: str
    identity: dict = field(default_factory=dict)      # name, age, gender, region, background
    narrow_target: dict = field(default_factory=dict) # Janus NarrowPersona 설정(crazy narrow)
    angles: list = field(default_factory=list)        # SheetPanel[] (front/3-4/side/back/full/detail)
    expressions: list = field(default_factory=list)   # SheetPanel[] (neutral/happy/...)
    wardrobe: dict = field(default_factory=dict)      # {outfit, palette, forbidden[]}

    def hero_panel(self) -> Optional[SheetPanel]:
        """대표 컷 = front 앵글 우선, 없으면 첫 앵글."""
        panels = _panels(self.angles)
        for p in panels:
            if p.label == "front" and p.has_image:
                return p
        for p in panels:
            if p.has_image:
                return p
        return None

    def approved_panels(self) -> list[SheetPanel]:
        return [p for p in (_panels(self.angles) + _panels(self.expressions)) if p.has_image]

    def to_character_lock(self) -> CharacterLock:
        """ElementLocks 소비 호환(브릿지). hero_cut=front 컷·sheet=identity·wardrobe 승계."""
        hero = self.hero_panel()
        return CharacterLock(
            persona_id=self.persona_id,
            hero_cut=hero.to_ref("character") if hero else None,
            sheet={**self.identity, "narrow_target": self.narrow_target},
            wardrobe=dict(self.wardrobe or {}))

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.persona_id:
            errs.append("CharacterMasterSheet.persona_id 없음")
        for p in _panels(self.angles) + _panels(self.expressions):
            errs.extend(p.validate())
        return errs

    def to_dict(self) -> dict:
        """JSON 직렬화 — TargetSheet.to_dict()가 visual 층으로 호출하는 계약
        (2026-07-11 실사고: 이 메서드 부재로 생산 경로의 4층 SSOT persist가
        AttributeError → fail-soft에 삼켜져 전량 조용히 실패했다)."""
        def _pl(panels):
            return [{"slot": p.slot, "label": p.label, "storage_key": p.storage_key,
                     "url": p.url, "engine": p.engine, "derived_from": p.derived_from}
                    for p in _panels(panels)]
        return {"persona_id": self.persona_id, "identity": dict(self.identity or {}),
                "narrow_target": dict(self.narrow_target or {}),
                "angles": _pl(self.angles), "expressions": _pl(self.expressions),
                "wardrobe": dict(self.wardrobe or {})}

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "CharacterMasterSheet":
        """to_dict 역방향 — TargetSheet.from_dict()가 visual 층으로 호출하는 계약."""
        d = d or {}
        return cls(persona_id=str(d.get("persona_id") or ""),
                   identity=d.get("identity") or {},
                   narrow_target=d.get("narrow_target") or {},
                   angles=_panels(d.get("angles")),
                   expressions=_panels(d.get("expressions")),
                   wardrobe=d.get("wardrobe") or {})


@dataclass(frozen=True)
class ProductMasterSheet:
    """제품 마스터시트 — front/3-4/back/detail/pour 다각도 락(실제 제품·AI 금지 캐논)."""

    sku: str = ""
    angles: list = field(default_factory=list)        # SheetPanel[]
    sheet: dict = field(default_factory=dict)

    def hero_panel(self) -> Optional[SheetPanel]:
        for p in _panels(self.angles):
            if p.has_image:
                return p
        return None

    def to_product_lock(self) -> ProductLock:
        hero = self.hero_panel()
        return ProductLock(hero_cut=hero.to_ref("product") if hero else None, sheet=dict(self.sheet or {}))


@dataclass(frozen=True)
class ParzifalMasterSheet:
    """리스팅 스코프 마스터시트 DB 엔트리. status='approved'만 소비(draft=byte-identical no-op)."""

    listing_slug: str = ""
    master_id: str = ""
    version: int = 0
    status: str = "draft"                             # draft | approved
    authored_by: str = ""
    engine: str = ""                                  # 다모델 라우팅 결과
    characters: dict = field(default_factory=dict)    # {persona_id: CharacterMasterSheet}
    product: Optional[ProductMasterSheet] = None
    background: dict = field(default_factory=dict)    # {ref: SheetPanel, text_lock: str}
    version_history: list = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    def character(self, persona_id: str) -> Optional[CharacterMasterSheet]:
        c = self.characters.get(persona_id) if persona_id else None
        if c is None and len(self.characters) == 1:       # 단일 히로인 폴백(element_locks 계약과 동일)
            c = next(iter(self.characters.values()))
        return c if isinstance(c, CharacterMasterSheet) else None

    def approved_refs(self, persona_id: str = "") -> list[ElementRef]:
        """Athena 소비 호환 — 승인 마스터시트의 [character hero, product hero, background] refs.

        ElementLocks.approved_refs와 동형(하류 무변경). draft/미승인=[] (byte-identical).
        """
        if not self.is_approved:
            return []
        refs: list[ElementRef] = []
        ch = self.character(persona_id)
        if ch is not None:
            hero = ch.hero_panel()
            if hero:
                refs.append(hero.to_ref("character"))
        if self.product is not None:
            ph = self.product.hero_panel()
            if ph:
                refs.append(ph.to_ref("product"))
        bg = self.background.get("ref") if isinstance(self.background, dict) else None
        if isinstance(bg, SheetPanel) and bg.has_image:
            refs.append(bg.to_ref("background"))
        elif isinstance(bg, dict) and (bg.get("storage_key") or bg.get("url")):
            refs.append(ElementRef(kind="background", storage_key=bg.get("storage_key"), url=bg.get("url")))
        return refs

    def constraint_prompt(self, persona_id: str = "") -> str:
        """Athena 소비 호환 — 복장 유지·금지·narrow 설정을 프롬프트 말미 가드로. 미승인=''."""
        if not self.is_approved:
            return ""
        ch = self.character(persona_id)
        if ch is None:
            return ""
        bits: list[str] = []
        wr = ch.wardrobe or {}
        if wr.get("outfit"):
            bits.append(f"복장 유지: {wr['outfit']}")
        forb = wr.get("forbidden") or []
        if forb:
            bits.append(f"금지: {', '.join(str(f) for f in forb)}")
        nt = ch.narrow_target or {}
        act = nt.get("activity_context")
        if act:
            bits.append(f"활동맥락: {act}")
        return (" · ".join(bits) + " · 락된 마스터시트 정체성 유지.") if bits else ""

    def to_element_locks(self) -> ElementLocks:
        """ElementLocks 브릿지 — 기존 Athena/visual.py 소비자가 그대로 먹게(하위호환)."""
        chars = {pid: c.to_character_lock() for pid, c in self.characters.items()
                 if isinstance(c, CharacterMasterSheet)}
        bg = None
        if isinstance(self.background, dict):
            ref = self.background.get("ref")
            hero = ref.to_ref("background") if isinstance(ref, SheetPanel) else None
            bg = BackgroundLock(hero_cut=hero, text_lock=str(self.background.get("text_lock") or ""))
        return ElementLocks(
            status=self.status, authored_by=self.authored_by, characters=chars,
            product=self.product.to_product_lock() if self.product is not None else None,
            background=bg)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.status not in SHEET_STATUSES:
            errs.append(f"status 미지원: {self.status}")
        for c in self.characters.values():
            if isinstance(c, CharacterMasterSheet):
                errs.extend(c.validate())
        if self.is_approved and not any(
            isinstance(c, CharacterMasterSheet) and c.hero_panel() is not None
            for c in self.characters.values()):
            errs.append("approved인데 승인된 캐릭터 hero 패널 없음")
        return errs

    def to_dict(self) -> dict:
        def _pl(panels):
            return [{"slot": p.slot, "label": p.label, "storage_key": p.storage_key,
                     "url": p.url, "engine": p.engine, "derived_from": p.derived_from}
                    for p in _panels(panels)]
        return {
            "listing_slug": self.listing_slug, "master_id": self.master_id,
            "version": self.version, "status": self.status, "authored_by": self.authored_by,
            "engine": self.engine,
            "characters": {pid: {"persona_id": c.persona_id, "identity": c.identity,
                                 "narrow_target": c.narrow_target, "angles": _pl(c.angles),
                                 "expressions": _pl(c.expressions), "wardrobe": c.wardrobe}
                           for pid, c in self.characters.items() if isinstance(c, CharacterMasterSheet)},
            "product": ({"sku": self.product.sku, "angles": _pl(self.product.angles),
                         "sheet": self.product.sheet} if self.product is not None else None),
            "background": _bg_to_dict(self.background),
            "version_history": list(self.version_history or []),
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ParzifalMasterSheet":
        d = d or {}
        chars = {}
        for pid, c in (d.get("characters") or {}).items():
            c = c or {}
            chars[str(pid)] = CharacterMasterSheet(
                persona_id=str(c.get("persona_id") or pid), identity=c.get("identity") or {},
                narrow_target=c.get("narrow_target") or {}, angles=_panels(c.get("angles")),
                expressions=_panels(c.get("expressions")), wardrobe=c.get("wardrobe") or {})
        prod = None
        if isinstance(d.get("product"), dict):
            pr = d["product"]
            prod = ProductMasterSheet(sku=str(pr.get("sku") or ""), angles=_panels(pr.get("angles")),
                                      sheet=pr.get("sheet") or {})
        return cls(
            listing_slug=str(d.get("listing_slug") or ""), master_id=str(d.get("master_id") or ""),
            version=int(d.get("version") or 0), status=str(d.get("status") or "draft"),
            authored_by=str(d.get("authored_by") or ""), engine=str(d.get("engine") or ""),
            characters=chars, product=prod, background=_bg_from_dict(d.get("background")),
            version_history=list(d.get("version_history") or []))


def _bg_to_dict(bg) -> dict:
    if not isinstance(bg, dict):
        return {}
    ref = bg.get("ref")
    out = {"text_lock": bg.get("text_lock", "")}
    if isinstance(ref, SheetPanel):
        out["ref"] = {"slot": ref.slot, "label": ref.label, "storage_key": ref.storage_key, "url": ref.url}
    elif isinstance(ref, dict):
        out["ref"] = ref
    return out


def _bg_from_dict(bg) -> dict:
    if not isinstance(bg, dict):
        return {}
    ref = bg.get("ref")
    out = {"text_lock": str(bg.get("text_lock") or "")}
    if isinstance(ref, dict):
        out["ref"] = SheetPanel(slot=str(ref.get("slot") or "detail"), label=str(ref.get("label") or "bg"),
                                storage_key=ref.get("storage_key"), url=ref.get("url"))
    return out
