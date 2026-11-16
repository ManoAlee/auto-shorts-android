"""Professional Video Editing Engine for AI Shorts & Automated Cuts.

Fuses capabilities distilled from:
- github.com/gabuldev/auto-edit-video (silence removal, jump-zoom pacing)
- github.com/rtadewald/agent-video-editor (cinematic grading, audio ducking, safe zones)
- github.com/haidrrrry/claude-remotion-skill (motion graphics cards, animated progress & lower thirds)
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def generate_cinematic_filter_chain(
    width: int = 720,
    height: int = 1280,
    apply_vignette: bool = True,
    apply_color_grade: bool = True,
    zoom_scale: float = 1.0,
) -> str:
    """Generate high-end FFmpeg filter chain with color contrast and subtle vignette."""
    filters: List[str] = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "setsar=1",
    ]
    if apply_color_grade:
        # Subtle cinema contrast curve + rich saturation
        filters.append("eq=contrast=1.06:brightness=-0.02:saturation=1.10")

    if apply_vignette:
        # Focus viewer's gaze toward subtitles and central action
        filters.append("vignette=angle=PI/5:aspect=9/16")

    if zoom_scale > 1.0:
        # Push-in zoom centered
        crop_w = int(width / zoom_scale)
        crop_h = int(height / zoom_scale)
        filters.append(f"crop={crop_w}:{crop_h},scale={width}:{height}")

    return ",".join(filters)


def build_motion_graphics_lower_third(
    category_badge: str,
    headline_text: str,
    source_label: str = "",
    font_path: str = "",
    width: int = 720,
    height: int = 1280,
) -> List[str]:
    """Build Remotion-inspired lower-third / headline card using pure FFmpeg drawbox & drawtext.
    
    Safe zone placement: Top Y=64 to 200, strictly clear of platform top bars.
    """
    card_filters: List[str] = [
        # Dark modern frosted card
        "drawbox=x=24:y=60:w=672:h=138:color=0x0B0F19@0.88:t=fill",
        # Accent indicator border (Neon Red/Cyan)
        "drawbox=x=24:y=60:w=672:h=4:color=0x00E5FF:t=fill",
    ]

    safe_category = category_badge.upper().replace(":", "\\:").replace("'", "")[:24]
    safe_headline = headline_text.replace(":", "\\:").replace("'", "")[:65]
    safe_source = source_label.upper().replace(":", "\\:").replace("'", "")[:28]

    if font_path and Path(font_path).is_file():
        fp = font_path.replace("\\", "/").replace(":", "\\:")
        # Category Tag badge
        badge_txt = f"  {safe_category}  "
        card_filters.append(
            f"drawtext=fontfile='{fp}':text='{badge_txt}':"
            f"fontsize=16:fontcolor=white:box=1:boxcolor=0x00E5FF@0.9:boxborderw=4:x=40:y=76"
        )
        if safe_source:
            card_filters.append(
                f"drawtext=fontfile='{fp}':text='FONTE\\: {safe_source}':"
                f"fontsize=14:fontcolor=0xAAAAAA:x=220:y=78"
            )
        # Headline text
        card_filters.append(
            f"drawtext=fontfile='{fp}':text='{safe_headline}':"
            f"fontsize=20:fontcolor=white:borderw=2:bordercolor=black:x=40:y=118"
        )

    return card_filters


def parse_silence_intervals_from_ffmpeg(
    silence_log: str,
    min_silence_duration: float = 0.45,
) -> List[Tuple[float, float]]:
    """Parse silencedetect output from FFmpeg into a list of (start, end) silence timestamps."""
    silences: List[Tuple[float, float]] = []
    current_start: Optional[float] = None

    for line in silence_log.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            current_start = float(start_match.group(1))

        end_match = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if end_match:
            end_t = float(end_match.group(1))
            dur = float(end_match.group(2))
            if current_start is not None and dur >= min_silence_duration:
                silences.append((current_start, end_t))
            current_start = None

    return silences


def compute_speech_intervals_from_silences(
    silences: List[Tuple[float, float]],
    total_duration: float,
    padding: float = 0.15,
) -> List[Tuple[float, float]]:
    """Invert silence intervals into kept speech intervals with safety padding."""
    if not silences:
        return [(0.0, total_duration)]

    speech: List[Tuple[float, float]] = []
    cur_pos = 0.0

    for s_start, s_end in silences:
        # Buffer before silence
        seg_end = min(total_duration, s_start + padding)
        seg_start = max(0.0, cur_pos - padding if cur_pos > 0 else 0.0)
        
        if seg_end - seg_start >= 0.3:
            speech.append((round(seg_start, 3), round(seg_end, 3)))
        cur_pos = max(0.0, s_end - padding)

    if cur_pos < total_duration:
        seg_start = max(0.0, cur_pos)
        if total_duration - seg_start >= 0.3:
            speech.append((round(seg_start, 3), round(total_duration, 3)))

    return speech


def generate_capcut_word_pop_ass(
    segments: List[Dict[str, Any]],
    out_ass_path: Path,
    width: int = 720,
    height: int = 1280,
    video_width: Optional[int] = None,
    video_height: Optional[int] = None,
    primary_color: str = "&H00FFFFFF&",    # White
    highlight_color: str = "&H0000FFFF&",  # Vibrant Yellow (&HAABBGGRR in ASS)
    outline_color: str = "&H00000000&",    # Black outline
    font_name: str = "DejaVu Sans",
    font_size: int = 34,
    margin_v: Optional[int] = None,
    **kwargs: Any,
) -> Path:
    """Generate professional CapCut-style ASS subtitles with active word highlight & drop shadow."""
    vw = video_width if video_width is not None else width
    vh = video_height if video_height is not None else height
    out_ass_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Safe vertical position: 300px (~23.5%) from bottom (video-edit 450px @1080p rule)
    sub_margin_v = margin_v if margin_v is not None else int(vh * 0.235)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vw}
PlayResY: {vh}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CapCutPop,{font_name},{font_size},{primary_color},{highlight_color},{outline_color},&H80000000&,-1,0,0,0,100,100,1,0,1,3,2,2,48,72,{sub_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: List[str] = []

    def _fmt_ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

    for seg in segments:
        words = seg.get("words", [])
        if not words:
            # Fallback to whole segment
            start_str = _fmt_ts(float(seg.get("start", 0.0)))
            end_str = _fmt_ts(float(seg.get("end", 0.0)))
            txt = str(seg.get("text", "")).strip().upper()
            events.append(f"Dialogue: 0,{start_str},{end_str},CapCutPop,,0,0,0,,{txt}")
            continue

        # Word-by-word active highlight
        seg_start = float(words[0].get("start", seg.get("start", 0.0)))
        seg_end = float(words[-1].get("end", seg.get("end", 0.0)))

        # Group words in chunks of 3-5 words
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = words[i:i + chunk_size]
            c_start = float(chunk[0].get("start", seg_start))
            c_end = float(chunk[-1].get("end", seg_end))

            for active_idx, target_word in enumerate(chunk):
                w_start = float(target_word.get("start", c_start))
                w_end = float(target_word.get("end", c_end))

                # Build line where target_word is highlighted
                line_parts = []
                for idx, w in enumerate(chunk):
                    w_txt = str(w.get("word", "")).strip().upper()
                    if idx == active_idx:
                        # Highlight active word with secondary color & slight scale
                        line_parts.append(f"{{\\c{highlight_color}\\b1}}{w_txt}{{\\r}}")
                    else:
                        line_parts.append(w_txt)

                dialogue_line = " ".join(line_parts)
                events.append(
                    f"Dialogue: 0,{_fmt_ts(w_start)},{_fmt_ts(w_end)},CapCutPop,,0,0,0,,{dialogue_line}"
                )

    full_ass = header + "\n".join(events) + "\n"
    out_ass_path.write_text(full_ass, encoding="utf-8")
    return out_ass_path
