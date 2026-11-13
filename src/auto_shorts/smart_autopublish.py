"""Intelligent Multi-Channel Auto-Publisher (Coordinated Cadence, Niche Rotation & Pre-Flight SEO Healing)."""

import datetime as _dt
import json
import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .publisher import optimize_existing_publish_pack, publish_pack_to_instagram_reels, publish_pack_to_tiktok, publish_pack_to_youtube
from .re_engine import score_short_opus_runbook
from .retention import prune_storage
from .tiktok_algorithm import score_short_for_tiktok_algorithm
from .validator import audit_short_end_to_end
from .yt_algorithm import score_short_for_youtube_algorithm


CHANNELS = ("tiktok", "youtube", "instagram")
DEFAULT_DAILY_CAPS = {
    "tiktok": int(os.getenv("TIKTOK_DAILY_CAP", "6") or "6"),
    "youtube": int(os.getenv("YT_DAILY_CAP", "5") or "5"),
    "instagram": int(os.getenv("IG_DAILY_CAP", "4") or "4"),
}
DEFAULT_MIN_SPACING_SEC = {
    "tiktok": max(60, int(os.getenv("TIKTOK_MIN_SPACING_MIN", "90") or "90") * 60),
    "youtube": max(60, int(os.getenv("YT_MIN_SPACING_MIN", "120") or "120") * 60),
    "instagram": max(60, int(os.getenv("IG_MIN_SPACING_MIN", "90") or "90") * 60),
}
YOUTUBE_QUOTA_COOLDOWN_SEC = 4 * 3600
TIKTOK_INBOX_COOLDOWN_SEC = 2 * 3600


def _ledger_path(out_dir: Path) -> Path:
    return out_dir / "publish_ledger.json"


def load_publish_ledger(out_dir: Path) -> Dict:
    """Load persistent daily upload budget, cooldowns, and last published niches."""
    today = _dt.date.today().isoformat()
    base = {
        "date": today,
        "tiktok": {"count": 0, "last_ts": 0.0, "last_niche": "", "cooldown_until": 0.0},
        "youtube": {"count": 0, "last_ts": 0.0, "last_niche": "", "cooldown_until": 0.0},
        "instagram": {"count": 0, "last_ts": 0.0, "last_niche": "", "cooldown_until": 0.0},
        "history": [],
    }
    p = _ledger_path(out_dir)
    if not p.is_file():
        return base
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return base
    except (OSError, json.JSONDecodeError):
        return base

    if data.get("date") != today:
        # New calendar day resets daily counters while preserving recent niche memory & spacing timestamps
        for ch in CHANNELS:
            prev = data.get(ch) or {}
            base[ch]["last_ts"] = float(prev.get("last_ts") or 0.0)
            base[ch]["last_niche"] = str(prev.get("last_niche") or "")
        base["history"] = list(data.get("history") or [])[-30:]
        return base

    for ch in CHANNELS:
        prev = data.get(ch) or {}
        base[ch].update({
            "count": int(prev.get("count") or 0),
            "last_ts": float(prev.get("last_ts") or 0.0),
            "last_niche": str(prev.get("last_niche") or ""),
            "cooldown_until": float(prev.get("cooldown_until") or 0.0),
        })
    base["history"] = list(data.get("history") or [])[-30:]
    return base


