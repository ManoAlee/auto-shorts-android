"""Transcript loaders and normalizers for SRT, WebVTT (rolling + inline tags), and whisper.cpp JSON."""

import html
import json
import re
from pathlib import Path
from typing import Dict, List


_VTT_TIME_RE = re.compile(
    r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})"
)
_INLINE_WORD_TIME_RE = re.compile(r"<(?:(\d{1,2}):)?(\d{2}):(\d{2})\.(\d{3})>")
_TAG_RE = re.compile(r"<[^>]+>")
_BRACKET_NOISE_RE = re.compile(
    r"\[[^\]]*(?:__+|m[úu]sica|abertura|encerramento|aplausos|risos|music|applause|sound|efeito|ru[íi]do)[^\]]*\]|\[[^\]]*\]",
    re.IGNORECASE,
)


def _to_seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    h = int(hours) if hours else 0
    return h * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0


def _clean_caption_text(raw: str) -> str:
    text = html.unescape(_TAG_RE.sub("", raw or ""))
    text = _BRACKET_NOISE_RE.sub(" ", text)
    return " ".join(text.replace("\ufeff", "").replace("\xa0", " ").split()).strip()


def _parse_vtt_line_words(raw_line: str, seg_start: float, seg_end: float) -> List[Dict]:
    """Extract word-level timestamps from YouTube VTT inline <HH:MM:SS.mmm><c> tokens."""
    matches = list(_INLINE_WORD_TIME_RE.finditer(raw_line))
    if not matches:
        return []
    words: List[Dict] = []
    # Text before first timestamp starts at seg_start
    head = _clean_caption_text(raw_line[:matches[0].start()])
    first_ts = _to_seconds(*matches[0].groups())
    if head:
        for w in head.split():
            words.append({"word": w, "start": round(seg_start, 3), "end": round(max(seg_start + 0.05, first_ts), 3)})

    for idx, m in enumerate(matches):
        w_start = _to_seconds(*m.groups())
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_line)
        w_end = _to_seconds(*matches[idx + 1].groups()) if idx + 1 < len(matches) else seg_end
        chunk = _clean_caption_text(raw_line[m.end():body_end])
        if not chunk:
            continue
        parts = chunk.split()
        step = max(0.05, w_end - w_start) / len(parts)
        for p_idx, part in enumerate(parts):
            ws = w_start + p_idx * step
            we = w_start + (p_idx + 1) * step
            words.append({"word": part, "start": round(ws, 3), "end": round(max(ws + 0.04, we), 3)})
    return words


def _strip_word_overlap(prev_words: List[str], cur_words: List[str]) -> List[str]:
    """Drop prefix of cur_words that repeats the suffix of prev_words (YouTube rolling overlap)."""
    if not prev_words or not cur_words:
        return cur_words
    prev_l = [w.lower() for w in prev_words]
    cur_l = [w.lower() for w in cur_words]
    max_k = min(len(prev_l), len(cur_l))
    for k in range(max_k, 0, -1):
        if prev_l[-k:] == cur_l[:k]:
            return cur_words[k:]
    return cur_words


def _iter_cue_blocks(content: str) -> List[tuple[float, float, List[str]]]:
    """Iterate WebVTT/SRT cues cleanly by timestamp headers (resilient to blank space lines inside cues)."""
    cues: List[tuple[float, float, List[str]]] = []
    cur_start: float | None = None
    cur_end: float | None = None
    cur_lines: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        match = _VTT_TIME_RE.search(line)
        if match:
            if cur_start is not None and cur_end is not None and cur_lines:
                cues.append((cur_start, cur_end, cur_lines))
            cur_start = _to_seconds(*match.groups()[:4])
            cur_end = _to_seconds(*match.groups()[4:])
            cur_lines = []
            continue
        if cur_start is None:
            continue
        if not line or line.isdigit():
            continue
        cur_lines.append(line)

    if cur_start is not None and cur_end is not None and cur_lines:
        cues.append((cur_start, cur_end, cur_lines))
    return cues


def parse_srt(content: str) -> Dict:
    """Parse SRT subtitle text into {duration, segments}."""
    segments: List[Dict] = []
    for start, end, lines in _iter_cue_blocks(content):
        text = _clean_caption_text(" ".join(lines))
        if text and end > start:
            segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    duration = segments[-1]["end"] if segments else 0.0
    return {"duration": duration, "segments": segments}


