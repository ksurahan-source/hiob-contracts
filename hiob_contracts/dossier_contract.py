"""CreativeDossier 계약 (founder 2026-07-03 — "하나의 MECE 기획서 → 행성별 명령").

Janus 4소스(13Q·상세페이지 VL텍스트·네이버 insane-search·판매페이지)를 교차 대조해
Ares에 먹이는 단일 피딩 문서. 원칙:
  * 전 필드 패스스루 — 소비자가 모르는 키도 버리지 않는다 (V3 무음 드롭 교훈).
  * 증거는 소스 불리언 4칸을 반드시 갖는다 — "몇 곳에서 확인됐나"가 신뢰도의 전부.
  * 모순 플래그 = 13Q에는 있는데 상세페이지·네이버 어디에도 없는 주장 (날조 위험).
"""
from __future__ import annotations

from typing import Any

SOURCE_KEYS = ("intake", "detail_page", "naver", "sales_page")

EVIDENCE_ROLES = (
    "review",        # 후기/별점 (소셜프루프)
    "usage",         # 사용법/시연
    "before_after",  # 비포애프터
    "spec",          # 스펙/성분/인증
    "price",         # 가격/구성
    "usp",           # 핵심 주장
)


def normalize_evidence_item(raw: dict[str, Any]) -> dict[str, Any]:
    """LLM 산출 증거 1건을 계약 형태로 강제 (미지 키는 보존)."""
    if not isinstance(raw, dict):
        return {}
    sources = raw.get("sources") if isinstance(raw.get("sources"), dict) else {}
    norm_sources = {k: bool(sources.get(k)) for k in SOURCE_KEYS}
    confirmed = sum(1 for v in norm_sources.values() if v)
    item = {
        **raw,  # 패스스루 먼저 — 아래 정규화 키가 덮는다
        "claim": str(raw.get("claim") or "").strip()[:300],
        "role": str(raw.get("role") or "usp").strip()[:24],
        "sources": norm_sources,
        "confirmed_count": confirmed,
        # 모순: 인테이크 주장인데 상세·네이버 어디서도 확인 안 됨 = 릴에 싣기 전 사람 확인 필수
        "contradiction": bool(norm_sources["intake"] and not norm_sources["detail_page"] and not norm_sources["naver"]),
        "source_refs": [str(r)[:300] for r in (raw.get("source_refs") or []) if r][:6],
        "asset_key": str(raw.get("asset_key") or "") or None,
    }
    return item


def normalize_dossier(raw: dict[str, Any]) -> dict[str, Any]:
    """CreativeDossier 전체 정규화 — evidence 강제 + tone/corpus 보존."""
    if not isinstance(raw, dict):
        raw = {}
    evidence = [normalize_evidence_item(e) for e in (raw.get("evidence") or []) if isinstance(e, dict)]
    evidence = [e for e in evidence if e.get("claim")]
    tone = raw.get("tone") if isinstance(raw.get("tone"), dict) else {}
    return {
        **raw,
        "version": 1,
        "evidence": evidence,
        "tone": {
            "voice": str(tone.get("voice") or "").strip()[:200],
            "basis": str(tone.get("basis") or "").strip()[:300],
            **{k: v for k, v in tone.items() if k not in ("voice", "basis")},
        },
        "corpus": raw.get("corpus") if isinstance(raw.get("corpus"), dict) else {},
        "contradiction_count": sum(1 for e in evidence if e.get("contradiction")),
    }


def dossier_brief_block(dossier: dict[str, Any]) -> str:
    """upstream.brief 승계용 압축 블록 — 대본/아트/사운드 프롬프트가 그대로 읽는다."""
    if not isinstance(dossier, dict) or not dossier.get("evidence"):
        return ""
    lines = ["[검증된 사회적 증거 — 4소스 교차 확인, 이 목록 밖의 수치·주장 날조 금지]"]
    for e in dossier["evidence"][:8]:
        srcs = e.get("sources") or {}
        tags = "".join(("✓" if srcs.get(k) else "·") for k in SOURCE_KEYS)
        flag = " ⚠️모순(사람확인 전 사용금지)" if e.get("contradiction") else ""
        lines.append(f"- [{e.get('role')}] {e.get('claim')} (13Q상세네이버판매={tags}){flag}")
    voice = (dossier.get("tone") or {}).get("voice")
    if voice:
        lines.append(f"[확정 톤앤매너] {voice}")
    return "\n".join(lines)
