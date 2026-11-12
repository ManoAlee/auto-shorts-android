"""YouTube 3-system & Shorts Explore/Exploit algorithmic readiness scorer.

Based strictly on documented YouTube Browse/Search/Shorts benchmarks:
- Shorts Swipe-Away (<60% fail, >=75% strong) & Completion Rate (>=70% promotion, >100% loop)
- 1-3s hook window, 3s visual cadence, <=40-char mobile title front-loading,
  3-5 hashtags, clean 9:16 loudness, and <=3 notifications/24h cadence cap.
"""

from typing import Dict, List, Optional

from .tiktok_algorithm import score_short_for_tiktok_algorithm


def score_short_for_youtube_algorithm(
    pack: Optional[Dict] = None,
    validation: Optional[Dict] = None,
    filename: str = "",
) -> Dict:
    """Compute algorithmic readiness score (0-100) and cascade tier for one Short."""
    p = pack or {}
    v = validation or p.get("validation") or {}
    title = str(p.get("title") or filename or "").strip()
    hook = str(p.get("hook_title") or "").strip()
    caption = str(p.get("caption") or "").strip()
    tags = list(p.get("hashtags") or [])

    tips: List[str] = []
    score = 0

    # 1. Hook & Viewed-vs-Swiped-Away readiness (30 pts)
    hook_pts = 0
    if hook and 2 <= len(hook.split()) <= 7 and len(hook) <= 42:
        hook_pts += 15
    else:
        tips.append("Encurte o banner do topo (hook) para 2 a 6 palavras (<= 42 chars) visiveis nos primeiros 1-3s.")
    if title and not title.lower().startswith("corte "):
        hook_pts += 15
    else:
        tips.append("Troque o titulo generico 'Corte ...' por um titulo curioso com a palavra-chave nos primeiros 40 caracteres.")
    score += hook_pts

    # 2. Retention, pacing & length sweet spot (30 pts)
    dur = float(v.get("duration") or 0.0)
    is_tiktok = "tiktok" in (str(p.get("platform") or "") + " " + str(p.get("output_path") or "") + " " + filename).lower()
    ret_pts = 0
    if 13.0 <= dur <= 22.0 or 34.0 <= dur <= 58.0 or (is_tiktok and 60.0 <= dur <= 130.0):
        ret_pts += 15
    elif 5.0 <= dur <= 60.0 or (is_tiktok and dur <= 180.0):
        ret_pts += 10
        tips.append("Duracao ideal no algoritmo Shorts: 15-20s (alta conclusao) ou 35-55s (retencao narrativa).")
    elif dur > 60.0:
        tips.append("Video acima de 60s sofre risco de bloqueio por Content ID em musica e menor conclusao.")

    cues = int(v.get("subtitle_cues") or 0)
    overlaps = int(v.get("subtitle_overlaps") or 0)
    if cues >= 4 and overlaps == 0:
        ret_pts += 15
    elif cues > 0 and overlaps == 0:
        ret_pts += 10
    else:
        tips.append("Adicione legendas dinamicas sem sobreposicao (mudanca visual a cada ~3s).")
    score += ret_pts

    # 3. Search & Shorts Feed Metadata (20 pts)
    seo_pts = 0
    if "#Shorts" in caption or "#Shorts" in tags or is_tiktok:
        seo_pts += 7
    else:
        tips.append("Inclua #Shorts na descricao.")
    if 3 <= len(tags) <= 5:
        seo_pts += 7
    else:
        seo_pts += 3
        tips.append("Use entre 3 e 5 hashtags segmentadas (evite excesso de tags).")
    if len(caption.strip()) >= 40:
        seo_pts += 6
    else:
        tips.append("Escreva contexto real nos primeiros 125 caracteres da descricao para YouTube Search.")
    score += seo_pts

    # 4. Technical satisfaction gate (20 pts)
    tech_pts = 0
    if v.get("valid"):
        tech_pts += 12
        mean_db = v.get("mean_volume_db")
        if isinstance(mean_db, (int, float)) and -26.0 <= mean_db <= -11.0:
            tech_pts += 8
        else:
            tech_pts += 4
            tips.append("Normalize o audio entre -22 dB e -14 dB para segurar atencao no feed.")
    else:
        tips.append("Execute a validacao automatica 9:16 + audio antes de postar.")
    score += tech_pts

    score = max(0, min(100, score))
    if score >= 82:
        tier = "Exploit / Escalavel (4 camadas)"
        viewed_forecast = "75%+ Viewed"
    elif score >= 60:
        tier = "Seed / Explore (teste de coorte)"
        viewed_forecast = "60-74% Viewed"
    else:
        tier = "Ajustar Hook antes de postar"
        viewed_forecast = "<60% (risco swipe-away)"

    return {
        "algo_score": score,
        "cascade_tier": tier,
        "viewed_forecast": viewed_forecast,
        "title_mobile_preview": title[:40] + ("..." if len(title) > 40 else ""),
        "tips": tips,
    }


def rank_feed_for_channel(videos: List[Dict]) -> List[Dict]:
    """Attach algorithmic scores and rank channel videos by readiness + recency."""
    enriched: List[Dict] = []
    for item in videos:
        pack = {
            "title": item.get("title", ""),
            "hook_title": item.get("hook_title", ""),
            "caption": item.get("caption", ""),
            "hashtags": item.get("hashtags", []),
        }
        algo = score_short_for_youtube_algorithm(
            pack=pack,
            validation=item.get("validation"),
            filename=item.get("filename", ""),
        )
        tt_algo = score_short_for_tiktok_algorithm(
            pack={**pack, "niche": item.get("niche", "geral"), "background_style": item.get("background_style", ""), "visual_audit": item.get("visual_audit")},
            validation=item.get("validation"),
            filename=item.get("filename", ""),
        )
        enriched.append({**item, "algorithm": algo, "tiktok_algo": tt_algo})
    enriched.sort(key=lambda x: (1 if x.get("youtube") else 0, x["algorithm"]["algo_score"]), reverse=True)
    return enriched