def parse_vtt(content: str) -> Dict:
    """Parse WebVTT (including YouTube 2-line rolling auto-captions) without duplicating lines."""
    segments: List[Dict] = []
    rolling_tail: List[str] = []

    for start, end, body_lines in _iter_cue_blocks(content):
        if end <= start:
            continue

        # YouTube emits 10ms static duplicate cues between rolling word cues; ignore if <=80ms and plain text.
        has_inline_times = any(_INLINE_WORD_TIME_RE.search(ln) for ln in body_lines)
        if (end - start) <= 0.08 and not has_inline_times and segments:
            continue

        cleaned_lines = [_clean_caption_text(ln) for ln in body_lines]
        cleaned_lines = [ln for ln in cleaned_lines if ln]
        if not cleaned_lines:
            continue

        # When YouTube sends inline word timestamps on the last line, Line 1 is always the previous echoed line.
        active_raw = body_lines[-1] if has_inline_times else " ".join(cleaned_lines)
        words_data = _parse_vtt_line_words(active_raw, start, end) if has_inline_times else []
        cand_text = _clean_caption_text(active_raw)
        if not cand_text:
            continue

        cand_words = cand_text.split()
        # Handle cumulative extension of the immediately preceding cue
        if segments and cand_text == segments[-1]["text"]:
            segments[-1]["end"] = round(max(segments[-1]["end"], end), 3)
            continue
        if segments and cand_text.startswith(segments[-1]["text"]) and len(cand_text) > len(segments[-1]["text"]):
            segments[-1]["text"] = cand_text
            segments[-1]["end"] = round(max(segments[-1]["end"], end), 3)
            if words_data:
                segments[-1]["words"] = words_data
            rolling_tail = (rolling_tail + cand_words)[-32:]
            continue

        novel_words = _strip_word_overlap(rolling_tail, cand_words)
        if not novel_words:
            continue
        novel_text = " ".join(novel_words)
        seg: Dict = {"start": round(start, 3), "end": round(end, 3), "text": novel_text}
        if words_data:
            skip_n = len(cand_words) - len(novel_words)
            kept_w = words_data[skip_n:]
            if kept_w:
                seg["words"] = kept_w
                seg["start"] = kept_w[0]["start"]
        segments.append(seg)
        rolling_tail = (rolling_tail + novel_words)[-32:]

    duration = segments[-1]["end"] if segments else 0.0
    return {"duration": duration, "segments": segments}


def parse_whisper_cpp_json(content: str) -> Dict:
    """Parse whisper.cpp -oj / -ojf JSON output into {duration, segments}, merging BPE subwords cleanly."""
    data = json.loads(content)
    segments: List[Dict] = []
    for item in data.get("transcription", []):
        offsets = item.get("offsets", {})
        start = float(offsets.get("from", 0)) / 1000.0
        end = float(offsets.get("to", 0)) / 1000.0
        text = _clean_caption_text(item.get("text", ""))
        if text and end > start:
            seg: Dict = {"start": round(start, 3), "end": round(end, 3), "text": text}
            tokens = item.get("tokens")
            if isinstance(tokens, list) and tokens:
                words: List[Dict] = []
                for tok in tokens:
                    raw_tok = html.unescape(str(tok.get("text", "")))
                    if not raw_tok.strip() or raw_tok.strip().startswith("[_"):
                        continue
                    t_off = tok.get("offsets", {})
                    w_start = round(float(t_off.get("from", 0)) / 1000.0, 3)
                    w_end = round(float(t_off.get("to", 0)) / 1000.0, 3)
                    clean_piece = _clean_caption_text(raw_tok)
                    if not clean_piece:
                        continue
                    # BPE tokens without a leading space (or bare punctuation) continue the previous word.
                    starts_new_word = raw_tok[0].isspace() or not words
                    is_bare_punct = all(ch in ".,!?;:—-\"'" for ch in clean_piece)
                    if words and (not starts_new_word or is_bare_punct):
                        words[-1]["word"] += clean_piece
                        words[-1]["end"] = max(words[-1]["end"], w_end)
                    else:
                        words.append({
                            "word": clean_piece,
                            "start": w_start,
                            "end": max(w_start + 0.04, w_end),
                        })
                if words:
                    seg["words"] = words
                    seg["text"] = " ".join(w["word"] for w in words)
            segments.append(seg)
    duration = segments[-1]["end"] if segments else 0.0
    return {"duration": duration, "segments": segments}


def load_transcript(path: str | Path) -> Dict:
    """Load transcript from .srt, .vtt, or whisper.cpp .json file."""
    p = Path(path)
    content = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return parse_whisper_cpp_json(content)
    if suffix == ".vtt":
        return parse_vtt(content)
    return parse_srt(content)


def format_transcript_for_llm(segments: List[Dict]) -> str:
    """Render transcript segments with [start - end] timestamps for LLM prompt."""
    return "\n".join(
        f"[{seg['start']:.1f} - {seg['end']:.1f}] {seg['text']}"
        for seg in segments
    )
