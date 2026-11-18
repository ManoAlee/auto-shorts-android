"""Real-Time Live Stream Sniper & Gamer Split-Screen Clipper.

Engineered specifically for hyper-scale game launches (GTA 6 - Nov 19, 2026).
Monitors live streams (Twitch, YouTube, Kick), detects visceral reactions via audio energy spikes,
and renders 9:16 split-screen clips (Facecam + Gameplay) with viral hooks in <90 seconds.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .renderer import find_default_font
from .subtitles import escape_ffmpeg_filter_path
from .viral_intelligence import AntiSlopHumanizer, score_hook


@dataclass
class StreamerTarget:
    name: str
    channel_url: str
    platform: str  # twitch, youtube, kick
    default_facecam_pos: str  # top_right, top_left, bottom_right, bottom_left
    niche: str = "games_gta6"


GTA6_LAUNCH_WATCHLIST: List[StreamerTarget] = [
    StreamerTarget(
        name="Davy Jones",
        channel_url="https://www.youtube.com/@gameplayrj/live",
        platform="youtube",
        default_facecam_pos="top_left",
        niche="games_gta6",
    ),
    StreamerTarget(
        name="Alanzoka",
        channel_url="https://www.twitch.tv/alanzoka",
        platform="twitch",
        default_facecam_pos="bottom_right",
    ),
    StreamerTarget(
        name="Gaules",
        channel_url="https://www.twitch.tv/gaules",
        platform="twitch",
        default_facecam_pos="bottom_left",
    ),
    StreamerTarget(
        name="Coringa",
        channel_url="https://www.twitch.tv/loud_coringa",
        platform="twitch",
        default_facecam_pos="top_right",
    ),
    StreamerTarget(
        name="KaiCenat",
        channel_url="https://www.twitch.tv/kaicenat",
        platform="twitch",
        default_facecam_pos="bottom_right",
    ),
    StreamerTarget(
        name="xQc",
        channel_url="https://kick.com/xqc",
        platform="kick",
        default_facecam_pos="top_left",
    ),
]


class AudioEnergyAnalyzer:
    """Detects visceral human reactions (screams, laughter, shock) from raw PCM audio."""

    def __init__(self, sample_rate: int = 16000, spike_threshold_db: float = 8.0, min_absolute_db: float = -18.0):
        self.sample_rate = sample_rate
        self.spike_threshold_db = spike_threshold_db
        self.min_absolute_db = min_absolute_db
        self._history: List[float] = []
        self._max_history = 60  # keep ~60 seconds of history

    def calculate_db_from_pcm16(self, raw_bytes: bytes) -> float:
        """Compute Decibels Relative to Full Scale (dBFS) for 16-bit mono PCM."""
        if not raw_bytes or len(raw_bytes) < 2:
            return -96.0
        # Unpack signed 16-bit integers
        count = len(raw_bytes) // 2
        shorts = struct.unpack(f"<{count}h", raw_bytes[: count * 2])
        sum_sq = sum(float(sample * sample) for sample in shorts)
        rms = math.sqrt(sum_sq / count)
        if rms <= 0.0001:
            return -96.0
        # Reference max 32767
        db = 20.0 * math.log10(rms / 32767.0)
        return max(-96.0, min(0.0, db))

    def evaluate_frame(self, raw_bytes: bytes) -> Tuple[bool, float, float]:
        """Evaluate audio chunk. Returns (is_spike, current_db, rolling_avg_db)."""
        cur_db = self.calculate_db_from_pcm16(raw_bytes)
        if not self._history:
            avg_db = cur_db
        else:
            avg_db = sum(self._history) / len(self._history)

        self._history.append(cur_db)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # A spike occurs if audio jumps significantly above recent baseline and exceeds minimum threshold
        is_spike = (cur_db - avg_db >= self.spike_threshold_db) and (cur_db >= self.min_absolute_db)
        return is_spike, round(cur_db, 1), round(avg_db, 1)


def build_gamer_split_filter(
    facecam_pos: str = "bottom_right",
    facecam_pct: float = 0.34,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> str:
    """Build high-retention 9:16 Gamer Split-Screen FFmpeg filtergraph.

    Top: Streamer Facecam (scaled & cropped to 1080x650)
    Bottom: Centered 16:9 Gameplay (scaled & cropped to 1080x1270)
    Accented with subtle divider bar.
    """
    top_h = int(canvas_h * facecam_pct)
    # Ensure even heights for YUV420p
    top_h = top_h if top_h % 2 == 0 else top_h + 1
    bot_h = canvas_h - top_h

    # Presets for streamer webcam position inside 1920x1080 source
    cam_boxes = {
        "top_left": "x=0:y=0:w=iw*0.28:h=ih*0.32",
        "top_right": "x=iw*0.72:y=0:w=iw*0.28:h=ih*0.32",
        "bottom_left": "x=0:y=ih*0.68:w=iw*0.28:h=ih*0.32",
        "bottom_right": "x=iw*0.72:y=ih*0.68:w=iw*0.28:h=ih*0.32",
    }
    crop_cam = cam_boxes.get(facecam_pos, cam_boxes["bottom_right"])

    filtergraph = (
        f"[0:v]split=2[cam_raw][game_raw];"
        # 1. Facecam extraction & fill for top
        f"[cam_raw]crop={crop_cam},scale={canvas_w}:{top_h}:force_original_aspect_ratio=increase,"
        f"crop={canvas_w}:{top_h}[top_cam];"
        # 2. Gameplay crop for bottom
        f"[game_raw]scale={canvas_w}:{bot_h}:force_original_aspect_ratio=increase,"
        f"crop={canvas_w}:{bot_h}[bot_game];"
        # 3. Vertical Stack
        f"[top_cam][bot_game]vstack=inputs=2[v_stacked];"
        # 4. Subtle accent separator line at the boundary
        f"[v_stacked]drawbox=x=0:y={top_h - 2}:w={canvas_w}:h=4:color=0x00F0FF@0.9:t=fill[v_out]"
    )
    return filtergraph


def resolve_live_stream_url(stream_url: str) -> Optional[str]:
    """Resolve direct HLS/m3u8 stream URL using yt-dlp."""
    yt_dlp_bin = shutil.which("yt-dlp") or "yt-dlp"
    cmd = [yt_dlp_bin, "-g", "-f", "311+234/312+234/bestvideo+bestaudio/best", stream_url]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip().startswith("http")]
            return lines[0] if lines else None
    except Exception:
        pass
    return None


def check_streamer_is_live(channel_url: str) -> Optional[Dict[str, Any]]:
    """Probe if a target streamer is currently broadcasting live."""
    yt_dlp_bin = shutil.which("yt-dlp") or "yt-dlp"
    cmd = [
        yt_dlp_bin,
        "--dump-json",
        "--no-playlist",
        channel_url,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            meta = json.loads(res.stdout.splitlines()[0])
            is_live = meta.get("is_live") or meta.get("live_status") == "is_live"
            if is_live:
                return {
                    "id": meta.get("id"),
                    "title": meta.get("title", ""),
                    "channel": meta.get("channel") or meta.get("uploader", ""),
                    "url": meta.get("webpage_url") or f"https://www.youtube.com/watch?v={meta.get('id')}",
                    "viewers": meta.get("view_count") or meta.get("concurrent_view_count") or 0,
                }
    except Exception:
        pass
    return None


def download_live_chunk(
    stream_url: str,
    output_path: str | Path,
    duration_sec: int = 45,
    timeout_sec: Optional[int] = None,
) -> bool:
    """Download a high-quality chunk directly from an active live stream."""
    yt_dlp_bin = shutil.which("yt-dlp") or "yt-dlp"
    if timeout_sec is None:
        timeout_sec = max(90, int(duration_sec * 1.5) + 30)

    cmd = [
        yt_dlp_bin,
        "-f", "311+234/312+234/bestvideo+bestaudio/best",
        "--downloader", "ffmpeg",
        "--downloader-args", f"ffmpeg_i:-t {duration_sec}",
        "-o", str(output_path),
        "--no-playlist",
        stream_url,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_sec)
        return res.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 100000
    except Exception:
        return False


def render_gamer_clip(
    source_video: str | Path,
    output_mp4: str | Path,
    start_sec: float,
    duration_sec: float,
    hook_banner: str = "GTA 6: O PRIMEIRO BUG!",
    streamer_name: str = "Alanzoka",
    facecam_pos: str = "bottom_right",
    ass_subtitle_path: Optional[str | Path] = None,
) -> bool:
    """Render a standalone 9:16 gamer short with facecam split, banner, and loudnorm."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    src = str(source_video)
    out = str(output_mp4)

    filter_complex = build_gamer_split_filter(facecam_pos=facecam_pos, facecam_pct=0.34)
    v_last = "v_out"

    # Add hook banner at the seam between webcam and gameplay
    font_path = find_default_font()
    if font_path:
        font_path_esc = str(font_path).replace("\\", "/").replace(":", "\\:")
        font_arg = f":fontfile='{font_path_esc}'"
    else:
        font_arg = ""
    safe_banner = hook_banner.replace("'", "").replace(":", "\\:").upper()

    top_h = int(1920 * 0.34)
    top_h = top_h if top_h % 2 == 0 else top_h + 1

    banner_filter = (
        f";[{v_last}]drawbox=x=(w-980)/2:y={top_h + 16}:w=980:h=90:color=0x000000@0.75:t=fill,"
        f"drawtext=text='{safe_banner}'{font_arg}:fontcolor=0x00FFFF:fontsize=44:"
        f"x=(w-text_w)/2:y={top_h + 38}[v_banner]"
    )
    filter_complex += banner_filter
    v_last = "v_banner"

    # Add subtitle burn if available
    if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
        escaped_ass = escape_ffmpeg_filter_path(ass_subtitle_path)
        filter_complex += f";[{v_last}]subtitles='{escaped_ass}'[v_final]"
        v_last = "v_final"
    else:
        filter_complex = filter_complex.replace(f"[{v_last}]", "[v_final]")
        v_last = "v_final"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", f"{start_sec:.2f}",
        "-t", f"{duration_sec:.2f}",
        "-i", src,
        "-filter_complex", filter_complex,
        "-map", f"[{v_last}]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        out,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        return res.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 10000
    except Exception:
        return False


