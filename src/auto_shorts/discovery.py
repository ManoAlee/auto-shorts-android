"""Automatic real-video discovery via yt-dlp without requiring a YouTube account."""

import json
import os
import subprocess
from typing import Any, Callable, Dict, List, Optional, Set

from .anime_trends import get_releasing_anime_radar


NICHE_SEARCH_QUERIES: Dict[str, List[str]] = {
    "financas": [
        "podcast financas investimentos brasil",
        "como sair das dividas investir brasil",
    ],
    "ia_tech": [
        "inteligencia artificial ferramentas podcast brasil",
        "automacao ia tecnologia brasil",
    ],
    "entretenimento_animes": [
        "anime dublado cena epica brasil",
        "jujutsu kaisen dublado melhores momentos brasil",
        "dragon ball z dublado cena marcante brasil",
        "naruto shippuden dublado luta epica brasil",
        "demon slayer dublado cena brasil",
        "one piece dublado cena epica brasil",
        "solo leveling dublado cena brasil",
        "bleach dublado cena epica brasil",
    ],
    "desenvolvimento_pessoal": [
        "habitos disciplina podcast brasil",
        "psicologia mentalidade podcast brasil",
    ],
    "saude_fitness": [
        "nutricao hipertrofia podcast brasil",
        "emagrecimento metabolismo medico brasil",
    ],
    "concursos": [
        "como estudar concurso publico podcast brasil",
        "dicas aprovacao concurso brasil",
    ],
    "games": [
        "alanzoka gta 6 live completa brasil",
        "alanzoka melhores momentos live jogos brasil",
        "gta 6 gameplay react live brasil",
        "gaules davyjones live gameplay cortes brasil",
    ],
    "humor_memes": [
        "alanzoka momentos engracados live brasil",
        "casimiro react memes engracado live brasil",
        "diogo defante melhores momentos live brasil",
        "compilado memes engracado stream brasil",
    ],
    "podcast": [
        "corte podcast entrevista viral brasil",
        "flow podpah inteligencia ltda corte",
    ],
    "geral": [
        "podcast historia curiosidade brasil",
        "corte podcast viral brasil",
    ],
}


def parse_discovery_lines(
    ndjson_text: str,
    seen_ids: Optional[Set[str]] = None,
    min_duration: float = 180.0,
    max_duration: float = 28800.0,
    registry: Optional[Any] = None,
) -> List[Dict]:
    """Filter raw yt-dlp --flat-playlist --dump-json output for clip-worthy real videos."""
    seen = seen_ids or set()
    candidates: List[Dict] = []

    for line in ndjson_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid = str(item.get("id") or "").strip()
        url = str(item.get("webpage_url") or item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not vid or not url or vid in seen:
            continue
        if registry:
            if registry.is_duplicate_video_id(vid) or registry.is_duplicate_url(url):
                continue
            is_dup_title, _ = registry.is_duplicate_headline(title)
            if is_dup_title:
                continue
        if item.get("live_status") in {"is_live", "is_upcoming"} or item.get("is_live"):
            continue

        try:
            duration = float(item.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration < min_duration or (max_duration > 0 and duration > max_duration):
            continue

        try:
            views = int(item.get("view_count") or 0)
        except (TypeError, ValueError):
            views = 0

        candidates.append({
            "id": vid,
            "url": url,
            "title": str(item.get("title") or "").strip(),
            "channel": str(item.get("channel") or item.get("uploader") or "").strip(),
            "duration": duration,
            "view_count": views,
        })

    candidates.sort(key=lambda c: c["view_count"], reverse=True)
    return candidates


def discover_videos(
    niche: str = "geral",
    query: Optional[str] = None,
    source_url: Optional[str] = None,
    limit: int = 8,
    seen_ids: Optional[Set[str]] = None,
    cookies_path: Optional[str] = None,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> List[Dict]:
    """Discover real public YouTube videos (no login required by default)."""
    target = source_url
    if not target:
        q = query
        if not q and niche == "entretenimento_animes" and os.getenv("ANIME_TRENDS_RADAR", "1") != "0":
            radar = get_releasing_anime_radar(limit=5)
            if radar:
                q = radar[0]["youtube_query"]
        if not q:
            import random
            pool = NICHE_SEARCH_QUERIES.get(niche, NICHE_SEARCH_QUERIES["geral"])
            q = random.choice(pool)
        target = f"ytsearch{max(1, limit)}:{q}"

    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings"]
    resolved_cookies = cookies_path or os.getenv("YTDLP_COOKIES", "").strip()
    if resolved_cookies:
        cmd.extend(["--cookies", resolved_cookies])
    cmd.append(target)

    exec_fn = runner or subprocess.run
    proc = exec_fn(cmd, capture_output=True, text=True, check=True)
    return parse_discovery_lines(proc.stdout or "", seen_ids=seen_ids)

