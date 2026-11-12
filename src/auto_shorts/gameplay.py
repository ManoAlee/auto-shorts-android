"""No-copyright gameplay background manager for viral narrated & news Shorts."""

from pathlib import Path
import random
import re
import subprocess
from typing import Dict, List, Optional, Tuple

GAMEPLAY_QUERIES: Dict[str, List[str]] = {
    "minecraft": [
        "ytsearch8:minecraft parkour gameplay no copyright vertical",
        "ytsearch8:minecraft parkour gameplay free to use no copyright",
    ],
    "subway": [
        "ytsearch8:subway surfers gameplay no copyright vertical",
        "ytsearch8:subway surfers no copyright gameplay 1080x1920",
    ],
    "gta_ramp": [
        "ytsearch8:gta 5 mega ramp no copyright gameplay vertical",
        "ytsearch8:gta 5 stunt race gameplay no copyright",
    ],
    "beamng": [
        "ytsearch8:beamng drive mega ramp gameplay no copyright",
        "ytsearch8:beamng drive stunts no copyright gameplay vertical",
    ],
    "satisfying": [
        "ytsearch8:satisfying kinetic sand cutting no copyright vertical",
        "ytsearch8:soap carving kinetic sand relaxing no copyright",
    ],
    "drone_cinema": [
        "ytsearch8:4k drone aerial city mountain sunset no copyright vertical",
        "ytsearch8:fpv drone nature flying no copyright b roll",
    ],
    "space_cosmos": [
        "ytsearch8:4k space earth from orbit nebula timelapse no copyright",
        "ytsearch8:cosmos galaxy stars animation no copyright background",
    ],
    "urban_rain": [
        "ytsearch8:cyberpunk night rain city walk 4k no copyright",
        "ytsearch8:night car drive rain neon aesthetic no copyright",
    ],
    "finance_minimal": [
        "ytsearch8:modern glass skyscrapers financial district drone 4k no copyright",
        "ytsearch8:luxury supercar night driving 4k no copyright",
    ],
    "fitness_motion": [
        "ytsearch8:calisthenics street workout motivation b roll no copyright",
        "ytsearch8:runner athlete training morning fog no copyright",
    ],
}

NICHE_STYLE_AFFINITY: Dict[str, List[str]] = {
    "noticias_mundiais": ["drone_cinema", "urban_rain", "space_cosmos"],
    "ia_tech": ["space_cosmos", "urban_rain", "drone_cinema"],
    "financas": ["finance_minimal", "drone_cinema", "urban_rain"],
    "desenvolvimento_pessoal": ["drone_cinema", "urban_rain", "space_cosmos"],
    "saude_fitness": ["fitness_motion", "drone_cinema", "urban_rain"],
    "entretenimento_animes": ["urban_rain", "space_cosmos", "drone_cinema"],
    "podcast": ["urban_rain", "drone_cinema", "space_cosmos"],
    "concursos": ["drone_cinema", "urban_rain", "finance_minimal"],
    "gameplay": ["minecraft", "subway", "gta_ramp", "beamng", "satisfying"],
}

_BRAINROT_GAMEPLAY_STYLES = {"minecraft", "subway", "gta_ramp", "beamng", "satisfying"}


def discover_dynamic_visual_queries(niche: str = "geral", topic: str = "") -> Tuple[str, List[str]]:
    """Build dynamic no-copyright background search queries tailored to any topic/niche."""
    clean_words = [
        w for w in re.sub(r"[^a-zA-ZÀ-ÿ0-9 ]+", " ", (topic or "")).split()
        if len(w) >= 4
    ][:3]
    if clean_words:
        slug = "adaptive_" + "_".join(clean_words[:2]).lower()
        kw = " ".join(clean_words)
        return slug, [
            f"ytsearch8:{kw} 4k cinematic background no copyright",
            f"ytsearch8:{kw} aesthetic loop no copyright vertical",
        ]
    affinity = NICHE_STYLE_AFFINITY.get(niche, ["minecraft", "subway", "drone_cinema", "gta_ramp", "satisfying"])
    chosen_style = random.choice(affinity)
    return chosen_style, GAMEPLAY_QUERIES.get(chosen_style, GAMEPLAY_QUERIES["minecraft"])


def gameplay_cache_dir(out_dir: str | Path) -> Path:
    """Return persistent assets/gameplay directory beside project root."""
    out_p = Path(out_dir).resolve()
    root = out_p.parent if out_p.name in {"output", "out"} else out_p
    gdir = root / "assets" / "gameplay"
    gdir.mkdir(parents=True, exist_ok=True)
    return gdir