def snip_streamer_highlight(
    target: StreamerTarget,
    out_dir: str | Path,
    hook_banner: Optional[str] = None,
    clip_duration: float = 30.0,
    direct_url: Optional[str] = None,
    num_clips: int = 3,
) -> Optional[Dict[str, Any]]:
    """Snip multiple high-energy live reactions from a streamer into 9:16 Shorts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stream_url = direct_url or target.channel_url
    meta = check_streamer_is_live(stream_url)
    if not meta and not direct_url:
        return None

    title_source = (meta.get("title") if meta else "") or "GTA 6 Gameplay Ao Vivo"
    timestamp_tag = int(time.time())
    raw_sample = out_dir / f"live_{target.name.lower().replace(' ', '_')}_{timestamp_tag}_raw.mp4"

    # 1. Download live sample proportional to requested clips
    requested_clips = max(1, min(5, int(num_clips)))
    buffer_sec = max(60, min(240, int(requested_clips * (clip_duration + 15))))
    ok = download_live_chunk(stream_url, raw_sample, duration_sec=buffer_sec)
    if not ok or not raw_sample.is_file():
        return None

    # 2. Extract PCM audio and find non-overlapping reaction spikes
    analyzer = AudioEnergyAnalyzer(sample_rate=16000, spike_threshold_db=5.0, min_absolute_db=-25.0)
    selected_starts: List[float] = []

    try:
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        pcm_cmd = [
            ffmpeg_bin, "-y", "-i", str(raw_sample),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-f", "s16le", "-"
        ]
        pcm_proc = subprocess.run(pcm_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=max(45, buffer_sec + 30))
        raw_pcm = pcm_proc.stdout
        chunk_size = 16000 * 2  # 1 second
        spikes: List[Tuple[float, float]] = []
        for i in range(0, len(raw_pcm), chunk_size):
            chunk = raw_pcm[i:i + chunk_size]
            sec = float(i // chunk_size)
            is_spike, cur_db, avg_db = analyzer.evaluate_frame(chunk)
            if is_spike:
                spikes.append((sec, cur_db))

        # Sort spikes by energy and greedily pick non-overlapping reaction points
        spikes.sort(key=lambda s: s[1], reverse=True)
        min_spacing = max(20.0, clip_duration - 4.0)

        for sec, _ in spikes:
            start_cand = max(1.0, sec - 2.0)
            if not any(abs(start_cand - exist) < min_spacing for exist in selected_starts):
                selected_starts.append(start_cand)
                if len(selected_starts) >= requested_clips:
                    break
    except Exception:
        pass

    # If audio spikes were insufficient, space clips uniformly across the recorded buffer
    step = clip_duration + 5.0
    cand_offset = 2.0
    while len(selected_starts) < requested_clips and (cand_offset + clip_duration) <= (buffer_sec - 2.0):
        if not any(abs(cand_offset - exist) < (clip_duration - 2.0) for exist in selected_starts):
            selected_starts.append(cand_offset)
        cand_offset += step

    if not selected_starts:
        selected_starts = [2.0]

    selected_starts.sort()

    # 3. Render each Short segment with dedicated hooks
    banner_presets = [
        f"{target.name.upper()}: O INÍCIO DO GTA 6!",
        f"{target.name.upper()}: A REAÇÃO ÉPICA NO GTA 6!",
        f"{target.name.upper()}: INSANO NO GTA 6!",
        f"{target.name.upper()}: MOMENTO HISTÓRICO GTA 6!",
        f"{target.name.upper()}: NUNCA VISTO NO GTA 6!",
    ]

    generated_clips: List[Dict[str, Any]] = []

    for idx, start_sec in enumerate(selected_starts, start=1):
        suffix = f"_p{idx:02d}" if len(selected_starts) > 1 else ""
        out_mp4 = out_dir / f"short_live_{target.name.lower().replace(' ', '_')}_{timestamp_tag}{suffix}.mp4"

        if hook_banner and len(selected_starts) > 1:
            current_banner = f"{hook_banner} (Parte {idx})"
        elif hook_banner:
            current_banner = hook_banner
        else:
            current_banner = banner_presets[(idx - 1) % len(banner_presets)]

        rendered = render_gamer_clip(
            source_video=raw_sample,
            output_mp4=out_mp4,
            start_sec=start_sec,
            duration_sec=clip_duration,
            hook_banner=current_banner,
            streamer_name=target.name,
            facecam_pos=target.default_facecam_pos,
        )

        if rendered and out_mp4.is_file() and out_mp4.stat().st_size > 50000:
            part_str = f" (Parte {idx})" if len(selected_starts) > 1 else ""
            clean_title = f"{target.name} Reage ao GTA 6{part_str} | Gameplay Ao Vivo #Shorts"
            caption = (
                f"A reação do {target.name} jogando GTA 6 ao vivo no lançamento!{part_str}\n\n"
                f"Transmissão original: {title_source}\n"
                f"Canal do streamer: {target.channel_url}\n\n"
                f"#GTA6 #DavyJones #GameplayRJ #GTA6Gameplay #ShortsBrasil #Games #AleplayTV"
            )
            hashtags = ["#GTA6", "#DavyJones", "#GameplayRJ", "#GTA6Gameplay", "#ShortsBrasil", "#Games", "#AleplayTV"]
            created_iso = time.strftime("%Y-%m-%dT%H:%M:%S")

            pack_data = {
                "title": clean_title,
                "caption": caption,
                "hashtags": hashtags,
                "niche": "games_gta6",
                "playlist": "Games e GTA 6 - Shorts",
                "composite_score": 115.0,
                "opus_score": 95,
                "channel_algo_score": 98,
                "streamer": target.name,
                "source_url": stream_url,
                "part": idx,
                "total_parts": len(selected_starts),
                "created_at": created_iso,
            }
            publish_json = out_mp4.with_suffix(".publish.json")
            publish_json.write_text(json.dumps(pack_data, ensure_ascii=False, indent=2), encoding="utf-8")

            generated_clips.append({
                "video_path": str(out_mp4),
                "publish_path": str(publish_json),
                "title": clean_title,
                "pack": pack_data,
            })

    # Clean up raw sample
    try:
        raw_sample.unlink(missing_ok=True)
    except Exception:
        pass

    if not generated_clips:
        return None

    first = generated_clips[0]
    return {
        "clips": generated_clips,
        "count": len(generated_clips),
        "video_path": first["video_path"],
        "publish_path": first["publish_path"],
        "title": first["title"],
        "pack": first["pack"],
    }


def probe_and_snip_gta6_watchlist(out_dir: str | Path, num_clips: int = 3) -> Optional[Dict[str, Any]]:
    """Scan all streamers in the GTA6 launch watchlist and snip multiple highlights from the first active live."""
    for target in GTA6_LAUNCH_WATCHLIST:
        try:
            live_meta = check_streamer_is_live(target.channel_url)
            if live_meta:
                res = snip_streamer_highlight(target, out_dir=out_dir, num_clips=num_clips)
                if res:
                    return res
        except Exception:
            continue
    return None
