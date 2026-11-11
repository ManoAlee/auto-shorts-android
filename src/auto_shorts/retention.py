"""Smart Retention engine calibrated to Instagram Reels, TikTok, and Shorts algorithms."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import time
from typing import Dict, List


@dataclass(frozen=True)
class RetentionProfile:
    platform: str
    min_silence_sec: float
    pace_speed: float
    punch_zoom: float
    target_min_sec: int
    target_max_sec: int
    reels_cta_hint: str


RETENTION_PROFILES: Dict[str, RetentionProfile] = {
    "instagram_reels": RetentionProfile(
        platform="instagram_reels",
        min_silence_sec=0.45,  # Aggressive jump-cut for high completion & rewatch rate
        pace_speed=1.04,       # Subtle 4% pace lift keeps attention without chipmunk voice
        punch_zoom=1.05,       # 5% periodic zoom pulse every 6s as visual pattern interrupt
        target_min_sec=25,
        target_max_sec=48,     # Sweet spot for Reels completion + shares/saves
        reels_cta_hint="Salva esse Reel pra nao perder e manda pra um amigo que curte isso!",
    ),
    "youtube_shorts": RetentionProfile(
        platform="youtube_shorts",
        min_silence_sec=0.50,
        pace_speed=1.03,
        punch_zoom=1.04,
        target_min_sec=30,
        target_max_sec=56,
        reels_cta_hint="Se inscreve para acompanhar os proximos cortes e novidades todos os dias!",
    ),
    "tiktok_rewards": RetentionProfile(
        platform="tiktok_rewards",
        min_silence_sec=0.65,  # Preserves >60s runtime required by Creator Rewards
        pace_speed=1.00,
        punch_zoom=1.04,
        target_min_sec=62,
        target_max_sec=90,
        reels_cta_hint="Comenta sua opiniao e segue para acompanhar os proximos cortes!",
    ),
}


def get_retention_profile(platform: str) -> RetentionProfile:
    return RETENTION_PROFILES.get(platform, RETENTION_PROFILES["instagram_reels"])


def build_pattern_interrupt_filter(width: int, height: int, zoom: float = 1.05, interval_sec: int = 6) -> str:
    """Return a zero-overhead FFmpeg scale+crop expression toggling subtle zoom every N seconds.

    Breaks visual monotony every few seconds to hold attention and avoid static-reupload flags.
    """
    if zoom <= 1.0:
        return ""
    amp = (zoom - 1.0) / 2.0
    # Smooth cos-eased zoom pulse avoiding jarring jumps while preserving eval=frame
    return (
        f"scale='trunc((iw*(1+{amp:.4f}*(1-cos(2*PI*t/{interval_sec}))))/2)*2':"
        f"'trunc((ih*(1+{amp:.4f}*(1-cos(2*PI*t/{interval_sec}))))/2)*2':eval=frame,"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
    )


def _dir_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    for root, _dirs, files in os.walk(path):
        for fn in files:
            try:
                total += (Path(root) / fn).stat().st_size
            except OSError:
                pass
    return total


def _delete_video_with_sidecars(mp4_path: Path) -> int:
    freed = 0
    targets = [
        mp4_path,
        mp4_path.with_suffix(".publish.json"),
        mp4_path.with_suffix(".ass"),
        mp4_path.with_suffix(".srt"),
        mp4_path.with_name(f"{mp4_path.stem}_thumb_16x9.jpg"),
        mp4_path.with_name(f"{mp4_path.stem}_cover_9x16.jpg"),
    ]
    for p in targets:
        if p.is_file():
            try:
                freed += p.stat().st_size
                p.unlink(missing_ok=True)
            except OSError:
                pass
    narrate_dir = mp4_path.parent / f"_narrate_{mp4_path.stem}"
    if narrate_dir.is_dir():
        freed += _dir_bytes(narrate_dir)
        shutil.rmtree(narrate_dir, ignore_errors=True)
    return freed


def prune_storage(
    out_dir: str | Path,
    max_videos: int = 20,
    max_output_mb: float = 1200.0,
    keep_recent_work_hours: float = 1.0,
) -> Dict:
    """Smart storage retention: clean stale temp dirs, duplicates, rejected clips, and oldest published Shorts.

    Never deletes unpublished validated Shorts waiting in the YouTube publish queue unless explicitly rejected/duplicated.
    """
    out_root = Path(out_dir)
    if not out_root.is_dir():
        return {"ok": True, "freed_mb": 0.0, "removed_dirs": 0, "removed_videos": [], "remaining_videos": 0, "total_mb": 0.0}

    max_v = int(os.getenv("STORAGE_MAX_VIDEOS", str(max_videos)) or max_videos)
    max_mb = float(os.getenv("STORAGE_MAX_MB", str(max_output_mb)) or max_output_mb)
    now = time.time()
    cutoff_work = now - max(0.0, keep_recent_work_hours) * 3600.0
    freed_bytes = 0
    removed_dirs = 0
    removed_videos: List[str] = []

    # 1. Remove orphaned _work_* / _news_bg_* directories and heavy _narrate_* scene intermediates
    for entry in list(out_root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith(("_work_", "_news_bg_")):
            try:
                if entry.stat().st_mtime <= cutoff_work:
                    freed_bytes += _dir_bytes(entry)
                    shutil.rmtree(entry, ignore_errors=True)
                    removed_dirs += 1
            except OSError:
                pass
        elif name.startswith("_narrate_"):
            stem = name[len("_narrate_"):]
            final_exists = (out_root / f"{stem}.mp4").is_file()
            try:
                stale = entry.stat().st_mtime <= cutoff_work
            except OSError:
                stale = False
            if final_exists:
                # Keep tiny .ass/.srt if needed, remove heavy intermediate B-Roll / scene MP4s & WAVs
                for f in list(entry.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".mp4", ".wav", ".mp3"}:
                        try:
                            freed_bytes += f.stat().st_size
                            f.unlink(missing_ok=True)
                        except OSError:
                            pass
                if not any(entry.iterdir()):
                    shutil.rmtree(entry, ignore_errors=True)
                    removed_dirs += 1
            elif stale:
                freed_bytes += _dir_bytes(entry)
                shutil.rmtree(entry, ignore_errors=True)
                removed_dirs += 1

    # 2. Classify generated MP4s
    records: List[Dict] = []
    for mp4 in sorted(out_root.glob("*.mp4"), key=lambda p: p.stat().st_mtime):
        pack: Dict = {}
        pj = mp4.with_suffix(".publish.json")
        if pj.is_file():
            try:
                pack = json.loads(pj.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pack = {}
        vis_ok = bool((pack.get("visual_audit") or {}).get("approved") if pack.get("visual_audit") else (pack.get("validation") or {}).get("valid", True))
        is_pub = bool((pack.get("youtube") or {}).get("video_id") or (pack.get("youtube") or {}).get("url"))
        is_dup = bool(pack.get("duplicate_of"))
        records.append({
            "path": mp4,
            "mtime": mp4.stat().st_mtime,
            "is_dup": is_dup,
            "is_rejected": not vis_ok,
            "is_published": is_pub,
        })

    # 3. Always remove exact duplicates (already deselected from queue) and invalid stubs
    kept: List[Dict] = []
    for rec in records:
        if rec["is_dup"] or (rec["is_rejected"] and (now - rec["mtime"]) > 3600.0):
            freed_bytes += _delete_video_with_sidecars(rec["path"])
            removed_videos.append(rec["path"].name)
        else:
            kept.append(rec)

    # 4. Enforce max_videos & max_output_mb by pruning oldest ALREADY-PUBLISHED videos first
    total_mb = _dir_bytes(out_root) / (1024 * 1024)
    if len(kept) > max_v or total_mb > max_mb:
        for rec in list(kept):
            if len(kept) <= max_v and total_mb <= max_mb:
                break
            if rec["is_published"]:
                b = _delete_video_with_sidecars(rec["path"])
                freed_bytes += b
                total_mb = max(0.0, total_mb - (b / (1024 * 1024)))
                removed_videos.append(rec["path"].name)
                kept.remove(rec)

    return {
        "ok": True,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "removed_dirs": removed_dirs,
        "removed_videos": removed_videos,
        "remaining_videos": len(kept),
        "total_mb": round(_dir_bytes(out_root) / (1024 * 1024), 2),
        "limits": {"max_videos": max_v, "max_output_mb": max_mb},
    }

