"""FFmpeg-based silence detection and jump-cut interval builder (mobile-friendly)."""

import re
import subprocess
from typing import List, Tuple


_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


def parse_silencedetect_log(stderr_text: str, total_duration: float) -> List[Tuple[float, float]]:
    """Parse ffmpeg silencedetect stderr into speech intervals [(start, end), ...]."""
    silences: List[Tuple[float, float]] = []
    cur_start: float | None = None

    for line in stderr_text.splitlines():
        m_start = _SILENCE_START_RE.search(line)
        if m_start:
            cur_start = float(m_start.group(1))
            continue
        m_end = _SILENCE_END_RE.search(line)
        if m_end and cur_start is not None:
            end = float(m_end.group(1))
            if end > cur_start:
                silences.append((cur_start, end))
            cur_start = None

    if cur_start is not None and total_duration > cur_start:
        silences.append((cur_start, total_duration))

    if not silences:
        return [(0.0, total_duration)] if total_duration > 0 else []

    keep: List[Tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        # Leave small 0.12s breathing room so cuts don't sound clipped.
        seg_end = min(total_duration, s_start + 0.12)
        if seg_end - cursor > 0.25:
            keep.append((round(cursor, 3), round(seg_end, 3)))
        cursor = max(cursor, s_end - 0.12)

    if total_duration - cursor > 0.25:
        keep.append((round(cursor, 3), round(total_duration, 3)))

    return keep or [(0.0, total_duration)]


def detect_speech_intervals(
    media_path: str,
    total_duration: float,
    noise_db: str = "-35dB",
    min_silence: float = 0.65,
) -> List[Tuple[float, float]]:
    """Run ffmpeg silencedetect on a cut clip and return active speech ranges."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", media_path,
        "-af", f"silencedetect=noise={noise_db}:d={min_silence:.2f}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return parse_silencedetect_log(proc.stderr or "", total_duration)


def remap_transcript_segments(
    segments: List[dict],
    keep_intervals: List[Tuple[float, float]],
) -> List[dict]:
    """Remap clip-relative transcript timestamps after silence removal without duplicating split segments."""
    if not keep_intervals:
        return segments

    # Precompute cumulative timeline offset per kept interval
    offsets: List[float] = []
    acc = 0.0
    for k_start, k_end in keep_intervals:
        offsets.append(acc)
        acc += (k_end - k_start)

    remapped: List[dict] = []
    for seg in segments:
        words = seg.get("words")
        if isinstance(words, list) and words:
            for (k_start, k_end), out_offset in zip(keep_intervals, offsets):
                kept_words = []
                for w in words:
                    w0, w1 = float(w["start"]), float(w["end"])
                    mid = 0.5 * (w0 + w1)
                    if k_start <= mid <= k_end:
                        kept_words.append({
                            "word": w["word"],
                            "start": round(out_offset + max(0.0, w0 - k_start), 3),
                            "end": round(out_offset + min(k_end - k_start, max(w0 - k_start + 0.04, w1 - k_start)), 3),
                        })
                if kept_words:
                    remapped.append({
                        "start": kept_words[0]["start"],
                        "end": kept_words[-1]["end"],
                        "text": " ".join(kw["word"] for kw in kept_words),
                        "words": kept_words,
                    })
            continue

        # No word timestamps: map the segment once into the kept interval with largest overlap.
        best_idx = -1
        best_ov = 0.0
        for idx, (k_start, k_end) in enumerate(keep_intervals):
            ov = min(float(seg["end"]), k_end) - max(float(seg["start"]), k_start)
            if ov > best_ov:
                best_ov = ov
                best_idx = idx
        if best_idx >= 0 and best_ov > 0.05:
            k_start, k_end = keep_intervals[best_idx]
            out_offset = offsets[best_idx]
            s0 = max(float(seg["start"]), k_start)
            s1 = min(float(seg["end"]), k_end)
            remapped.append({
                "start": round(out_offset + (s0 - k_start), 3),
                "end": round(out_offset + (s1 - k_start), 3),
                "text": seg["text"],
            })

    remapped.sort(key=lambda s: (float(s["start"]), float(s["end"])))
    return remapped

