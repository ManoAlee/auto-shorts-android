"""Live Anime & Manga multi-horizon radar via AniList GraphQL and Jikan v4 (zero API key)."""

import concurrent.futures
import datetime as _dt
import json
import time
import urllib.request
from typing import Dict, List, Optional

_ANIME_CACHE: Dict[tuple, tuple[float, List[Dict]]] = {}


ANILIST_URL = "https://graphql.anilist.co"
JIKAN_SEASON_URL = "https://api.jikan.moe/v4/seasons/now?limit=12"
JIKAN_UPCOMING_URL = "https://api.jikan.moe/v4/seasons/upcoming?limit=12"
JIKAN_TOP_URL = "https://api.jikan.moe/v4/top/anime?filter=bypopularity&limit=12"

ANIME_CATEGORIES = {
    "all": "Todos os Animes (Teorias & Radar)",
    "em_exibicao": "Em Exibicao (Semana)",
    "famosos_ano": "Mais Famosos do Ano",
    "mais_curtidos": "Mais Curtidos da Temporada",
    "proximos": "Estreias Este Ano & Proximo Ano",
}

_ANILIST_FLEX_QUERY = """
query ($perPage: Int, $status: MediaStatus, $season: MediaSeason, $seasonYear: Int, $sort: [MediaSort]) {
  Page(perPage: $perPage) {
    media(type: ANIME, status: $status, season: $season, seasonYear: $seasonYear, sort: $sort, isAdult: false) {
      id
      title { romaji english }
      popularity
      trending
      favourites
      averageScore
      episodes
      season
      seasonYear
      status
      genres
      coverImage {
        large
      }
      nextAiringEpisode {
        episode
        timeUntilAiring
      }
    }
  }
}
"""


def _current_year_and_season() -> tuple[int, str]:
    now = _dt.datetime.now()
    m = now.month
    if m in (1, 2, 3):
        season = "WINTER"
    elif m in (4, 5, 6):
        season = "SPRING"
    elif m in (7, 8, 9):
        season = "SUMMER"
    else:
        season = "FALL"
    return now.year, season


def _format_search_query(
    title: str,
    next_ep: Optional[int],
    category: str = "em_exibicao",
    season_year: Optional[int] = None,
) -> str:
    clean = " ".join(title.split()[:6])
    if category == "proximos":
        yr = f" {season_year}" if season_year else ""
        return f"{clean}{yr} trailer teoria spoilers estreia anime brasil"
    if category in {"famosos_ano", "mais_curtidos"}:
        return f"{clean} maiores teorias segredos explicacao final anime brasil"
    if next_ep and next_ep > 1:
        return f"{clean} episodio {next_ep - 1} analise teoria brasil"
    return f"{clean} anime teoria analise segredos brasil"


def _parse_anilist_items(items: List[Dict], category: str, cat_label: str) -> List[Dict]:
    results: List[Dict] = []
    for m in items:
        titles = m.get("title") or {}
        name = str(titles.get("english") or titles.get("romaji") or "").strip()
        if not name:
            continue
        nxt = m.get("nextAiringEpisode") or {}
        next_ep = nxt.get("episode")
        secs = nxt.get("timeUntilAiring")
        s_year = m.get("seasonYear")
        results.append({
            "source": "anilist",
            "id": m.get("id"),
            "title": name,
            "romaji": titles.get("romaji") or name,
            "popularity": int(m.get("popularity") or 0),
            "trending": int(m.get("trending") or 0),
            "favourites": int(m.get("favourites") or 0),
            "score": int(m.get("averageScore") or 0),
            "episodes": m.get("episodes"),
            "season": m.get("season") or "",
            "season_year": s_year,
            "status": m.get("status") or "",
            "anime_category": category,
            "anime_category_label": cat_label,
            "next_episode": next_ep,
            "hours_until_next": round(secs / 3600.0, 1) if isinstance(secs, (int, float)) else None,
            "genres": m.get("genres") or [],
            "image_url": (m.get("coverImage") or {}).get("large") or "",
            "youtube_query": _format_search_query(name, next_ep, category=category, season_year=s_year),
            "teoria_foco": True,
        })
    return results


