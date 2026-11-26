import json
import os
import subprocess
from pathlib import Path

out = Path("output")
mp4s = sorted(out.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
stats = {
    "total_mp4_files": len(mp4s),
    "raw_chunks_count": 0,
    "raw_chunks_mb": 0.0,
    "normal_shorts_count": 0,
    "normal_shorts_mb": 0.0,
    "tiny_mp4": 0,
    "no_ftyp": 0,
    "ffprobe_bad": 0,
    "no_json": 0,
    "bad_json": 0,
    "double_ext_json": 0,
    "yt_pub": 0,
    "tt_pub": 0,
    "ig_pub": 0,
    "rejected": 0,
    "weak_short_lt15s": 0,
    "work_dirs_count": 0,
    "work_dirs_mb": 0.0,
    "chrome_profiles_mb": 0.0,
}
errors = []

for entry in out.iterdir():
    if entry.is_dir():
        sz = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
        if entry.name.startswith(("_work_", "_news_bg_", "_narrate_")):
            stats["work_dirs_count"] += 1
            stats["work_dirs_mb"] += sz / (1024 * 1024)
        elif "chrome_profile" in entry.name:
            stats["chrome_profiles_mb"] += sz / (1024 * 1024)

for p in mp4s:
    sz = p.stat().st_size
    if ".raw_chunk" in p.name or p.name.startswith(("_", "temp_")) or ".part" in p.name:
        stats["raw_chunks_count"] += 1
        stats["raw_chunks_mb"] += sz / (1024 * 1024)
        continue
    stats["normal_shorts_count"] += 1
    stats["normal_shorts_mb"] += sz / (1024 * 1024)
    if sz < 50000:
        stats["tiny_mp4"] += 1
        errors.append({"file": p.name, "err": "tiny_mp4", "bytes": sz})
        continue
    try:
        head = p.read_bytes()[:65536]
        if b"ftyp" not in head[:64]:
            stats["no_ftyp"] += 1
            errors.append({"file": p.name, "err": "no_ftyp", "bytes": sz})
            continue
    except Exception as e:
        errors.append({"file": p.name, "err": f"read_err:{e}", "bytes": sz})
        continue

    # Check ffprobe duration/streams
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True, check=False
    )
    if pr.returncode != 0 or not pr.stdout.strip():
        stats["ffprobe_bad"] += 1
        errors.append({"file": p.name, "err": f"ffprobe_bad:{pr.stderr.strip()[:100]}", "bytes": sz})
    else:
        try:
            dur = float(pr.stdout.strip())
            if dur < 15.0:
                stats["weak_short_lt15s"] += 1
                errors.append({"file": p.name, "err": f"short_dur:{dur:.1f}s", "bytes": sz})
        except ValueError:
            pass

    pj = p.with_suffix(".publish.json")
    pj2 = p.with_name(p.name + ".publish.json")
    if pj2.is_file() and not pj.is_file():
        stats["double_ext_json"] += 1
        errors.append({"file": p.name, "err": "double_ext_json", "bytes": sz})
    elif not pj.is_file():
        stats["no_json"] += 1
        errors.append({"file": p.name, "err": "no_json", "bytes": sz})
    else:
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
            if (d.get("youtube") or {}).get("video_id") or (d.get("youtube") or {}).get("url"):
                stats["yt_pub"] += 1
            if (d.get("tiktok") or {}).get("publish_id"):
                stats["tt_pub"] += 1
            if (d.get("instagram") or {}).get("id") or (d.get("instagram") or {}).get("media_id"):
                stats["ig_pub"] += 1
            va = d.get("visual_audit") or {}
            if va and not va.get("approved"):
                stats["rejected"] += 1
                errors.append({"file": p.name, "err": "visual_rejected", "bytes": sz})
        except Exception as e:
            stats["bad_json"] += 1
            errors.append({"file": p.name, "err": f"bad_json:{e}", "bytes": sz})

stats["raw_chunks_mb"] = round(stats["raw_chunks_mb"], 1)
stats["normal_shorts_mb"] = round(stats["normal_shorts_mb"], 1)
stats["work_dirs_mb"] = round(stats["work_dirs_mb"], 1)
stats["chrome_profiles_mb"] = round(stats["chrome_profiles_mb"], 1)
print(json.dumps({"stats": stats, "errors": errors}, indent=2, ensure_ascii=False))
