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
        min_silence_sec=0.48,
        pace_speed=1.04,
        punch_zoom=1.04,
        target_min_sec=22,
        target_max_sec=46,     # 2025/2026 Shorts completion & rewatch sweet spot (22-45s)
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


def build_pattern_interrupt_filter(width: int, height: int, zoom: float = 1.05, interval_sec: float = 3.5) -> str:
    """Return a zero-overhead FFmpeg scale+crop expression toggling subtle zoom every N seconds.

    Breaks visual monotony every 2.5-3.5s (2025/2026 retention benchmark) to prevent swipe-aways.
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
        mp4_path.with_name(f"{mp4_path.name}.publish.json"),
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


def _prune_chrome_profile_caches(out_root: Path) -> int:
    """Trim heavy browser cache dirs inside *_chrome_profile while keeping login cookies."""
    freed = 0
    cache_names = ("Cache", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache", "Media Cache")
    for prof in out_root.glob("*_chrome_profile"):
        if not prof.is_dir():
            continue
        for sub in (prof / "Default", prof):
            if not sub.is_dir():
                continue
            for cname in cache_names:
                cdir = sub / cname
                if cdir.is_dir():
                    freed += _dir_bytes(cdir)
                    shutil.rmtree(cdir, ignore_errors=True)
    return freed


def prune_storage(
    out_dir: str | Path,
    max_videos: int = 20,
    max_output_mb: float = 800.0,
    keep_recent_work_hours: float = 0.5,
) -> Dict:
    """Brutal smart phone-only storage retention.

    1. Purges raw stream chunks (_work_live_*.raw_chunk*), temp_*.mp4, *.part, *.ytdl, and stale temp dirs.
    2. Purges 0-byte/corrupted MP4s (<50KB) and orphaned sidecars (.ass/.srt/.wav/.mp3/.jpg without .mp4).
    3. Trims heavy Chrome profile caches while preserving login cookies.
    4. Enforces max_videos & max_output_mb: deletes duplicates/rejected first, then oldest published,
       then lowest-score/oldest unpublished until strictly within phone limits.
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
        if entry.is_dir():
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
            continue

        # Clean stale raw chunks, partial downloads, and temp files in output/ root
        if not entry.is_file():
            continue
        fname = entry.name
        is_temp_blob = (
            ".raw_chunk" in fname
            or fname.startswith(("_work_", "temp_"))
            or fname.endswith((".part", ".ytdl", ".tmp"))
        )
        try:
            mtime = entry.stat().st_mtime
            sz = entry.stat().st_size
        except OSError:
            continue
        if is_temp_blob and mtime <= cutoff_work:
            try:
                freed_bytes += sz
                entry.unlink(missing_ok=True)
                removed_videos.append(fname)
            except OSError:
                pass

    # 1b. Trim Chrome cache bloat while keeping cookies
    freed_bytes += _prune_chrome_profile_caches(out_root)

    # 2. Classify generated MP4s (excluding temp/raw prefixes) and purge corrupted/orphaned ones
    records: List[Dict] = []
    for mp4 in sorted(out_root.glob("*.mp4"), key=lambda p: p.stat().st_mtime):
        if ".raw_chunk" in mp4.name or mp4.name.startswith(("_", "temp_")):
            continue
        try:
            st = mp4.stat()
        except OSError:
            continue
        if st.st_size < 50000 and (now - st.st_mtime) > 600.0:
            freed_bytes += _delete_video_with_sidecars(mp4)
            removed_videos.append(mp4.name)
            continue

        pack: Dict = {}
        pj = mp4.with_suffix(".publish.json")
        if pj.is_file():
            try:
                pack = json.loads(pj.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pack = {}
        vis_ok = bool((pack.get("visual_audit") or {}).get("approved") if pack.get("visual_audit") else (pack.get("validation") or {}).get("valid", True))
        is_pub = bool(
            (pack.get("youtube") or {}).get("video_id")
            or (pack.get("youtube") or {}).get("url")
            or (pack.get("tiktok") or {}).get("publish_id")
            or (pack.get("instagram") or {}).get("id")
            or (pack.get("instagram") or {}).get("media_id")
        )
        score = int(
            pack.get("sentinel_overall_score")
            or (pack.get("opus_scorecard") or {}).get("opus_score")
            or (pack.get("validation") or {}).get("score")
            or 50
        )
        is_dup = bool(pack.get("duplicate_of"))
        records.append({
            "path": mp4,
            "mtime": st.st_mtime,
            "is_dup": is_dup,
            "is_rejected": not vis_ok,
            "is_published": is_pub,
            "score": score,
        })

    # 2b. Remove orphaned sidecars (.ass/.srt/.jpg/.publish.json) with no matching .mp4
    valid_stems = {r["path"].stem for r in records}
    for entry in list(out_root.iterdir()):
        if not entry.is_file():
            continue
        suf = entry.suffix.lower()
        if suf in {".ass", ".srt"} or entry.name.endswith(("_thumb_16x9.jpg", "_cover_9x16.jpg", ".publish.json")):
            stem = entry.name
            for tag in ("_thumb_16x9.jpg", "_cover_9x16.jpg", ".publish.json", ".ass", ".srt"):
                if stem.endswith(tag):
                    stem = stem[: -len(tag)]
                    break
            if stem not in valid_stems:
                try:
                    if entry.stat().st_mtime <= cutoff_work:
                        freed_bytes += entry.stat().st_size
                        entry.unlink(missing_ok=True)
                except OSError:
                    pass

    # 3. Always remove exact duplicates and rejected clips
    kept: List[Dict] = []
    for rec in records:
        if rec["is_dup"] or (rec["is_rejected"] and (now - rec["mtime"]) > 1800.0):
            freed_bytes += _delete_video_with_sidecars(rec["path"])
            removed_videos.append(rec["path"].name)
        else:
            kept.append(rec)

    # 4. Enforce max_videos & max_output_mb: published oldest first, then lowest-score/oldest unpublished
    total_mb = _dir_bytes(out_root) / (1024 * 1024)
    if len(kept) > max_v or total_mb > max_mb:
        prune_order = sorted(
            kept,
            key=lambda r: (0 if r["is_published"] else 1, r["score"], r["mtime"]),
        )
        for rec in prune_order:
            if len(kept) <= max_v and total_mb <= max_mb:
                break
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