def _query_anilist(variables: Dict, category: str, cat_label: str, timeout: int = 12) -> List[Dict]:
    clean_vars = {k: v for k, v in variables.items() if v is not None}
    payload = json.dumps({"query": _ANILIST_FLEX_QUERY, "variables": clean_vars}).encode("utf-8")
    req = urllib.request.Request(
        ANILIST_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AutoShortsMobile/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw = data.get("data", {}).get("Page", {}).get("media", []) or []
    return _parse_anilist_items(raw, category=category, cat_label=cat_label)


def fetch_anilist_trending(limit: int = 8, timeout: int = 12) -> List[Dict]:
    """Query AniList GraphQL for currently releasing trending anime (no auth required)."""
    items = _query_anilist(
        {"perPage": max(1, limit), "status": "RELEASING", "sort": ["TRENDING_DESC", "POPULARITY_DESC"]},
        category="em_exibicao",
        cat_label="Em Exibicao",
        timeout=timeout,
    )
    items.sort(key=lambda x: (x["trending"], x["popularity"]), reverse=True)
    return items


def fetch_anilist_famous_year(limit: int = 8, timeout: int = 12) -> List[Dict]:
    """Query AniList GraphQL for the most famous/popular anime of the current year."""
    yr, _ = _current_year_and_season()
    items = _query_anilist(
        {"perPage": max(1, limit), "seasonYear": yr, "sort": ["POPULARITY_DESC", "TRENDING_DESC"]},
        category="famosos_ano",
        cat_label=f"Mais Famoso {yr}",
        timeout=timeout,
    )
    items.sort(key=lambda x: (x["popularity"], x["score"]), reverse=True)
    return items


def fetch_anilist_top_liked_season(limit: int = 8, timeout: int = 12) -> List[Dict]:
    """Query AniList GraphQL for top-scored / most favourited anime of the current season."""
    yr, season = _current_year_and_season()
    items = _query_anilist(
        {"perPage": max(1, limit), "season": season, "seasonYear": yr, "sort": ["SCORE_DESC", "FAVOURITES_DESC"]},
        category="mais_curtidos",
        cat_label=f"Mais Curtido {season.title()} {yr}",
        timeout=timeout,
    )
    items.sort(key=lambda x: (x["score"], x["favourites"], x["popularity"]), reverse=True)
    return items


def fetch_anilist_upcoming_releases(limit: int = 10, timeout: int = 12) -> List[Dict]:
    """Query AniList GraphQL for anticipated releases of this year & next year."""
    yr, _ = _current_year_and_season()
    items = _query_anilist(
        {"perPage": max(1, limit + 4), "status": "NOT_YET_RELEASED", "sort": ["POPULARITY_DESC", "TRENDING_DESC"]},
        category="proximos",
        cat_label=f"Estreia {yr}/{yr + 1}",
        timeout=timeout,
    )
    filtered = [
        it for it in items
        if not it.get("season_year") or int(it["season_year"]) in (yr, yr + 1)
    ]
    out = filtered or items
    for it in out:
        if it.get("season_year"):
            it["anime_category_label"] = f"Estreia {it['season_year']}"
    out.sort(key=lambda x: (x["popularity"], x["favourites"]), reverse=True)
    return out[:limit]


def _fetch_jikan_endpoint(url: str, category: str, cat_label: str, limit: int = 8, timeout: int = 12) -> List[Dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "AutoShortsMobile/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    out: List[Dict] = []
    for item in (data.get("data") or [])[:limit]:
        name = str(item.get("title_english") or item.get("title") or "").strip()
        if not name:
            continue
        yr = item.get("year")
        out.append({
            "source": "jikan",
            "id": item.get("mal_id"),
            "title": name,
            "romaji": item.get("title") or name,
            "popularity": int(item.get("members") or 0),
            "trending": int(item.get("favorites") or 0),
            "favourites": int(item.get("favorites") or 0),
            "score": int(round(float(item.get("score") or 0) * 10)),
            "episodes": item.get("episodes"),
            "season": str(item.get("season") or "").upper(),
            "season_year": yr,
            "status": item.get("status") or "",
            "anime_category": category,
            "anime_category_label": cat_label,
            "next_episode": None,
            "hours_until_next": None,
            "genres": [g.get("name") for g in (item.get("genres") or []) if g.get("name")],
            "image_url": ((item.get("images") or {}).get("jpg") or {}).get("large_image_url") or "",
            "youtube_query": _format_search_query(name, None, category=category, season_year=yr),
            "teoria_foco": True,
        })
    return out


def fetch_jikan_seasonal(limit: int = 8, timeout: int = 12) -> List[Dict]:
    """Fallback to Jikan v4 (MyAnimeList) current seasonal anime."""
    return _fetch_jikan_endpoint(JIKAN_SEASON_URL, "em_exibicao", "Temporada Atual", limit=limit, timeout=timeout)


def get_releasing_anime_radar(limit: int = 24, category: str = "all") -> List[Dict]:
    """Fetch balanced multi-category anime radar concurrently with fast fallback & cache."""
    cat = (category or "all").strip().lower()
    use_cache = (getattr(urllib.request.urlopen, "__name__", "") == "urlopen")
    cache_k = (cat, int(limit))
    if use_cache:
        hit = _ANIME_CACHE.get(cache_k)
        if hit and (time.time() - hit[0]) < 240:
            return hit[1]

    per_bucket = max(4, min(10, (limit // 3) + 2)) if cat == "all" else max(8, limit)
    bucket_plan = {
        "em_exibicao": (
            [lambda: fetch_anilist_trending(limit=per_bucket, timeout=7)],
            [lambda: fetch_jikan_seasonal(limit=per_bucket, timeout=7)],
        ),
        "famosos_ano": (
            [lambda: fetch_anilist_famous_year(limit=per_bucket, timeout=7)],
            [lambda: _fetch_jikan_endpoint(JIKAN_TOP_URL, "famosos_ano", "Mais Famosos", limit=per_bucket, timeout=7)],
        ),
        "mais_curtidos": (
            [lambda: fetch_anilist_top_liked_season(limit=per_bucket, timeout=7)],
            [lambda: _fetch_jikan_endpoint(JIKAN_SEASON_URL, "mais_curtidos", "Mais Curtido", limit=per_bucket, timeout=7)],
        ),
        "proximos": (
            [lambda: fetch_anilist_upcoming_releases(limit=per_bucket, timeout=7)],
            [lambda: _fetch_jikan_endpoint(JIKAN_UPCOMING_URL, "proximos", "Proximas Estreias", limit=per_bucket, timeout=7)],
        ),
    }

    if cat in bucket_plan:
        primary_fns, fallback_fns = bucket_plan[cat]
    else:
        primary_fns = [
            lambda: fetch_anilist_trending(limit=per_bucket, timeout=7),
            lambda: fetch_anilist_top_liked_season(limit=per_bucket, timeout=7),
            lambda: fetch_anilist_famous_year(limit=per_bucket, timeout=7),
            lambda: fetch_anilist_upcoming_releases(limit=per_bucket, timeout=7),
        ]
        fallback_fns = [
            lambda: fetch_jikan_seasonal(limit=per_bucket, timeout=7),
            lambda: _fetch_jikan_endpoint(JIKAN_UPCOMING_URL, "proximos", "Proximas Estreias", limit=per_bucket, timeout=7),
        ]

    buckets: List[List[Dict]] = []
    if len(primary_fns) == 1:
        try:
            res = primary_fns[0]()
            if res:
                buckets.append(res)
        except Exception:
            pass
    else:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(primary_fns))
        try:
            futs = [pool.submit(fn) for fn in primary_fns]
            concurrent.futures.wait(futs, timeout=7.5)
            for f in futs:
                if f.done():
                    try:
                        res = f.result()
                        if res:
                            buckets.append(res)
                    except Exception:
                        continue
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    merged: List[Dict] = []
    seen = set()

    def _absorb(lists: List[List[Dict]]) -> None:
        max_len = max((len(b) for b in lists), default=0)
        for idx in range(max_len):
            for b in lists:
                if idx >= len(b):
                    continue
                item = b[idx]
                key = str(item.get("title") or "").strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    merged.append(item)
                    if len(merged) >= limit:
                        return

    _absorb(buckets)
    if len(merged) < min(limit, 8):
        fb_buckets: List[List[Dict]] = []
        for fn in fallback_fns:
            try:
                res = fn()
                if res:
                    fb_buckets.append(res)
            except Exception:
                continue
        _absorb(fb_buckets)

    out = merged[:limit]
    if use_cache and out:
        _ANIME_CACHE[cache_k] = (time.time(), out)
    return out
