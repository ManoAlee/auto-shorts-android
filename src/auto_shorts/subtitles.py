"""ASS animated/highlighted subtitle generator safe for FFmpeg filtergraphs."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple


ASS_HEADER = """[Script Info]
Title: AutoShorts Mobile Subtitles
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,56,56,{margin_v},1
Style: Karaoke,{font_name},{font_size},&H0015CCFA,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,56,56,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS H:MM:SS.cs timestamp."""
    total_cs = max(0, int(round(seconds * 100)))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape_ffmpeg_filter_path(path: str | Path) -> str:
    """Escape file paths for FFmpeg filter arguments (Windows/Linux safe).

    Lesson from openshorts/burned_subtitles.py: callers must keep apostrophes out
    of generated subtitle filenames because FFmpeg's filtergraph parser splits on `'`.
    """
    p = str(path).replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


def _style_caption_line(text: str) -> str:
    """Highlight focal keyword in Shorts amber-gold while keeping smooth fade-in."""
    safe = text.replace("{", "(").replace("}", ")")
    words = safe.split()
    if len(words) < 2:
        return r"{\fad(35,25)}" + safe
    focus_idx = max(range(len(words)), key=lambda i: (len(words[i].strip(".,!?;:")), i))
    styled = [
        rf"{{\c&H0015CCFA&}}{w}{{\r}}" if idx == focus_idx else w
        for idx, w in enumerate(words)
    ]
    return r"{\fad(35,25)}" + " ".join(styled)
_CLAUSE_PUNCT = tuple(",;:!?….")


def _split_into_short_lines(text: str, max_words: int = 4) -> List[str]:
    """Split text into compact groups respecting clause punctuation boundaries (OpusClip caption_cues)."""
    words = text.split()
    if not words:
        return []
    groups: List[str] = []
    cur: List[str] = []
    for w in words:
        cur.append(w)
        ends_clause = w.rstrip("\"'”’)]}").endswith(_CLAUSE_PUNCT)
        if len(cur) >= max_words or (ends_clause and len(cur) >= 2):
            groups.append(" ".join(cur))
            cur = []
    if cur:
        groups.append(" ".join(cur))
    return groups


def _style_karaoke_group(group: List[Dict], base_start: float) -> str:
    r"""Build progressive word-by-word {\kf} ASS karaoke fill + kinetic entrance pop."""
    parts: List[str] = [r"{\fad(25,20)\fscx94\fscy94\t(0,85,\fscx103\fscy103)\t(85,170,\fscx100\fscy100)}"]
    cursor = base_start
    for w in group:
        token = str(w.get("word") or "").strip().upper().replace("{", "(").replace("}", ")")
        if not token:
            continue
        w_start = max(cursor, float(w["start"]))
        w_end = max(w_start + 0.06, float(w["end"]))
        gap_cs = max(0, int(round((w_start - cursor) * 100)))
        if gap_cs > 0:
            parts.append(rf"{{\k{gap_cs}}}")
        dur_cs = max(6, int(round((w_end - w_start) * 100)))
        parts.append(rf"{{\kf{dur_cs}}}{token} ")
        cursor = w_end
    return "".join(parts).rstrip()


def _style_weighted_karaoke_phrase(phrase: str, dur_sec: float) -> str:
    r"""Build smooth progressive {\kf} karaoke animation across words when timing is chunk-level."""
    words = [w.strip() for w in phrase.replace("{", "(").replace("}", ")").split() if w.strip()]
    if not words:
        return ""
    if len(words) == 1:
        dur_cs = max(10, int(round(dur_sec * 100)))
        return rf"{{\fad(25,20)\fscx94\fscy94\t(0,85,\fscx103\fscy103)\t(85,170,\fscx100\fscy100)\kf{dur_cs}}}{words[0]}"
    weights = [max(2, len(w)) for w in words]
    tot_w = sum(weights)
    tot_cs = max(12, int(round(dur_sec * 100)))
    parts: List[str] = [r"{\fad(25,20)\fscx94\fscy94\t(0,85,\fscx103\fscy103)\t(85,170,\fscx100\fscy100)}"]
    for idx, (word, wt) in enumerate(zip(words, weights)):
        cs = max(6, int(round((wt / tot_w) * tot_cs)))
        suffix = " " if idx + 1 < len(words) else ""
        parts.append(rf"{{\kf{cs}}}{word}{suffix}")
    return "".join(parts)


def generate_ass_subtitles(
    segments: List[Dict],
    clip_start: float,
    clip_end: float,
    out_path: str | Path,
    width: int = 720,
    height: int = 1280,
    font_name: str = "DejaVu Sans",
    relative_to_clip: bool = True,
    max_words: int = 4,
    margin_v: Optional[int] = None,
) -> Path:
    """Write a bold, strictly non-overlapping TikTok/Shorts .ass subtitle file."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Compact readable Shorts proportions (~30px on 720x1280, ~45px on 1080x1920)
    scale = width / 720.0
    font_size = int(round(30 * scale))
    resolved_margin_v = int(round((margin_v if margin_v is not None else 190) * scale))

    lines = [
        ASS_HEADER.format(
            width=width,
            height=height,
            font_name=font_name,
            font_size=font_size,
            margin_v=resolved_margin_v,
        )
    ]

    cues: List[Tuple[float, float, str, str]] = []
    clip_dur = max(0.05, clip_end - clip_start)
    for seg in segments:
        words_meta = seg.get("words")
        if isinstance(words_meta, list) and words_meta:
            in_window = [
                w for w in words_meta
                if float(w["end"]) > clip_start and float(w["start"]) < clip_end
            ]
            for i in range(0, len(in_window), max(1, max_words)):
                group = in_window[i:i + max(1, max_words)]
                phrase = " ".join(str(w["word"]).strip() for w in group if str(w["word"]).strip()).upper()
                if not phrase:
                    continue
                c_start = max(0.0, float(group[0]["start"]) - clip_start) if relative_to_clip else float(group[0]["start"])
                c_end = min(clip_dur, float(group[-1]["end"]) - clip_start) if relative_to_clip else float(group[-1]["end"])
                if c_end > c_start + 0.02:
                    base_start = (c_start + clip_start) if relative_to_clip else float(group[0]["start"])
                    k_text = _style_karaoke_group(group, base_start)
                    cues.append((c_start, c_end, "Karaoke", k_text))
            continue

        s0 = float(seg["start"])
        s1 = float(seg["end"])
        if s1 <= clip_start or s0 >= clip_end:
            continue
        rel_start = max(0.0, s0 - clip_start) if relative_to_clip else s0
        rel_end = min(clip_dur, s1 - clip_start) if relative_to_clip else s1
        if rel_end <= rel_start:
            continue

        all_words = str(seg.get("text", "")).upper().split()
        if not all_words:
            continue
        # If segment starts well before clip_start, trim leading words proportionally to stay synced.
        seg_len = max(0.1, s1 - s0)
        if relative_to_clip and s0 < clip_start and seg_len > 1.0:
            skip_ratio = min(0.85, (clip_start - s0) / seg_len)
            all_words = all_words[int(round(len(all_words) * skip_ratio)):] or all_words[-max_words:]
        chunks = _split_into_short_lines(" ".join(all_words), max_words=max_words)
        if not chunks:
            continue

        chunk_dur = (rel_end - rel_start) / len(chunks)
        for idx, chunk_text in enumerate(chunks):
            c_start = rel_start + idx * chunk_dur
            c_end = rel_start + (idx + 1) * chunk_dur
            cues.append((c_start, c_end, "Karaoke", _style_weighted_karaoke_phrase(chunk_text, c_end - c_start)))

    # Guarantee zero timestamp overlap + OpusClip CUE_JOIN_SEC (0.50s) anti-flicker hold across brief breaths.
    cues.sort(key=lambda item: (item[0], item[1]))
    normalized: List[Tuple[float, float, str, str]] = []
    prev_end = 0.0
    for c_start, c_end, style_name, safe_text in cues:
        fixed_start = max(c_start, prev_end)
        fixed_end = max(c_end, fixed_start)
        if fixed_end - fixed_start < 0.04:
            continue
        if normalized and 0.0 < (fixed_start - normalized[-1][1]) <= 0.50:
            p_s, _, p_st, p_tx = normalized[-1]
            normalized[-1] = (p_s, fixed_start, p_st, p_tx)
        prev_end = fixed_end
        normalized.append((fixed_start, fixed_end, style_name, safe_text))

    for fixed_start, fixed_end, style_name, safe_text in normalized:
        lines.append(
            f"Dialogue: 0,{format_ass_time(fixed_start)},{format_ass_time(fixed_end)},{style_name},,0,0,0,,{safe_text}"
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

