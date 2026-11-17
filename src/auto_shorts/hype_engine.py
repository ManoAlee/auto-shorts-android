"""Temporal Hype, Seasonality & Launch-Window Intelligence Engine.

Makes AutoShorts Studio aware of the current date, active mega-launches (e.g. GTA 6),
seasonal calendar windows (Black Friday, Anime Seasons, ENEM, IRPF), and live niche
priority so the autonomous pilot boosts what is peaking right now instead of blind round-robin.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_YT_CHIP_CACHE: Dict[str, object] = {"ts": 0.0, "chips": []}

_CHIP_TO_NICHE: Tuple[Tuple[str, str], ...] = (
    ("grand theft auto", "games_gta6"),
    ("gta", "games_gta6"),
    ("jogos", "games_gta6"),
    ("gaming", "games_gta6"),
    ("inteligência artificial", "ia_tech"),
    ("ia", "ia_tech"),
    ("gadgets", "ia_tech"),
    ("monetiza", "financas"),
    ("finan", "financas"),
    ("podcast", "podcast"),
    ("anime", "entretenimento_animes"),
    ("notícias", "noticias_mundiais"),
)


def fetch_youtube_br_home_chips(timeout: float = 4.5, ttl_sec: int = 1800) -> List[str]:
    """Extract live category chips from YouTube BR HTML (`ytInitialData`) without API v3 quota."""
    now = time.time()
    cached = _YT_CHIP_CACHE.get("chips")
    if isinstance(cached, list) and cached and (now - float(_YT_CHIP_CACHE.get("ts") or 0.0)) < ttl_sec:
        return list(cached)
    try:
        req = urllib.request.Request(
            "https://www.youtube.com/?hl=pt&gl=BR",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0 Safari/537.36"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_txt = resp.read().decode("utf-8", errors="ignore")
        chips = re.findall(r'"chipCloudChipRenderer":\{"text":\{"simpleText":"([^"]+)"\}', html_txt)
        clean_chips = [c for c in dict.fromkeys(chips) if c.lower() not in {"tudo", "ao vivo", "mixes"}][:16]
        if clean_chips:
            _YT_CHIP_CACHE["ts"] = now
            _YT_CHIP_CACHE["chips"] = clean_chips
        return clean_chips
    except Exception:
        return list(cached) if isinstance(cached, list) else []


def map_chips_to_niche_boosts(chips: List[str]) -> List[str]:
    """Map YouTube BR home chips into boosted AutoShorts niche keys."""
    boosted: List[str] = []
    for chip in chips:
        low = chip.lower()
        for kw, niche in _CHIP_TO_NICHE:
            if kw in low and niche not in boosted:
                boosted.append(niche)
    return boosted


@dataclass(frozen=True)
class HypeWindow:
    id: str
    label: str
    niche: str
    news_topic: Optional[str]
    start_mmdd: Tuple[int, int]
    end_mmdd: Tuple[int, int]
    weight: int  # 1 = normal, 2 = elevated, 3 = mega-hype
    year_filter: Optional[int] = None
    target_date: Optional[Tuple[int, int, int]] = None


# Active seasonal & mega-event windows
HYPE_WINDOWS: Tuple[HypeWindow, ...] = (
    HypeWindow(
        id="gta6_launch",
        label="GTA 6 Launch Hype (19/Nov)",
        niche="games_gta6",
        news_topic="games",
        start_mmdd=(11, 10),
        end_mmdd=(12, 5),
        weight=3,
        year_filter=2026,
        target_date=(2026, 11, 19),
    ),
    HypeWindow(
        id="black_friday_tech",
        label="Black Friday & Hardware Tech",
        niche="ia_tech",
        news_topic="tech",
        start_mmdd=(11, 15),
        end_mmdd=(11, 30),
        weight=2,
    ),
    HypeWindow(
        id="game_awards_hype",
        label="The Game Awards & Melhores do Ano",
        niche="games_gta6",
        news_topic="games",
        start_mmdd=(12, 1),
        end_mmdd=(12, 18),
        weight=2,
    ),
    HypeWindow(
        id="new_year_finance",
        label="Metas & Finanças de Ano Novo",
        niche="financas",
        news_topic="economia",
        start_mmdd=(12, 20),
        end_mmdd=(1, 20),
        weight=2,
    ),
    HypeWindow(
        id="irpf_brasil",
        label="Imposto de Renda & Economia BR",
        niche="financas",
        news_topic="economia",
        start_mmdd=(3, 1),
        end_mmdd=(5, 31),
        weight=2,
    ),
    HypeWindow(
        id="anime_spring_season",
        label="Temporada Animes Primavera",
        niche="entretenimento_animes",
        news_topic=None,
        start_mmdd=(4, 1),
        end_mmdd=(5, 15),
        weight=2,
    ),
    HypeWindow(
        id="anime_fall_season",
        label="Temporada Animes Outono",
        niche="entretenimento_animes",
        news_topic=None,
        start_mmdd=(10, 1),
        end_mmdd=(11, 12),
        weight=2,
    ),
    HypeWindow(
        id="enem_concursos",
        label="Reta Final ENEM & Concursos",
        niche="concursos",
        news_topic=None,
        start_mmdd=(10, 15),
        end_mmdd=(11, 15),
        weight=2,
    ),
)

BASE_ROTATION: Tuple[str, ...] = (
    "games_gta6",
    "noticias_mundiais",
    "entretenimento_animes",
    "ia_tech",
    "financas",
    "podcast",
    "desenvolvimento_pessoal",
    "saude_fitness",
)


def _in_mmdd_range(today: _dt.date, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
    cur = (today.month, today.day)
    if start <= end:
        return start <= cur <= end
    # Wraps year boundary (e.g. Dec 20 -> Jan 20)
    return cur >= start or cur <= end


def get_active_hype_windows(today: Optional[_dt.date] = None) -> List[HypeWindow]:
    """Return all seasonal/event hype windows active on `today`, sorted by weight desc."""
    ref = today or _dt.date.today()
    active: List[HypeWindow] = []
    for w in HYPE_WINDOWS:
        if w.year_filter is not None and ref.year != w.year_filter:
            continue
        if _in_mmdd_range(ref, w.start_mmdd, w.end_mmdd):
            active.append(w)
    active.sort(key=lambda w: w.weight, reverse=True)
    return active


def build_weighted_rotation(today: Optional[_dt.date] = None) -> List[str]:
    """Build an interleaved niche rotation weighted by active temporal hype windows."""
    active = get_active_hype_windows(today)
    if not active:
        return list(BASE_ROTATION)

    top = active[0]
    # Interleave the top hype niche every 2nd slot for weight>=3, or every 3rd slot for weight==2
    stride = 2 if top.weight >= 3 else 3
    weighted: List[str] = []
    for idx, niche in enumerate(BASE_ROTATION):
        if idx % stride == 0:
            weighted.append(top.niche)
        if niche != top.niche or idx % stride != 0:
            weighted.append(niche)
    return weighted


def pick_hype_aware_niche(
    runs_completed: int,
    requested_niche: str = "all",
    today: Optional[_dt.date] = None,
) -> Tuple[str, Optional[str], str]:
    """Pick `(active_niche, preferred_news_topic, hype_summary)` for the current cycle."""
    active = get_active_hype_windows(today)
    top = active[0] if active else None
    summary = ""
    if top:
        if top.target_date:
            t_dt = _dt.date(*top.target_date)
            ref = today or _dt.date.today()
            delta = (t_dt - ref).days
            if delta > 0:
                summary = f"{top.label} (faltam {delta}d)"
            elif delta == 0:
                summary = f"{top.label} (LANÇAMENTO HOJE!)"
            else:
                summary = f"{top.label} (pós-lançamento +{abs(delta)}d)"
        else:
            summary = top.label

    if requested_niche and requested_niche != "all":
        topic = top.news_topic if (top and top.niche == requested_niche) else None
        return requested_niche, topic, summary

    rotation = build_weighted_rotation(today)
    picked = rotation[int(runs_completed) % len(rotation)]
    # Alternate games_gta6 between video clipping (even cycles) and breaking games news (odd cycles)
    news_topic = None
    if picked == "games_gta6" and int(runs_completed) % 2 == 1:
        news_topic = "games"
    elif picked == "noticias_mundiais" and top and top.news_topic and int(runs_completed) % 2 == 0:
        news_topic = top.news_topic
    return picked, news_topic, summary


def get_hype_status_payload(today: Optional[_dt.date] = None) -> Dict:
    """Return structured hype telemetry for /api/status and Copiloto IA."""
    active = get_active_hype_windows(today)
    _, _, summary = pick_hype_aware_niche(0, "all", today=today)
    chips = fetch_youtube_br_home_chips()
    return {
        "active_hype": summary or "Rotação equilibrada",
        "windows": [
            {"id": w.id, "label": w.label, "niche": w.niche, "weight": w.weight}
            for w in active
        ],
        "youtube_br_chips": chips[:10],
        "boosted_niches": map_chips_to_niche_boosts(chips),
        "rotation_preview": build_weighted_rotation(today)[:6],
    }


def get_live_trend_cards(today: Optional[_dt.date] = None) -> Dict:
    """Build live hype cards strictly from real YouTube BR chips + live RSS feeds (zero hardcoded cards)."""
    ref = today or _dt.date.today()
    chips = fetch_youtube_br_home_chips()
    status = get_hype_status_payload(ref)

    cards: List[Dict[str, str]] = []
    seen_titles: set[str] = set()
    try:
        from .world_news import fetch_world_news_headlines
        for topic_key in ("games", "tech", "world"):
            if len(cards) >= 4:
                break
            for h in fetch_world_news_headlines(topic=topic_key, limit=4):
                title = str(h.get("title") or "").strip()
                norm = title.lower()
                if not title or norm in seen_titles:
                    continue
                seen_titles.add(norm)
                cards.append({
                    "topic": topic_key,
                    "title": title[:78],
                    "desc": f"{h.get('source', 'Radar Ao Vivo')} • Capturado em tempo real.",
                    "niche": topic_key,
                })
                if len(cards) >= 4:
                    break
    except Exception:
        pass

    return {
        "ok": True,
        "active_hype": status["active_hype"],
        "youtube_br_chips": chips[:12],
        "cards": cards[:4],
    }
