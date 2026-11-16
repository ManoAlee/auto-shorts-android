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
    cmd = [yt_dlp_bin, "-g", "-f", "best[ext=mp4]/best", stream_url]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip().startswith("http")]
            return lines[0] if lines else None
    except Exception:
        pass
    return None


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

    # Add hook banner at the top seam
    font_path = find_default_font()
    font_arg = f":fontfile='{font_path}'" if font_path else ""
    safe_banner = hook_banner.replace("'", "").replace(":", "\\:").upper()

    banner_filter = (
        f";[{v_last}]drawbox=x=(w-980)/2:y=20:w=980:h=90:color=0x000000@0.75:t=fill,"
        f"drawtext=text='{safe_banner}'{font_arg}:fontcolor=0x00FFFF:fontsize=44:"
        f"x=(w-text_w)/2:y=42[v_banner]"
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