def probe_video_duration(video_path: Path) -> float:
    """Return duration in seconds via ffprobe, or 0.0 on failure."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nk=1:nw=1",
                str(video_path),
            ],
            text=True,
            timeout=6,
        ).strip()
        return max(0.0, float(out))
    except Exception:
        return 0.0


def list_gameplay_clips(out_dir: str | Path) -> List[Path]:
    """List cached valid gameplay MP4 files (>200 KB)."""
    gdir = gameplay_cache_dir(out_dir)
    return sorted(
        (p for p in gdir.glob("*.mp4") if p.is_file() and p.stat().st_size > 200_000),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _normalize_to_vertical_gameplay(raw_path: Path, final_path: Path, max_sec: int = 180) -> bool:
    """Transcode fetched clip into smooth 720x1280 30fps vertical loop ready for mobile rendering."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "8", "-t", str(max_sec),
        "-i", str(raw_path),
        "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,eq=contrast=1.05:saturation=1.10",
        "-fps_mode", "cfr", "-r", "30", "-g", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-an",
        str(final_path),
    ]
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0 and final_path.is_file() and final_path.stat().st_size > 200_000


def fetch_gameplay_clip(
    out_dir: str | Path,
    style: str = "minecraft",
    max_sec: int = 180,
    custom_queries: Optional[List[str]] = None,
) -> Optional[Path]:
    """Download one no-copyright gameplay or dynamic B-roll clip via yt-dlp and cache it in 9:16."""
    import yt_dlp

    gdir = gameplay_cache_dir(out_dir)
    queries = custom_queries or GAMEPLAY_QUERIES.get(style, GAMEPLAY_QUERIES["minecraft"])
    chosen_url = ""
    chosen_id = "gp"
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "no_warnings": True}) as ydl:
            for q in queries:
                info = ydl.extract_info(q, download=False) or {}
                for entry in (info.get("entries") or []):
                    dur = float(entry.get("duration") or 0)
                    title_low = str(entry.get("title") or "").lower()
                    if 60 <= dur <= 720 and entry.get("id"):
                        # Prefer clean gameplay titles without speech/facecam overlays
                        if any(bad in title_low for bad in ("tutorial", "review", "react", "commentary")):
                            continue
                        chosen_id = str(entry["id"])
                        chosen_url = f"https://www.youtube.com/watch?v={chosen_id}"
                        break
                if chosen_url:
                    break
        if not chosen_url:
            return None

        raw_tpl = str(gdir / f"_raw_{style}_{chosen_id}.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[height<=720][ext=mp4]/best[height<=720][ext=mp4]/best[height<=720]",
            "outtmpl": raw_tpl,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([chosen_url])

        raw_files = list(gdir.glob(f"_raw_{style}_{chosen_id}.*"))
        if not raw_files:
            return None
        raw_file = raw_files[0]
        final_mp4 = gdir / f"gp_{style}_{chosen_id}.mp4"
        ok = _normalize_to_vertical_gameplay(raw_file, final_mp4, max_sec=max_sec)
        for rf in raw_files:
            rf.unlink(missing_ok=True)
        return final_mp4 if ok else None
    except Exception:
        for rf in gdir.glob(f"_raw_{style}_*"):
            rf.unlink(missing_ok=True)
        return None


def ensure_gameplay_library(out_dir: str | Path, styles: Tuple[str, ...] = ("minecraft", "subway")) -> List[Path]:
    """Ensure at least one real gameplay clip per requested style exists locally."""
    existing = list_gameplay_clips(out_dir)
    if existing:
        return existing
    created: List[Path] = []
    for st in styles:
        p = fetch_gameplay_clip(out_dir, style=st)
        if p is not None:
            created.append(p)
            break  # One working loop immediately unblocks rendering; caller can sync more
    return created


def _is_segment_visually_bright(clip_path: Path, offset_sec: float = 2.0) -> bool:
    """Fast 1-frame luma check so dark fade-ins or pitch-black space loops are rejected before render."""
    try:
        if not clip_path.is_file() or clip_path.stat().st_size < 10_000:
            return True
        if b"ftyp" not in clip_path.read_bytes()[:64]:
            return True
        import shutil
        if not shutil.which("ffmpeg"):
            return True
        raw = subprocess.check_output(
            [
                "ffmpeg", "-v", "error", "-ss", f"{max(0.0, offset_sec + 3.0):.2f}",
                "-i", str(clip_path), "-frames:v", "1",
                "-vf", "scale=32:32,format=gray", "-f", "rawvideo", "pipe:1",
            ],
            stderr=subprocess.DEVNULL,
            timeout=6,
        )
        if len(raw) < 1024:
            return True
        mean = sum(raw[:1024]) / 1024.0
        var = sum((b - mean) ** 2 for b in raw[:1024]) / 1024.0
        return mean >= 20.0 and (var ** 0.5) >= 7.0
    except Exception:
        return True


def _extract_style_tag(clip_path: Path) -> str:
    parts = clip_path.stem.split("_")
    if len(parts) >= 3 and parts[0] == "gp":
        return "_".join(parts[1:-1])
    return clip_path.stem


def pick_evolving_background(
    out_dir: str | Path,
    niche: str = "geral",
    topic: str = "",
    min_duration: float = 40.0,
    auto_download: bool = True,
) -> Optional[Tuple[Path, float, str]]:
    """Adaptive & evolving visual background selector (UCB1 bandit + dynamic niche/topic discovery)."""
    from .evolution import EvolutionStore

    clips = sorted(list_gameplay_clips(out_dir), key=lambda p: p.name)
    gdir = gameplay_cache_dir(out_dir)
    hist_file = gdir / ".last_gameplay.txt"
    last_name = hist_file.read_text(encoding="utf-8").strip() if hist_file.is_file() else ""
    last_style = last_name.split("|")[1] if "|" in last_name else ""

    existing_styles = sorted({_extract_style_tag(c) for c in clips})
    preferred_for_niche = NICHE_STYLE_AFFINITY.get(niche, list(GAMEPLAY_QUERIES.keys()))

    # Exploration boost: grow library dynamically beyond static styles when network/auto_download allowed
    if auto_download and len(existing_styles) < 8:
        unseen_niche_styles = [s for s in preferred_for_niche if s not in existing_styles]
        if not clips or (unseen_niche_styles and random.random() < 0.35):
            if unseen_niche_styles:
                dl_style = unseen_niche_styles[0]
                dl_queries = GAMEPLAY_QUERIES.get(dl_style)
            else:
                dl_style, dl_queries = discover_dynamic_visual_queries(niche=niche, topic=topic)
            fetched = fetch_gameplay_clip(out_dir, style=dl_style, custom_queries=dl_queries)
            if fetched is not None:
                clips = sorted(list_gameplay_clips(out_dir), key=lambda p: p.name)
                existing_styles = sorted({_extract_style_tag(c) for c in clips})

    if not clips:
        return None

    # Never inject random Minecraft/Subway/GTA gameplay into non-gaming niches when coherent cinematic B-roll exists
    if niche not in {"gameplay", "geral"}:
        coherent_clips = [
            c for c in clips
            if _extract_style_tag(c) in preferred_for_niche
            or _extract_style_tag(c).startswith("adaptive_")
            or _extract_style_tag(c) not in _BRAINROT_GAMEPLAY_STYLES
        ]
        if coherent_clips:
            clips = coherent_clips
            existing_styles = sorted({_extract_style_tag(c) for c in clips})

    store = EvolutionStore(Path(out_dir) / "shorts_evolution.db")
    chosen_style = store.select_evolving_background_style(niche, existing_styles, last_style=last_style)
    style_clips = [c for c in clips if _extract_style_tag(c) == chosen_style] or clips
    last_file = last_name.split("|")[0]
    fresh_clips = [c for c in style_clips if c.name != last_file] or style_clips
    chosen = random.choice(fresh_clips)

    try:
        hist_file.write_text(f"{chosen.name}|{chosen_style}", encoding="utf-8")
    except OSError:
        pass

    total = probe_video_duration(chosen)
    max_off = max(0.0, total - min_duration - 2.0)
    offset = round(random.uniform(0.0, max_off), 2) if max_off >= 3.0 else 0.0

    # Pre-check brightness before committing render so dark backgrounds (e.g. space blackouts) never ship
    if not _is_segment_visually_bright(chosen, offset):
        alt_off = round(min(max_off, total * 0.45), 2) if max_off >= 3.0 else 2.0
        if _is_segment_visually_bright(chosen, alt_off):
            offset = alt_off
        else:
            store.record_background_outcome(niche, chosen_style, quality_score=22.0)
            for alt_clip in [c for c in clips if c.name != chosen.name]:
                alt_tot = probe_video_duration(alt_clip)
                alt_max = max(0.0, alt_tot - min_duration - 2.0)
                cand_off = round(random.uniform(0.0, alt_max), 2) if alt_max >= 3.0 else 0.0
                if _is_segment_visually_bright(alt_clip, cand_off):
                    chosen = alt_clip
                    chosen_style = _extract_style_tag(alt_clip)
                    offset = cand_off
                    try:
                        hist_file.write_text(f"{chosen.name}|{chosen_style}", encoding="utf-8")
                    except OSError:
                        pass
                    break
    return chosen, offset, chosen_style


def pick_gameplay_segment(
    out_dir: str | Path,
    min_duration: float = 40.0,
    auto_download: bool = True,
    seed_style: Optional[str] = None,
) -> Optional[Tuple[Path, float]]:
    """Rotate strictly across different visual styles without consecutive repeats + random offset."""
    res = pick_evolving_background(
        out_dir,
        niche=seed_style or "geral",
        min_duration=min_duration,
        auto_download=auto_download,
    )
    if res is None:
        return None
    return res[0], res[1]

