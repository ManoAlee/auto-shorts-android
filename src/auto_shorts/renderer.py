"""FFmpeg 9:16 mobile renderer with hook overlay, burned ASS captions, loudnorm, and metadata scrub."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .config import LOUDNORM_FILTER, METADATA_SCRUB, QUALITY_PRESETS
from .retention import build_pattern_interrupt_filter
from .subtitles import escape_ffmpeg_filter_path


def find_default_font() -> Optional[str]:
    """Locate a reliable TTF font across Termux/Android, Linux, and Windows."""
    candidates = [
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/system/fonts/Roboto-Bold.ttf",
        "/system/fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _format_hook_banner(raw: str, max_chars: int = 34) -> tuple[str, int]:
    """Wrap hook banner into max 2 balanced lines so text never overflows video edges."""
    words = " ".join((raw or "").split()).upper()[:max_chars].split()
    if not words:
        return "", 0
    if len(" ".join(words)) <= 18:
        line = " ".join(words)
        return line, len(line)
    mid = (len(words) + 1) // 2
    l1 = " ".join(words[:mid])
    l2 = " ".join(words[mid:])
    longest = max(len(l1), len(l2))
    text = f"{l1}\n{l2}" if l2 else l1
    return text, longest


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "")
        .replace("%", "\\%")
    )


def detect_face_crop_offset_x(source_path: str | Path, start_time: float = 0.0, end_time: float = 10.0) -> Optional[float]:
    """Detect normalized horizontal face center [0.15..0.85] for smart 9:16 framing when cv2 is available."""
    try:
        import shutil
        import tempfile
        if not shutil.which("ffmpeg"):
            return None
        import cv2  # type: ignore

        mid_ts = max(0.2, (float(start_time) + float(end_time)) * 0.5)
        with tempfile.TemporaryDirectory() as td:
            frame_jpg = Path(td) / "probe.jpg"
            proc = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-ss", f"{mid_ts:.2f}", "-i", str(source_path),
                    "-frames:v", "1", str(frame_jpg),
                ],
                check=False,
                timeout=8,
            )
            if proc.returncode != 0 or not frame_jpg.is_file():
                return None
            img = cv2.imread(str(frame_jpg))
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
            clf = cv2.CascadeClassifier(cascade_path)
            faces = clf.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(36, 36))
            if len(faces) == 0:
                return None
            # Largest foreground face wins
            x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
            cx = (x + fw * 0.5) / max(1, img.shape[1])
            return round(max(0.15, min(0.85, cx)), 3)
    except Exception:
        return None


def build_video_filter(
    layout: str,
    width: int,
    height: int,
    ass_path: Optional[Path] = None,
    hook_title: str = "",
    font_path: Optional[str] = None,
    punch_zoom: float = 1.0,
    focus_x: Optional[float] = None,
) -> str:
    """Build a single-pass FFmpeg -vf / filter_complex graph for 9:16 shorts.

    Layouts:
      - blur_bg: full landscape centered over blurred 9:16 canvas (podcasts, screencasts)
      - center_crop: 9:16 center/face-tracked crop scaled to target WxH (single talking head)
      - split_top_bottom: left & right halves stacked vertically (2-person podcasts)
    """
    if layout == "center_crop":
        if isinstance(focus_x, (int, float)) and 0.0 <= float(focus_x) <= 1.0:
            crop_x = f"max(0,min(iw-ow,iw*{float(focus_x):.3f}-ow/2))"
        else:
            crop_x = "(iw-ow)/2"
        base = (
            f"crop='min(iw,ih*{width}/{height})':'min(ih,iw*{height}/{width})':"
            f"'{crop_x}':(ih-oh)/2,scale={width}:{height}:flags=lanczos"
        )
    elif layout == "split_top_bottom":
        half_h = height // 2
        base = (
            f"split=2[left][right];"
            f"[left]crop=iw/2:ih:0:0,scale={width}:{half_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{half_h}[top];"
            f"[right]crop=iw/2:ih:iw/2:0,scale={width}:{half_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{half_h}[bot];"
            f"[top][bot]vstack=inputs=2"
        )
    else:
        # blur_bg (default): preserves all context without clipping edges.
        base = (
            f"split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=22:3[bg_blur];"
            f"[fg]scale={width}:-2:force_original_aspect_ratio=decrease[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
        )

    post_filters: List[str] = [
        "setsar=1",
        "eq=contrast=1.06:saturation=1.14",
        "unsharp=3:3:0.45:3:3:0.0",
    ]
    if punch_zoom > 1.0:
        zoom_expr = build_pattern_interrupt_filter(width, height, zoom=punch_zoom)
        if zoom_expr:
            post_filters.append(zoom_expr)

    if ass_path is not None:
        safe_ass = escape_ffmpeg_filter_path(ass_path)
        post_filters.append(f"ass='{safe_ass}'")

    if hook_title and font_path:
        banner_txt, longest = _format_hook_banner(hook_title)
        if banner_txt:
            safe_font = escape_ffmpeg_filter_path(font_path)
            safe_text = _escape_drawtext(banner_txt)
            # Dynamically fit width * 0.84 cleanly without oversized blocks on vertical canvas
            fit_px = int((width * 0.84) / max(10, longest * 0.58))
            font_size = max(19, min(int(width * 0.035), fit_px))
            y_pos = int(height * 0.068)
            bar_w = int(width * 0.42)
            bar_x = (width - bar_w) // 2
            # Vibrant amber accent rule + crisp high-contrast hook pill (never font=)
            post_filters.append(f"drawbox=x={bar_x}:y={int(height * 0.056)}:w={bar_w}:h=4:color=0xFACC15:t=fill")
            post_filters.append(
                f"drawtext=fontfile='{safe_font}':text='{safe_text}':"
                f"fontsize={font_size}:fontcolor=white:borderw=3:bordercolor=black:"
                f"box=1:boxcolor=0x0B0F19@0.80:boxborderw=10:x=(w-text_w)/2:y={y_pos}"
            )

    post_filters.append("setsar=1")
    post_filters.append("format=yuv420p")

    if ";" in base:
        return f"{base},{','.join(post_filters)}"
    return f"{base},{','.join(post_filters)}"


def build_ffmpeg_command(
    source_path: str | Path,
    out_path: str | Path,
    start_time: float,
    end_time: float,
    layout: str = "blur_bg",
    quality: str = "mobile",
    ass_path: Optional[Path] = None,
    hook_title: str = "",
    font_path: Optional[str] = None,
    encoder: str = "libx264",
    normalize_audio: bool = True,
    punch_zoom: float = 1.0,
) -> List[str]:
    """Assemble the complete FFmpeg render command for one vertical clip."""
    q = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["mobile"])
    width = int(q["width"])
    height = int(q["height"])
    focus_x = detect_face_crop_offset_x(source_path, start_time, end_time) if layout == "center_crop" else None
    vf = build_video_filter(
        layout=layout,
        width=width,
        height=height,
        ass_path=ass_path,
        hook_title=hook_title,
        font_path=font_path,
        punch_zoom=punch_zoom,
        focus_x=focus_x,
    )

    dur = max(0.1, end_time - start_time)
    cmd: List[str] = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start_time:.3f}",
        "-t", f"{dur:.3f}",
        "-i", str(source_path),
    ]

    if ";" in vf:
        cmd.extend(["-filter_complex", f"[0:v]{vf}[vout]", "-map", "[vout]", "-map", "0:a?"])
    else:
        cmd.extend(["-vf", vf])

    cmd.extend(["-fps_mode", "cfr", "-r", "30", "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p"])

    if encoder == "h264_mediacodec":
        cmd.extend(["-c:v", "h264_mediacodec", "-b:v", "4M"])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", q["preset"], "-crf", q["crf"]])

    if normalize_audio:
        cmd.extend(["-af", LOUDNORM_FILTER])

    cmd.extend([
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        *METADATA_SCRUB,
        str(out_path),
    ])
    return cmd


def cut_segment_temp(source_path: str | Path, start: float, end: float, out_path: str | Path) -> Path:
    """Extract raw subclip in strict CFR 30fps / 44.1kHz stereo prior to silence trimming."""
    dur = max(0.1, end - start)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
        "-i", str(source_path),
        "-fps_mode", "cfr", "-r", "30", "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return Path(out_path)


def build_jump_cut_filter(keep_intervals: List[Tuple[float, float]], fps: int = 30, sample_rate: int = 44100) -> str:
    """Build frame-quantized select/aselect filter keeping A/V mathematically synced."""
    terms: List[str] = []
    step = 1.0 / max(1, fps)
    for s, e in keep_intervals:
        s_q = max(0.0, round(s * fps) / fps)
        e_q = max(s_q + step, round(e * fps) / fps)
        terms.append(f"gte(t,{s_q:.4f})*lt(t,{e_q:.4f})")
    expr = "+".join(terms) if terms else "1"
    return (
        f"[0:v]select='{expr}',setpts=N/{fps}/TB[vout];"
        f"[0:a]aselect='{expr}',asetpts=N/{sample_rate}/TB[aout]"
    )


def trim_silence_concat(
    clip_path: str | Path,
    keep_intervals: List[Tuple[float, float]],
    out_path: str | Path,
) -> Path:
    """Drop long silences via sample-exact synchronized select/aselect jump cut."""
    filter_graph = build_jump_cut_filter(keep_intervals)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(clip_path),
        "-filter_complex", filter_graph,
        "-map", "[vout]", "-map", "[aout]",
        "-fps_mode", "cfr", "-r", "30", "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return Path(out_path)


def render_clip(
    source_path: str | Path,
    out_path: str | Path,
    start_time: float,
    end_time: float,
    layout: str = "blur_bg",
    quality: str = "mobile",
    ass_path: Optional[Path] = None,
    hook_title: str = "",
    encoder: str = "libx264",
    normalize_audio: bool = True,
    punch_zoom: float = 1.0,
) -> Path:
    """Render final vertical clip, falling back to libx264 if mediacodec fails."""
    font_path = find_default_font()
    cmd = build_ffmpeg_command(
        source_path=source_path,
        out_path=out_path,
        start_time=start_time,
        end_time=end_time,
        layout=layout,
        quality=quality,
        ass_path=ass_path,
        hook_title=hook_title,
        font_path=font_path,
        encoder=encoder,
        normalize_audio=normalize_audio,
        punch_zoom=punch_zoom,
    )
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        if encoder == "h264_mediacodec":
            fallback_cmd = build_ffmpeg_command(
                source_path=source_path,
                out_path=out_path,
                start_time=start_time,
                end_time=end_time,
                layout=layout,
                quality=quality,
                ass_path=ass_path,
                hook_title=hook_title,
                font_path=font_path,
                encoder="libx264",
                normalize_audio=normalize_audio,
                punch_zoom=punch_zoom,
            )
            subprocess.run(fallback_cmd, check=True)
        else:
            raise
    return Path(out_path)

