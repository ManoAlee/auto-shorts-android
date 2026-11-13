"""Cross-Platform Algorithm Analytics & Global Trend Radar (YouTube, TikTok, Instagram).

Aggregates local vault telemetry (.publish.json) with live multi-source global trends
(Google Trends BR/US, X/Twitter viral signals, Reddit, Hacker News) and computes
actionable algorithm playbooks per platform.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

PLATFORM_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "tiktok": {
        "name": "TikTok",
        "primary_signals": [
            "Taxa de conclusao (100%+) e Rewatch nos primeiros 3s",
            "Comentarios + Salvamentos (Favoritos) + Compartilhamentos",
            "SEO na legenda (palavras-chave de busca + 3-5 hashtags de nicho)",
        ],
        "optimal_duration_s": "25-55s",
        "avoid": [
            "Links externos (youtube.com / youtu.be) na legenda",
            "Hashtags de plataformas concorrentes (#reels, #shorts)",
            "Textos longos acima de 300 chars que cobrem o video",
        ],
        "cta_template": "Comenta sua opiniao e salva pra ver depois!",
    },
    "youtube": {
        "name": "YouTube Shorts",
        "primary_signals": [
            "Viewed vs Swiped Away (>75% Viewed)",
            "Retencao media >95% (loop limpo sem pausa no final)",
            "Titulo SEO <=95 chars + #Shorts + Playlist por nicho",
        ],
        "optimal_duration_s": "30-58s",
        "avoid": [
            "Duracao >= 60.5s (sai do feed de Shorts)",
            "Mais de 5 hashtags (dilui classificacao do nicho)",
            "Clickbait desconexo do audio nos primeiros 5s",
        ],
        "cta_template": "Se inscreva para os proximos cortes!",
    },
    "instagram": {
        "name": "Instagram Reels",
        "primary_signals": [
            "Envios por DM (Sends per Reach) — sinal #1 de viralizacao",
            "Watch time medio + Salvamentos",
            "Capa 9:16 limpa + organizacao em Destaques por nicho",
        ],
        "optimal_duration_s": "25-55s",
        "avoid": [
            "Marca d'agua de outros apps (TikTok/CapCut)",
            "Legenda sem CTA de compartilhamento por DM",
            "Thumbnail duplicada (hash SHA-256 repetido)",
        ],
        "cta_template": "Manda pra um amigo que precisa ver isso!",
    },
}


def build_cross_platform_analytics(out_dir: Path) -> Dict[str, Any]:
    """Compute vault performance, niche distribution, and per-platform recommendations."""
    packs: List[Dict[str, Any]] = []
    for mp4 in sorted(out_dir.glob("*.mp4")):
        p = mp4.with_suffix(".publish.json")
        if not p.is_file():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, dict):
            d["_file"] = mp4.name
            d["_size_mb"] = round(mp4.stat().st_size / 1048576, 2)
            packs.append(d)

    total = len(packs)
    niches: Dict[str, int] = {}
    q_scores: List[float] = []
    algo_scores: List[float] = []
    durations: List[float] = []

    tt_pub = yt_pub = ig_pub = approved_cnt = 0
    pending_all_3: List[str] = []

    for d in packs:
        niche = str(d.get("niche") or "geral")
        niches[niche] = niches.get(niche, 0) + 1
        va = d.get("visual_audit") or {}
        if va.get("approved"):
            approved_cnt += 1
        if isinstance(va.get("quality_score"), (int, float)):
            q_scores.append(float(va["quality_score"]))
        alg = d.get("algorithm") or {}
        if isinstance(alg.get("algo_score"), (int, float)):
            algo_scores.append(float(alg["algo_score"]))
        val = d.get("validation") or {}
        if isinstance(val.get("duration"), (int, float)):
            durations.append(float(val["duration"]))

        has_tt = bool((d.get("tiktok") or {}).get("publish_id"))
        has_yt = bool((d.get("youtube") or {}).get("video_id"))
        has_ig = bool((d.get("instagram") or {}).get("media_pk"))
        tt_pub += int(has_tt)
        yt_pub += int(has_yt)
        ig_pub += int(has_ig)
        if va.get("approved") and not (has_tt and has_yt and has_ig):
            pending_all_3.append(str(d["_file"]))

    avg_q = round(sum(q_scores) / len(q_scores), 1) if q_scores else 0.0
    avg_algo = round(sum(algo_scores) / len(algo_scores), 1) if algo_scores else 0.0
    avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0

    recommendations: List[str] = []
    if total - tt_pub > 0:
        recommendations.append(f"Publicar {total - tt_pub} videos pendentes no TikTok via tiktok.publish_batch (sessao CDP aquecida).")
    if total - yt_pub > 0:
        recommendations.append(f"Publicar {total - yt_pub} Shorts pendentes no YouTube Studio via youtube.publish_batch (sem cota de API).")
    if total - ig_pub > 0:
        recommendations.append(f"Publicar {total - ig_pub} Reels pendentes no Instagram com CTA de envio por DM.")
    if niches and max(niches.values()) > max(3, int(total * 0.7)):
        top_n = max(niches, key=lambda k: niches[k])
        recommendations.append(f"Diversificar nichos: '{top_n}' concentra {niches[top_n]}/{total} videos; misturar noticias_mundiais e ia_tech.")

    return {
        "generated_at": int(time.time()),
        "summary": {
            "total_packs": total,
            "approved_packs": approved_cnt,
            "avg_quality_score": avg_q,
            "avg_algo_score": avg_algo,
            "avg_duration_s": avg_dur,
            "pending_cross_platform": len(pending_all_3),
        },
        "platforms": {
            "tiktok": {
                **PLATFORM_PLAYBOOKS["tiktok"],
                "published": tt_pub,
                "pending": max(0, total - tt_pub),
                "mode": os.getenv("TIKTOK_PUBLISH_MODE", "cdp") or "cdp",
            },
            "youtube": {
                **PLATFORM_PLAYBOOKS["youtube"],
                "published": yt_pub,
                "pending": max(0, total - yt_pub),
                "mode": os.getenv("YOUTUBE_PUBLISH_MODE", "cdp") or "cdp",
            },
            "instagram": {
                **PLATFORM_PLAYBOOKS["instagram"],
                "published": ig_pub,
                "pending": max(0, total - ig_pub),
                "mode": "graph_api_or_instagrapi",
            },
        },
        "niches": dict(sorted(niches.items(), key=lambda kv: kv[1], reverse=True)),
        "pending_sample": pending_all_3[:12],
        "recommendations": recommendations,
    }


def _fetch_text(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutoShortsTrendBot/1.0)",
            "Accept": "application/json, application/xml, text/xml, text/html",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _classify_niche(title: str) -> str:
    low = title.lower()
    if any(k in low for k in ("anime", "manga", "goku", "naruto", "one piece", "solo leveling", "demon slayer", "netflix", "filme", "jogo")):
        return "entretenimento_animes"
    if any(k in low for k in ("ia ", "ai ", "openai", "gpt", "gemini", "claude", "apple", "samsung", "galaxy", "microsoft", "tech", "chip", "nvidia")):
        return "ia_tech"
    if any(k in low for k in ("dolar", "bitcoin", "btc", "bolsa", "selic", "pix", "banco", "economia", "inflacao")):
        return "financas"
    return "noticias_mundiais"


def fetch_global_trends_radar(niche: str = "all", timeout: float = 5.0) -> Dict[str, Any]:
    """Query global trend sources (Google Trends BR/US, X/Twitter viral feeds, Reddit, HN)."""
    items: List[Dict[str, Any]] = []
    sources_ok: List[str] = []
    sources_err: List[str] = []

    rss_feeds = [
        ("google_trends_br", "https://trends.google.com/trending/rss?geo=BR"),
        ("google_trends_us", "https://trends.google.com/trending/rss?geo=US"),
        ("x_twitter_viral_br", "https://news.google.com/rss/search?q=viral+twitter+OR+x.com+brasil&hl=pt-BR&gl=BR&ceid=BR:pt-419"),
        ("x_twitter_world", "https://news.google.com/rss/search?q=trending+on+X+OR+viral+world&hl=en-US&gl=US&ceid=US:en"),
    ]
    for src_name, url in rss_feeds:
        try:
            xml_txt = _fetch_text(url, timeout=timeout)
            root = ET.fromstring(xml_txt)
            count = 0
            for it in root.findall(".//item")[:8]:
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                if not title:
                    continue
                detected_niche = _classify_niche(title)
                items.append({
                    "source": src_name,
                    "title": title,
                    "url": link,
                    "niche": detected_niche,
                    "hook_idea": f"Voce viu o que acabou de acontecer? {title[:75]}",
                })
                count += 1
            if count:
                sources_ok.append(src_name)
        except Exception as exc:
            sources_err.append(f"{src_name}:{type(exc).__name__}")

    # Reddit WorldNews / Technology / Anime hot JSON
    reddit_subs = [("reddit_worldnews", "worldnews"), ("reddit_technology", "technology"), ("reddit_anime", "anime")]
    for src_name, sub in reddit_subs:
        try:
            raw = _fetch_text(f"https://www.reddit.com/r/{sub}/hot.json?limit=5", timeout=timeout)
            data = json.loads(raw)
            children = ((data.get("data") or {}).get("children")) or []
            for ch in children:
                pd = ch.get("data") or {}
                title = str(pd.get("title") or "").strip()
                if not title or pd.get("stickied"):
                    continue
                items.append({
                    "source": src_name,
                    "title": title,
                    "url": f"https://reddit.com{pd.get('permalink', '')}",
                    "score": int(pd.get("score") or 0),
                    "niche": "entretenimento_animes" if sub == "anime" else _classify_niche(title),
                    "hook_idea": f"Isso esta explodindo agora: {title[:75]}",
                })
            sources_ok.append(src_name)
        except Exception as exc:
            sources_err.append(f"{src_name}:{type(exc).__name__}")

    # Hacker News top 5 for ia_tech
    try:
        ids = json.loads(_fetch_text("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=timeout))[:5]
        for hid in ids:
            st = json.loads(_fetch_text(f"https://hacker-news.firebaseio.com/v0/item/{hid}.json", timeout=timeout))
            title = str(st.get("title") or "").strip()
            if title:
                items.append({
                    "source": "hacker_news",
                    "title": title,
                    "url": str(st.get("url") or f"https://news.ycombinator.com/item?id={hid}"),
                    "score": int(st.get("score") or 0),
                    "niche": "ia_tech",
                    "hook_idea": f"Nova tendencia tech global: {title[:75]}",
                })
        sources_ok.append("hacker_news")
    except Exception as exc:
        sources_err.append(f"hacker_news:{type(exc).__name__}")

    # Deduplicate and filter by requested niche
    seen = set()
    filtered: List[Dict[str, Any]] = []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:48]
        if key in seen:
            continue
        seen.add(key)
        if niche not in ("", "all") and it["niche"] != niche:
            continue
        filtered.append(it)

    return {
        "fetched_at": int(time.time()),
        "niche_filter": niche,
        "total_trends": len(filtered),
        "sources_ok": sources_ok,
        "sources_err": sources_err,
        "trends": filtered[:30],
    }