def save_publish_ledger(out_dir: Path, ledger: Dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _ledger_path(out_dir).write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


def can_publish_channel(ledger: Dict, channel: str, now: Optional[float] = None) -> Tuple[bool, str, float]:
    """Check daily cap, organic interval spacing, and API cooldown for one channel."""
    ts = time.time() if now is None else float(now)
    st = ledger.get(channel) or {}
    cap = DEFAULT_DAILY_CAPS.get(channel, 5)
    min_gap = DEFAULT_MIN_SPACING_SEC.get(channel, 5400)

    cooldown_until = float(st.get("cooldown_until") or 0.0)
    if ts < cooldown_until:
        return False, "quota_cooldown", round(cooldown_until - ts, 1)

    if int(st.get("count") or 0) >= cap:
        return False, f"daily_cap_reached ({cap}/dia)", 0.0

    last_ts = float(st.get("last_ts") or 0.0)
    if last_ts > 0 and (ts - last_ts) < min_gap:
        wait_sec = round(min_gap - (ts - last_ts), 1)
        return False, f"organic_spacing ({int(wait_sec // 60)}m restantes)", wait_sec

    return True, "ready", 0.0


def _score_candidate_for_channel(mp4: Path, pack: Dict, channel: str, last_niche: str) -> Dict:
    val = pack.get("validation") or {}
    vis = pack.get("visual_audit") or {}
    opus = score_short_opus_runbook(pack, validation=val)
    yt = score_short_for_youtube_algorithm(pack=pack, validation=val, filename=mp4.name)
    tt = score_short_for_tiktok_algorithm(pack=pack, validation=val, filename=mp4.name)

    algo_pts = tt["tiktok_score"] if channel == "tiktok" else yt["algo_score"]
    vis_pts = float((vis.get("visual") or {}).get("vision_score") or vis.get("quality_score") or 75.0)
    niche = str(pack.get("niche") or "geral").strip().lower()
    dur = float(val.get("duration") or 0.0)

    composite = opus["opus_score"] * 0.45 + algo_pts * 0.45 + vis_pts * 0.10
    if niche and niche != last_niche:
        composite += 12.0  # Organic niche alternation bonus
    if channel == "tiktok" and dur >= 60.0:
        composite += 8.0   # Creator Rewards 60s+ priority boost

    return {
        "mp4": mp4,
        "filename": mp4.name,
        "title": pack.get("title") or mp4.name,
        "niche": niche,
        "duration": dur,
        "opus_score": opus["opus_score"],
        "channel_algo_score": algo_pts,
        "composite_score": round(composite, 2),
        "pack": pack,
    }


def rank_publish_candidates(out_dir: Path, channel: str, ledger: Optional[Dict] = None) -> List[Dict]:
    """Return validated, non-duplicate, unpublished candidates ordered by intelligence score."""
    if not out_dir.is_dir():
        return []
    lg = ledger or load_publish_ledger(out_dir)
    last_niche = str((lg.get(channel) or {}).get("last_niche") or "").lower()
    ranked: List[Dict] = []

    for mp4 in sorted(out_dir.glob("*.mp4")):
        if mp4.stat().st_size < 50_000:
            continue
        pack_file = mp4.with_suffix(".publish.json")
        if not pack_file.is_file():
            continue
        try:
            pack = json.loads(pack_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if pack.get("duplicate_of") or pack.get("queued_for_auto_publish") is False:
            continue
        if channel == "youtube" and isinstance(pack.get("youtube"), dict) and pack["youtube"].get("video_id"):
            continue
        if channel == "tiktok" and isinstance(pack.get("tiktok"), dict) and pack["tiktok"].get("publish_id"):
            continue
        if channel == "instagram" and isinstance(pack.get("instagram"), dict) and pack["instagram"].get("media_pk"):
            continue

        val = pack.get("validation") or {}
        if not val.get("valid"):
            continue
        vis = pack.get("visual_audit")
        if not isinstance(vis, dict):
            ass_cand = mp4.parent / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass"
            vis = audit_short_end_to_end(mp4, pack=pack, ass_path=ass_cand if ass_cand.is_file() else None, vision_check=False)
            pack["visual_audit"] = vis
            pack["queued_for_auto_publish"] = bool(vis.get("approved"))
            pack_file.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        if not vis.get("approved"):
            continue

        ranked.append(_score_candidate_for_channel(mp4, pack, channel, last_niche))

    ranked.sort(key=lambda item: (item["composite_score"], item["mp4"].stat().st_mtime), reverse=True)
    return ranked


def _needs_seo_healing(pack: Dict) -> bool:
    title = str(pack.get("title") or "")
    hook = str(pack.get("hook_title") or "")
    cap = str(pack.get("caption") or "")
    return (
        ">>" in title
        or ">>" in hook
        or title.lower().startswith("corte ")
        or len(cap.strip()) < 35
        or len(pack.get("hashtags") or []) < 3
    )


def get_autopublish_plan(
    out_dir: Path,
    youtube_ready: bool,
    tiktok_ready: bool,
    instagram_ready: bool = False,
    now: Optional[float] = None,
) -> Dict:
    """Summarize live smart queue, top-ranked next post per platform, and cooldown status."""
    ledger = load_publish_ledger(out_dir)
    plan: Dict[str, Dict] = {}
    for ch, enabled in (("tiktok", tiktok_ready), ("youtube", youtube_ready), ("instagram", instagram_ready)):
        ok, reason, wait_sec = can_publish_channel(ledger, ch, now=now) if enabled else (False, "unconfigured", 0.0)
        cands = rank_publish_candidates(out_dir, ch, ledger=ledger)
        top = cands[0] if cands else None
        plan[ch] = {
            "configured": enabled,
            "can_publish_now": ok,
            "gate_reason": reason,
            "wait_sec": wait_sec,
            "daily_used": int((ledger.get(ch) or {}).get("count") or 0),
            "daily_cap": DEFAULT_DAILY_CAPS.get(ch, 5),
            "last_niche": (ledger.get(ch) or {}).get("last_niche") or "",
            "pending_count": len(cands),
            "next_candidate": (
                {
                    "filename": top["filename"],
                    "title": top["title"],
                    "niche": top["niche"],
                    "composite_score": top["composite_score"],
                    "opus_score": top["opus_score"],
                    "channel_algo_score": top["channel_algo_score"],
                }
                if top
                else None
            ),
        }
    return {"date": ledger["date"], "channels": plan, "recent_history": ledger["history"][-8:]}


def run_smart_publish_cycle(
    out_dir: Path,
    youtube_ready: bool,
    tiktok_ready: bool,
    instagram_ready: bool = False,
    force: bool = False,
    now: Optional[float] = None,
    yt_publisher: Optional[Callable[[Path], Dict]] = None,
    tt_publisher: Optional[Callable[[Path], Dict]] = None,
    ig_publisher: Optional[Callable[[Path], Dict]] = None,
) -> Dict:
    """Select the highest-scoring, niche-diverse Short per ready channel, heal SEO, and publish."""
    ts = time.time() if now is None else float(now)
    ledger = load_publish_ledger(out_dir)
    yt_fn = yt_publisher or publish_pack_to_youtube
    tt_fn = tt_publisher or publish_pack_to_tiktok
    ig_fn = ig_publisher or publish_pack_to_instagram_reels

    results: Dict[str, Dict] = {}
    dispatched_any = False

    for ch, enabled, fn in (("tiktok", tiktok_ready, tt_fn), ("youtube", youtube_ready, yt_fn), ("instagram", instagram_ready, ig_fn)):
        if not enabled:
            results[ch] = {"status": "skipped_unconfigured"}
            continue
        ok, reason, wait_sec = can_publish_channel(ledger, ch, now=ts)
        if not ok and not (force and "organic_spacing" in reason):
            results[ch] = {"status": "deferred", "reason": reason, "wait_sec": wait_sec}
            continue

        cands = rank_publish_candidates(out_dir, ch, ledger=ledger)
        if not cands:
            results[ch] = {"status": "empty_queue"}
            continue

        picked = cands[0]
        mp4: Path = picked["mp4"]
        if _needs_seo_healing(picked["pack"]):
            ass_cand = next(
                (p for p in (out_dir / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass", mp4.with_suffix(".ass"), mp4.with_suffix(".srt")) if p.is_file()),
                None,
            )
            try:
                optimize_existing_publish_pack(mp4, ass_path=ass_cand)
            except Exception:
                pass

        try:
            pub_res = fn(mp4)
            is_sent = bool(pub_res.get("publish_id") or pub_res.get("video_id") or pub_res.get("media_pk") or str(pub_res.get("status", "")).startswith("published"))
            if is_sent:
                ledger[ch]["count"] = int(ledger[ch].get("count") or 0) + 1
                ledger[ch]["last_ts"] = ts
                ledger[ch]["last_niche"] = picked["niche"]
                ledger[ch]["cooldown_until"] = 0.0
                ledger["history"].append({
                    "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                    "channel": ch,
                    "filename": picked["filename"],
                    "title": picked["title"],
                    "niche": picked["niche"],
                    "composite_score": picked["composite_score"],
                    "id": pub_res.get("publish_id") or pub_res.get("video_id") or pub_res.get("media_pk") or "",
                })
                dispatched_any = True
            results[ch] = {"status": "published", "filename": picked["filename"], "score": picked["composite_score"], **pub_res}
        except Exception as exc:
            msg = str(exc)
            low = msg.lower()
            if ch == "youtube" and ("uploadlimitexceeded" in low or "exceeded the number of videos" in low):
                ledger[ch]["cooldown_until"] = ts + YOUTUBE_QUOTA_COOLDOWN_SEC
                results[ch] = {"status": "quota_cooldown_4h", "error": msg[:160]}
            elif ch == "tiktok" and ("spam_risk" in low or "rate_limit" in low or "too_many" in low):
                ledger[ch]["cooldown_until"] = ts + TIKTOK_INBOX_COOLDOWN_SEC
                results[ch] = {
                    "status": "inbox_pending_cooldown_2h",
                    "error": "Caixa de Entrada do TikTok atingiu limite de rascunhos pendentes. Publique/limpe no app TikTok no celular.",
                }
            else:
                results[ch] = {"status": "error", "error": msg[:200]}

    save_publish_ledger(out_dir, ledger)
    if dispatched_any:
        try:
            prune_storage(
                out_dir,
                max_videos=int(os.getenv("STORAGE_MAX_VIDEOS", "20")),
                max_output_mb=float(os.getenv("STORAGE_MAX_MB", "1200")),
            )
        except Exception:
            pass

    return {"dispatched": dispatched_any, "results": results, "plan": get_autopublish_plan(out_dir, youtube_ready, tiktok_ready, now=ts)}

