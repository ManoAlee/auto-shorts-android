"""Advanced high-CTR FFmpeg thumbnail & Reels cover generator for mobile Termux."""

import subprocess
from pathlib import Path
from typing import List, Optional

from .renderer import find_default_font
from .subtitles import escape_ffmpeg_filter_path


def _escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "")
        .replace("%", "\\%")
    )


def _split_hook_lines(hook_title: str, max_words: int = 5) -> List[str]:
    words = [w for w in (hook_title or "").strip().upper().split() if w][:max_words]
    if not words:
        return ["VOCE PRECISA", "VER ISSO!"]
    if len(words) <= 2:
        return [" ".join(words)]
    mid = (len(words) + 1) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def build_thumbnail_filter(
    width: int,
    height: int,
    hook_title: str,
    badge: str = "PODCAST",
    font_path: Optional[str] = None,
) -> str:
    """Build an FFmpeg filtergraph that turns a raw frame into a high-CTR thumbnail."""
    lines = _split_hook_lines(hook_title)
    parts: List[str] = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "eq=contrast=1.12:saturation=1.20:brightness=0.02",
        "vignette=PI/4",
        # Dark lower scrim to guarantee crisp text contrast on bright frames
        f"drawbox=x=0:y=ih*0.56:w=iw:h=ih*0.44:color=black@0.60:t=fill",
    ]

    if font_path:
        safe_font = escape_ffmpeg_filter_path(font_path)
        badge_txt = _escape_text((badge or "CORTES").upper()[:18])
        badge_size = max(22, int(min(width, height) * 0.042))
        # Safe zone calibration: vertical 9:16 (height > width) must clear phone notch,
        # status bar, and platform UI tabs (>= 150px on 1280h).
        badge_y = int(height * (0.125 if height > width else 0.08))
        badge_x = int(width * 0.08 if height > width else width * 0.05)
        parts.append(
            f"drawtext=fontfile='{safe_font}':text='{badge_txt}':"
            f"fontsize={badge_size}:fontcolor=black:box=1:boxcolor=#FFD400@0.95:"
            f"boxborderw=10:x={badge_x}:y={badge_y}"
        )

        # Dynamic title sizing to prevent horizontal overflow on narrow mobile screens
        max_line_len = max((len(l) for l in lines), default=10)
        base_title_size = max(38, int(height * 0.088 if width > height else width * 0.082))
        title_size = min(base_title_size, int((width * 0.86) / max(8, max_line_len * 0.58)))
        base_y = int(height * (0.60 if len(lines) == 2 else 0.68))
        line_gap = int(title_size * 1.18)
        for idx, line in enumerate(lines):
            color = "#FFD400" if idx == 0 else "white"
            safe_line = _escape_text(line)
            parts.append(
                f"drawtext=fontfile='{safe_font}':text='{safe_line}':"
                f"fontsize={title_size}:fontcolor={color}:borderw=6:bordercolor=black:"
                f"shadowcolor=black@0.8:shadowx=3:shadowy=3:"
                f"x=(w-text_w)/2:y={base_y + idx * line_gap}"
            )

    return ",".join(parts)


def generate_advanced_thumbnail(
    video_path: str | Path,
    out_jpg: str | Path,
    hook_title: str,
    badge: str = "PODCAST",
    timestamp_sec: float = 4.0,
    vertical_cover: bool = False,
) -> Path:
    """Render a compressed (<2MB) high-CTR 16:9 YouTube thumbnail or 9:16 Reels cover."""
    width, height = (720, 1280) if vertical_cover else (1280, 720)
    out = Path(out_jpg)
    out.parent.mkdir(parents=True, exist_ok=True)
    font_path = find_default_font()
    vf = build_thumbnail_filter(width, height, hook_title, badge=badge, font_path=font_path)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{max(0.5, timestamp_sec):.2f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "3",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out

