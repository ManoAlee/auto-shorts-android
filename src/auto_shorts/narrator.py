"""Expressive natural PT-BR AI narration + word-synced subtitle builder & audio mastering.

Zero SSML pitch-shifting distortion (uses pitch=+0Hz + warm analog studio EQ),
automatic PT-BR diacritic restoration for natural pronunciation, optional
ElevenLabs / OpenAI gpt-4o-mini-tts / Chatterbox cascade, and automated validation.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import METADATA_SCRUB, QUALITY_PRESETS, get_niche_badge
from .renderer import find_default_font
from .subtitles import generate_ass_subtitles
from .thumbnail import generate_advanced_thumbnail
from .transcript import parse_srt
from .validator import validate_generated_short


@dataclass(frozen=True)
class VoiceStyle:
    key: str
    label: str
    voice: str
    rate: str
    pitch: str
    openai_voice: str = "onyx"
    elevenlabs_voice: str = "pNInz6obpgDQGcFmaJgB"
    kokoro_voice: str = "pm_alex"
    direction: str = "Fale em portugues do Brasil com voz masculina natural, acolhedora e humana."


VOICE_STYLES: Dict[str, VoiceStyle] = {
    "narrador_pro": VoiceStyle(
        key="narrador_pro",
        label="Narrador Natural PT-BR — Kokoro Alex / Antonio",
        voice="pt-BR-AntonioNeural",
        rate="+3%",
        pitch="+0Hz",
        openai_voice="onyx",
        elevenlabs_voice="pNInz6obpgDQGcFmaJgB",
        kokoro_voice="pm_alex",
        direction="Voz masculina brasileira natural, conversa de estudio com pausas reais.",
    ),
    "thalita_hd": VoiceStyle(
        key="thalita_hd",
        label="Voz Mais Humana Gratuita — Thalita Multilingual HD PT-BR",
        voice="pt-BR-ThalitaMultilingualNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="nova",
        elevenlabs_voice="EXAVITQu4vr4xnSDxMaL",
        kokoro_voice="pf_dora",
        direction="Apresentadora brasileira ultra-natural, expressiva e zero robotica.",
    ),
    "andrew_hd": VoiceStyle(
        key="andrew_hd",
        label="Narrador HD Conversacional — Andrew Multilingual (Ultra Natural)",
        voice="en-US-AndrewMultilingualNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="ash",
        elevenlabs_voice="TxGEqnHWrfWFTfGW9XjX",
        kokoro_voice="pm_alex",
        direction="Conversa humana fluida, calida e expressiva de podcast.",
    ),
    "brian_hd": VoiceStyle(
        key="brian_hd",
        label="Documentario HD Profundo — Brian Multilingual",
        voice="en-US-BrianMultilingualNeural",
        rate="+0%",
        pitch="+0Hz",
        openai_voice="onyx",
        elevenlabs_voice="pNInz6obpgDQGcFmaJgB",
        kokoro_voice="pm_santa",
        direction="Voz masculina profunda de narrador de documentario.",
    ),
    "kokoro_alex": VoiceStyle(
        key="kokoro_alex",
        label="Kokoro-82M Offline PT-BR — Alex (StyleTTS 2 Humano)",
        voice="pt-BR-AntonioNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="onyx",
        elevenlabs_voice="pNInz6obpgDQGcFmaJgB",
        kokoro_voice="pm_alex",
        direction="Sintese StyleTTS 2 local PT-BR natural sem robotizacao.",
    ),
    "dublador_anime": VoiceStyle(
        key="dublador_anime",
        label="Dublador Anime Studio — Voz Humana Dramática PT-BR (Blend Alex+Santa / Brian HD)",
        voice="en-US-BrianMultilingualNeural",
        rate="+4%",
        pitch="+0Hz",
        openai_voice="ash",
        elevenlabs_voice="ErXwobaYiN019PkySvjV",
        kokoro_voice="pm_alex",
        direction="Interpretacao cinematografica de dublador de anime brasileiro, timbre encorpado e humano.",
    ),
    "anime_hype": VoiceStyle(
        key="anime_hype",
        label="Animes & Teorias — Dublador Studio PT-BR (Kokoro Blend / Brian Multilingual HD)",
        voice="en-US-BrianMultilingualNeural",
        rate="+5%",
        pitch="+0Hz",
        openai_voice="echo",
        elevenlabs_voice="ErXwobaYiN019PkySvjV",
        kokoro_voice="pm_alex",
        direction="Voz masculina brasileira animada e envolvente de dublador para teorias de anime.",
    ),
    "authority": VoiceStyle(
        key="authority",
        label="Autoridade / Financas & Tech — Kokoro / Antonio PT-BR",
        voice="pt-BR-AntonioNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="onyx",
        elevenlabs_voice="pNInz6obpgDQGcFmaJgB",
        kokoro_voice="pm_santa",
        direction="Voz masculina confiante de especialista.",
    ),
    "storyteller": VoiceStyle(
        key="storyteller",
        label="Historias & Curiosidades — Kokoro / Antonio PT-BR",
        voice="pt-BR-AntonioNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="ash",
        elevenlabs_voice="pNInz6obpgDQGcFmaJgB",
        kokoro_voice="pm_alex",
        direction="Narracao masculina cativante e natural.",
    ),
    "podcast_female": VoiceStyle(
        key="podcast_female",
        label="Apresentadora Natural — Thalita Multilingual HD / Kokoro Dora",
        voice="pt-BR-ThalitaMultilingualNeural",
        rate="+2%",
        pitch="+0Hz",
        openai_voice="nova",
        elevenlabs_voice="EXAVITQu4vr4xnSDxMaL",
        kokoro_voice="pf_dora",
        direction="Apresentadora brasileira natural e expressiva.",
    ),
}

DEFAULT_STYLE_KEY = "narrador_pro"

_PTBR_DIACRITICS = {
    "voce": "você",
    "voces": "vocês",
    "nao": "não",
    "tambem": "também",
    "ninguem": "ninguém",
    "alguem": "alguém",
    "entao": "então",
    "episodio": "episódio",
    "episodios": "episódios",
    "historia": "história",
    "historias": "histórias",
    "animacao": "animação",
    "video": "vídeo",
    "videos": "vídeos",
    "conteudo": "conteúdo",
    "conteudos": "conteúdos",
    "incrivel": "incrível",
    "incriveis": "incríveis",
    "atencao": "atenção",
    "informacao": "informação",
    "revelacao": "revelação",
    "reacao": "reação",
    "emocao": "emoção",
    "coracao": "coração",
    "razoes": "razões",
    "milhoes": "milhões",
    "visualizacoes": "visualizações",
    "rapidos": "rápidos",
    "dinamica": "dinâmica",
    "unico": "único",
    "financas": "finanças",
    "seguranca": "segurança",
    "solucao": "solução",
    "decisao": "decisão",
    "misterio": "mistério",
}


def humanize_ptbr_script(text: str) -> str:
    """Restore Portuguese accents for natural neural pronunciation and clean breathing rhythm."""
    cleaned = " ".join(str(text or "").split()).strip()
    cleaned = re.sub(r"\s+([,;:.!?])", r"\1", cleaned)
    if not cleaned:
        return ""

    def _replace_word(match: re.Match) -> str:
        word = match.group(0)
        low = word.lower()
        fixed = _PTBR_DIACRITICS.get(low)
        if not fixed:
            return word
        if word.isupper():
            return fixed.upper()
        if word[0].isupper():
            return fixed[0].upper() + fixed[1:]
        return fixed

    restored = re.sub(r"\b[A-Za-z]+\b", _replace_word, cleaned)
    return restored


def _prepare_speech_text(text: str) -> str:
    """Normalize currency, percentages, PT-BR acronyms & breathing pauses (CosyVoice + FalaBrasil discipline)."""
    s = str(text or "").strip()
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"R\$\s*(\d+(?:[.,]\d+)?)", r"\1 reais", s)
    s = re.sub(r"US\$\s*(\d+(?:[.,]\d+)?)", r"\1 dólares", s)
    s = re.sub(r"(\d+(?:[.,]\d+)?)\s*%", r"\1 por cento", s)
    s = re.sub(r"(\d+)\s*°C\b", r"\1 graus", s)
    s = re.sub(r"\bkm/h\b", "quilômetros por hora", s, flags=re.IGNORECASE)
    acronym_map = {
        r"\bIA\b": "inteligência artificial",
        r"\bEUA\b": "Estados Unidos",
        r"\bSTF\b": "Supremo Tribunal Federal",
        r"\bPIB\b": "Píbe",
        r"\bKPI\b": "indicador",
    }
    for pat, repl in acronym_map.items():
        s = re.sub(pat, repl, s)
    s = re.sub(r"\s*[—:]\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _format_srt_time(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    ms = ms_total % 1000
    s_total = ms_total // 1000
    s = s_total % 60
    m_total = s_total // 60
    m = m_total % 60
    h = m_total // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _word_events_to_srt(events: List[Dict], max_words: int = 3) -> str:
    """Group exact WordBoundary ticks into crisp, non-overlapping SRT blocks."""
    blocks: List[Tuple[float, float, str]] = []
    buf: List[Dict] = []

    def flush() -> None:
        if not buf:
            return
        start = float(buf[0]["offset"]) / 10_000_000.0
        last = buf[-1]
        end = float(last["offset"] + last["duration"]) / 10_000_000.0
        text = " ".join(str(item["text"]).strip() for item in buf if str(item["text"]).strip())
        if text:
            blocks.append((start, max(end, start + 0.12), text))
        buf.clear()

    for ev in events:
        word = str(ev.get("text") or "").strip()
        if not word:
            continue
        buf.append({"offset": ev["offset"], "duration": ev["duration"], "text": word})
        ends_phrase = word.endswith((".", "!", "?", ";", ",")) and len(buf) >= 2
        if len(buf) >= max_words or ends_phrase:
            flush()
    flush()

    lines: List[str] = []
    prev_end = 0.0
    for idx, (start, end, text) in enumerate(blocks, 1):
        fixed_start = max(start, prev_end)
        fixed_end = max(end, fixed_start + 0.10)
        prev_end = fixed_end
        lines.append(f"{idx}\n{_format_srt_time(fixed_start)} --> {_format_srt_time(fixed_end)}\n{text}\n")
    return "\n".join(lines)


def _build_weighted_srt(script_text: str, audio_duration: float, max_words: int = 3) -> str:
    """Fallback non-overlapping character-weighted SRT aligned to real audio duration."""
    words = " ".join(str(script_text or "").split()).split()
    if not words:
        return ""
    dur = max(1.5, float(audio_duration))
    lead = 0.05 if dur > 0.6 else 0.0
    tail = 0.05 if dur > 0.6 else 0.0
    usable = max(0.8, dur - lead - tail)

    groups = [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]
    weights = [max(2, len(re.sub(r"\W+", "", g)) + (3 if g.endswith((".", "!", "?")) else 0)) for g in groups]
    total_w = float(sum(weights))

    lines: List[str] = []
    cursor = lead
    for idx, (group_text, w) in enumerate(zip(groups, weights), 1):
        span = usable * (w / total_w)
        end = min(dur, cursor + max(0.18, span))
        lines.append(f"{idx}\n{_format_srt_time(cursor)} --> {_format_srt_time(end)}\n{group_text}\n")
        cursor = end
    return "\n".join(lines)


def _probe_media_duration(media_path: Path, fallback_words: int = 10) -> float:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nk=1:nw=1",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        val = float((proc.stdout or "").strip())
        if val > 0.2:
            return val
    except Exception:
        pass
    return max(3.5, fallback_words / 2.6)


async def _edge_tts_synth_async(
    text: str,
    out_mp3: Path,
    voice: str,
    rate: str,
    pitch: str,
) -> Tuple[List[Dict], str]:
    import edge_tts

    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    async def _run(boundary: Optional[str]) -> Tuple[List[Dict], str]:
        kwargs = {"text": text, "voice": voice, "rate": rate, "pitch": pitch}
        if boundary:
            kwargs["boundary"] = boundary
        communicate = edge_tts.Communicate(**kwargs)
        events: List[Dict] = []
        submaker = edge_tts.SubMaker()
        with open(out_mp3, "wb") as audio_file:
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    audio_file.write(chunk["data"])
                elif ctype == "WordBoundary":
                    events.append(chunk)
                    submaker.feed(chunk)
                elif ctype == "SentenceBoundary":
                    submaker.feed(chunk)
        return events, submaker.get_srt()

    try:
        return await _run("WordBoundary")
    except Exception:
        return await _run(None)


def _synthesize_elevenlabs(text: str, out_mp3: Path, style: VoiceStyle, api_key: str) -> bool:
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or style.elevenlabs_voice
    model_id = os.getenv("ELEVENLABS_MODEL_ID", "").strip() or "eleven_multilingual_v2"
    payload = json.dumps({
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.42,
            "similarity_boost": 0.78,
            "style": 0.38,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out_mp3.write_bytes(resp.read())
    return True


def _synthesize_openai_tts(text: str, out_mp3: Path, style: VoiceStyle, api_key: str) -> bool:
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("OPENAI_TTS_MODEL", "").strip() or "gpt-4o-mini-tts"
    voice = os.getenv("OPENAI_TTS_VOICE", "").strip() or style.openai_voice
    body: Dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    if "gpt-4o" in model:
        body["instructions"] = style.direction
    req = urllib.request.Request(
        f"{base_url}/audio/speech",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out_mp3.write_bytes(resp.read())
    return True


def _wav_bytes_to_mp3(wav_bytes: bytes, out_mp3: Path) -> None:
    tmp_wav = out_mp3.with_suffix(".tmp.wav")
    tmp_wav.write_bytes(wav_bytes)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_wav), "-ar", "44100", "-ac", "2", "-b:a", "192k", str(out_mp3)],
            check=True,
        )
    except Exception:
        out_mp3.write_bytes(wav_bytes)
    finally:
        tmp_wav.unlink(missing_ok=True)


def resolve_open_swara_pt_ref(style_key: str = DEFAULT_STYLE_KEY) -> str:
    """Return bundled CC-BY-SA Open-Swara humanized Portuguese reference WAV path when present."""
    is_fem = style_key in {"thalita_hd", "podcast_female"}
    fname = "pt_female_ref.wav" if is_fem else "pt_male_ref.wav"
    cand = Path(__file__).resolve().parents[2] / "assets" / "voices" / fname
    return str(cand) if cand.is_file() else ""


def _synthesize_cosyvoice(text: str, out_mp3: Path, style: VoiceStyle, api_url: str) -> bool:
    """Call self-hosted CosyVoice zero-shot/instruct server using Open-Swara PT-BR reference sample."""
    ref_wav = os.getenv("COSYVOICE_REF_AUDIO", "").strip() or resolve_open_swara_pt_ref(style.key)
    payload = json.dumps({
        "tts_text": text,
        "instruct_text": style.direction,
        "prompt_wav": ref_wav,
        "speed": 1.04,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/inference_instruct2",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read()
    if raw[:4] == b"RIFF":
        _wav_bytes_to_mp3(raw, out_mp3)
    else:
        out_mp3.write_bytes(raw)
    return out_mp3.is_file() and out_mp3.stat().st_size > 256


def _synthesize_gpt_sovits(text: str, out_mp3: Path, api_url: str, style_key: str = DEFAULT_STYLE_KEY) -> bool:
    """Call GPT-SoVITS api_v2.py /tts endpoint for zero-shot human voice cloning."""
    ref_audio = os.getenv("GPT_SOVITS_REF_AUDIO", "").strip() or resolve_open_swara_pt_ref(style_key)
    if not ref_audio:
        return False
    payload = json.dumps({
        "text": text,
        "text_lang": os.getenv("GPT_SOVITS_TEXT_LANG", "pt").strip() or "pt",
        "ref_audio_path": ref_audio,
        "prompt_text": os.getenv("GPT_SOVITS_PROMPT_TEXT", "").strip(),
        "prompt_lang": os.getenv("GPT_SOVITS_PROMPT_LANG", "pt").strip() or "pt",
        "text_split_method": "cut5",
        "media_type": "wav",
        "speed_factor": 1.0,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/tts",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        _wav_bytes_to_mp3(resp.read(), out_mp3)
    return True


def _synthesize_f5_tts(text: str, out_mp3: Path, api_url: str, style_key: str = DEFAULT_STYLE_KEY) -> bool:
    """Call local/LAN F5-TTS HTTP bridge for zero-shot Flow-Matching human speech."""
    payload = json.dumps({
        "text": text,
        "ref_audio": os.getenv("F5_TTS_REF_AUDIO", "").strip() or resolve_open_swara_pt_ref(style_key),
        "ref_text": os.getenv("F5_TTS_REF_TEXT", "").strip(),
        "speed": 1.0,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/tts",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        _wav_bytes_to_mp3(resp.read(), out_mp3)
    return True


def _resolve_kokoro_paths() -> Optional[Tuple[Path, Path]]:
    """Return (model.onnx, voices.bin) when Kokoro-82M ONNX weights exist locally."""
    env_m = os.getenv("KOKORO_MODEL_PATH", "").strip()
    env_v = os.getenv("KOKORO_VOICES_PATH", "").strip()
    if env_m and env_v and Path(env_m).is_file() and Path(env_v).is_file():
        return Path(env_m), Path(env_v)
    tts_dir = Path.home() / "models" / "tts"
    voices = tts_dir / "voices-v1.0.bin"
    for cand_name in ("kokoro-v1.0.int8.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.onnx"):
        m_path = tts_dir / cand_name
        if m_path.is_file() and voices.is_file():
            return m_path, voices
    return None


def _ensure_native_espeak_for_kokoro() -> Optional[Tuple[str, str]]:
    """Locate native Termux/Linux libespeak-ng.so and shim espeakng_loader when missing."""
    import importlib.util
    import sys
    import types

    prefix = os.getenv("PREFIX", "/data/data/com.termux/files/usr")
    cand_libs = [
        os.getenv("PHONEMIZER_ESPEAK_LIBRARY", "").strip(),
        f"{prefix}/lib/libespeak-ng.so",
        "/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1",
        "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1",
    ]
    cand_data = [
        f"{prefix}/share/espeak-ng-data",
        "/usr/share/espeak-ng-data",
        "/usr/lib/x86_64-linux-gnu/espeak-ng-data",
    ]
    lib_path = next((p for p in cand_libs if p and Path(p).is_file()), "")
    data_path = next((p for p in cand_data if p and Path(p).is_dir()), "")
    if lib_path:
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", lib_path)
    if importlib.util.find_spec("espeakng_loader") is None and lib_path and data_path:
        shim = types.ModuleType("espeakng_loader")
        shim.get_library_path = lambda: lib_path  # type: ignore[attr-defined]
        shim.get_data_path = lambda: data_path  # type: ignore[attr-defined]
        sys.modules.setdefault("espeakng_loader", shim)
    try:
        import dlinfo  # type: ignore  # noqa: F401
    except Exception:
        dl_shim = types.ModuleType("dlinfo")

        class _DLInfo:
            def __init__(self, lib: object) -> None:
                self.path = getattr(lib, "_name", "") or lib_path

        dl_shim.DLInfo = _DLInfo  # type: ignore[attr-defined]
        sys.modules["dlinfo"] = dl_shim
    return (lib_path, data_path) if (lib_path and data_path) else None


_KOKORO_INSTANCES: Dict[str, object] = {}


def _split_tts_chunks(text: str, max_chars: int = 210) -> List[str]:
    """Split long PT-BR narration cleanly into sentence chunks below Kokoro's 510-phoneme limit."""
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?;:])\s+", clean) if s.strip()]
    chunks: List[str] = []
    cur = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if cur:
                chunks.append(cur)
                cur = ""
            words = sent.split()
            buf: List[str] = []
            for w in words:
                if buf and len(" ".join([*buf, w])) > max_chars:
                    chunks.append(" ".join(buf))
                    buf = [w]
                else:
                    buf.append(w)
            if buf:
                cur = " ".join(buf)
        elif not cur:
            cur = sent
        elif len(cur) + 1 + len(sent) <= max_chars:
            cur = f"{cur} {sent}"
        else:
            chunks.append(cur)
            cur = sent
    if cur:
        chunks.append(cur)
    return chunks or [clean[:max_chars]]


def _synthesize_kokoro_onnx(text: str, out_mp3: Path, style: VoiceStyle) -> bool:
    """Local offline StyleTTS2 synthesis via thewh1teagle/kokoro-onnx (PT-BR pm_alex / pf_dora)."""
    paths = _resolve_kokoro_paths()
    if not paths:
        return False
    import io
    import wave
    import numpy as np

    espeak_info = _ensure_native_espeak_for_kokoro()
    from kokoro_onnx import Kokoro  # type: ignore
    from kokoro_onnx.config import EspeakConfig  # type: ignore

    model_path, voices_path = paths
    cache_key = f"{model_path}|{voices_path}"
    kokoro = _KOKORO_INSTANCES.get(cache_key)
    if kokoro is None:
        if espeak_info:
            kokoro = Kokoro(
                str(model_path),
                str(voices_path),
                espeak_config=EspeakConfig(lib_path=espeak_info[0], data_path=espeak_info[1]),
            )
        else:
            kokoro = Kokoro(str(model_path), str(voices_path))
        # Guard against upstream kokoro-onnx 0.4.x int32 speed bug on newer float32 ONNX exports
        orig_sess = kokoro.sess
        expected_float_inputs = {i.name for i in orig_sess.get_inputs() if "float" in str(i.type).lower()}

        class _SafeSess:
            def get_inputs(self):
                return orig_sess.get_inputs()

            def run(self, output_names, input_feed, run_options=None):
                fixed = {
                    k: (np.asarray(v, dtype=np.float32) if k in expected_float_inputs else v)
                    for k, v in input_feed.items()
                }
                return orig_sess.run(output_names, fixed, run_options)

        kokoro.sess = _SafeSess()
        _KOKORO_INSTANCES[cache_key] = kokoro
    base_speed = 1.05 if "+" in style.rate else 1.01
    chunks = _split_tts_chunks(text, max_chars=185)
    audio_parts: List[object] = []
    sample_rate = 24000
    voice_arg: object = style.kokoro_voice
    if style.key in {"dublador_anime", "anime_hype", "narrador_pro", "authority", "storyteller"} and hasattr(kokoro, "get_voice_style"):
        try:
            v_alex = np.asarray(kokoro.get_voice_style("pm_alex"), dtype=np.float32)
            v_santa = np.asarray(kokoro.get_voice_style("pm_santa"), dtype=np.float32)
            weights = {
                "dublador_anime": 0.72,
                "anime_hype": 0.72,
                "narrador_pro": 0.55,
                "storyteller": 0.50,
                "authority": 0.35,
            }
            w_alex = weights.get(style.key, 0.55)
            voice_arg = (w_alex * v_alex + (1.0 - w_alex) * v_santa).astype(np.float32)
        except Exception:
            voice_arg = style.kokoro_voice
    for idx, chunk in enumerate(chunks):
        c_str = chunk.strip()
        if c_str.endswith(("!", "?")):
            dyn_speed = min(1.12, base_speed * 1.04)
        elif "..." in c_str or "—" in c_str:
            dyn_speed = max(0.94, base_speed * 0.96)
        else:
            dyn_speed = base_speed
        try:
            part, sr = kokoro.create(chunk, voice=voice_arg, speed=dyn_speed, lang="pt-br")  # type: ignore[attr-defined]
        except Exception:
            part, sr = kokoro.create(chunk, voice=style.kokoro_voice, speed=base_speed, lang="pt-br")  # type: ignore[attr-defined]
        sample_rate = int(sr)
        if len(part) > 0:
            audio_parts.append(np.asarray(part, dtype=np.float32))
            if idx < len(chunks) - 1:
                pause_sec = 0.22 if c_str.endswith(("...", "?", "!")) else 0.14
                audio_parts.append(np.zeros(int(sample_rate * pause_sec), dtype=np.float32))
    if not audio_parts:
        return False
    samples = np.concatenate(audio_parts)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    _wav_bytes_to_mp3(buf.getvalue(), out_mp3)
    return True


def _synthesize_fish_audio(text: str, out_mp3: Path, style: VoiceStyle, api_key: str = "", api_url: str = "") -> bool:
    """Call Fish Audio S1/S2 cloud API or self-hosted fish-speech server."""
    base = (api_url or "https://api.fish.audio").strip().rstrip("/")
    endpoint = f"{base}/v1/tts"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "text": text,
        "format": "mp3",
        "latency": "normal",
    }
    ref_id = os.getenv("FISH_AUDIO_VOICE_ID", "").strip()
    if ref_id:
        payload["reference_id"] = ref_id
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    if endpoint.endswith("/tts") and raw[:4] == b"RIFF":
        _wav_bytes_to_mp3(raw, out_mp3)
    else:
        out_mp3.write_bytes(raw)
    return out_mp3.is_file() and out_mp3.stat().st_size > 256


def _trim_tts_dead_air(mp3_path: Path) -> None:
    """Trim dead air and apply subtle studio vocal warmth EQ + de-esser (anti-robotic timbre)."""
    tmp = mp3_path.with_name(f"{mp3_path.stem}_trimmed.mp3")
    af_chain = (
        "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,"
        "areverse,silenceremove=start_periods=1:start_silence=0.10:start_threshold=-45dB,areverse,"
        "silenceremove=stop_periods=-1:stop_duration=0.32:stop_threshold=-42dB,"
        "highpass=f=85,equalizer=f=185:width_type=h:width=120:g=2.0,"
        "equalizer=f=6800:width_type=h:width=1800:g=-2.2,"
        "acompressor=threshold=-20dB:ratio=2.1:attack=15:release=120"
    )
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3_path),
                "-af", af_chain,
                "-ar", "44100", "-ac", "2", "-b:a", "192k", str(tmp),
            ],
            check=True,
        )
        if tmp.is_file() and tmp.stat().st_size > 1024:
            tmp.replace(mp3_path)
    except Exception:
        tmp.unlink(missing_ok=True)


def active_tts_engine_label() -> str:
    if os.getenv("ELEVENLABS_API_KEY", "").strip():
        return "ElevenLabs Multilingual v2"
    ok = os.getenv("OPENAI_API_KEY", "").strip()
    if ok and ok.lower() not in {"local", "none", "disabled"} and not ok.startswith("sk-or-") and "openrouter.ai" not in os.getenv("OPENAI_BASE_URL", "") and "127.0.0.1" not in os.getenv("OPENAI_BASE_URL", ""):
        return "OpenAI gpt-4o-mini-tts"
    if os.getenv("FISH_AUDIO_API_KEY", "").strip() or os.getenv("FISH_SPEECH_URL", "").strip():
        return "Fish Speech S1/S2 (Ultra Humano)"
    if os.getenv("COSYVOICE_API_URL", "").strip():
        return "CosyVoice 3.0 + Open-Swara PT-BR"
    if os.getenv("GPT_SOVITS_API_URL", "").strip():
        return "GPT-SoVITS Clonagem Humana"
    if os.getenv("F5_TTS_API_URL", "").strip():
        return "F5-TTS Flow-Matching Humano"
    if os.getenv("CHATTERBOX_API_URL", "").strip():
        return "Chatterbox Neural Local"
    if _resolve_kokoro_paths() is not None:
        return "Kokoro-82M PT-BR Offline (Natural)"
    return "Edge Multilingual HD + Trim de Silencio (Dica: rode install_kokoro_ptbr.sh)"


def synthesize_narration(
    script_text: str,
    out_dir: str | Path,
    style_key: str = DEFAULT_STYLE_KEY,
    stem: str = "narration",
    humanize: bool = True,
) -> Tuple[Path, Path]:
    """Generate natural expressive PT-BR voiceover MP3 + non-overlapping SRT."""
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    out_mp3 = out_root / f"{stem}.mp3"
    out_srt = out_root / f"{stem}.srt"
    base_text = humanize_ptbr_script(script_text) if humanize else " ".join(str(script_text or "").split()).strip()
    clean_text = _prepare_speech_text(base_text) if humanize else base_text
    style = VOICE_STYLES.get(style_key, VOICE_STYLES[DEFAULT_STYLE_KEY])

    eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    fish_key = os.getenv("FISH_AUDIO_API_KEY", "").strip()
    fish_url = os.getenv("FISH_SPEECH_URL", "").strip()
    cosyvoice_url = os.getenv("COSYVOICE_API_URL", "").strip()
    gpt_sovits_url = os.getenv("GPT_SOVITS_API_URL", "").strip()
    f5_tts_url = os.getenv("F5_TTS_API_URL", "").strip()
    chatterbox_url = os.getenv("CHATTERBOX_API_URL", "").strip()

    word_events: List[Dict] = []
    synthesized_external = False

    if eleven_key:
        try:
            synthesized_external = _synthesize_elevenlabs(clean_text, out_mp3, style, eleven_key)
        except Exception:
            synthesized_external = False

    if (
        not synthesized_external
        and openai_key
        and openai_key.lower() not in {"local", "none", "disabled"}
        and not openai_key.startswith("sk-or-")
        and "openrouter.ai" not in os.getenv("OPENAI_BASE_URL", "")
        and "127.0.0.1" not in os.getenv("OPENAI_BASE_URL", "")
    ):
        try:
            synthesized_external = _synthesize_openai_tts(clean_text, out_mp3, style, openai_key)
        except Exception:
            synthesized_external = False

    if not synthesized_external and (fish_key or fish_url):
        try:
            synthesized_external = _synthesize_fish_audio(clean_text, out_mp3, style, api_key=fish_key, api_url=fish_url)
        except Exception:
            synthesized_external = False

    if not synthesized_external and cosyvoice_url:
        try:
            synthesized_external = _synthesize_cosyvoice(clean_text, out_mp3, style, cosyvoice_url)
        except Exception:
            synthesized_external = False

    if not synthesized_external and gpt_sovits_url:
        try:
            synthesized_external = _synthesize_gpt_sovits(clean_text, out_mp3, gpt_sovits_url, style.key)
        except Exception:
            synthesized_external = False

    if not synthesized_external and f5_tts_url:
        try:
            synthesized_external = _synthesize_f5_tts(clean_text, out_mp3, f5_tts_url, style.key)
        except Exception:
            synthesized_external = False

    if not synthesized_external and chatterbox_url:
        try:
            payload = json.dumps({
                "input": clean_text,
                "voice": style.voice,
                "exaggeration": 0.65,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{chatterbox_url.rstrip('/')}/v1/audio/speech",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                out_mp3.write_bytes(resp.read())
            synthesized_external = True
        except Exception:
            synthesized_external = False

    if not synthesized_external:
        try:
            synthesized_external = _synthesize_kokoro_onnx(clean_text, out_mp3, style)
            if synthesized_external:
                _trim_tts_dead_air(out_mp3)
        except Exception:
            synthesized_external = False

    if not synthesized_external:
        word_events, _raw_srt = asyncio.run(
            _edge_tts_synth_async(
                text=clean_text,
                out_mp3=out_mp3,
                voice=style.voice,
                rate=style.rate,
                pitch=style.pitch,
            )
        )
        _trim_tts_dead_air(out_mp3)

    srt_content = _word_events_to_srt(word_events, max_words=3) if (word_events and not synthesized_external) else ""
    if not srt_content.strip():
        audio_dur = _probe_media_duration(out_mp3, fallback_words=len(base_text.split()))
        srt_content = _build_weighted_srt(base_text, audio_dur, max_words=3)

    out_srt.write_text(srt_content, encoding="utf-8")
    return out_mp3, out_srt


def list_clean_backgrounds(out_dir: Path) -> List[str]:
    """List raw unsubtitled candidate background MP4s relative to project root or output/."""
    work_a = sorted((out_dir / "_work").glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True) if (out_dir / "_work").is_dir() else []
    work_b = sorted((out_dir.parent / "work").glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True) if (out_dir.parent / "work").is_dir() else []
    candidates: List[Path] = [*work_a, *work_b]
    out_list: List[str] = []
    for p in candidates:
        if p.is_file():
            try:
                out_list.append(p.relative_to(out_dir.parent).as_posix())
            except ValueError:
                out_list.append(str(p))
    return out_list


def resolve_background_video(bg_video: str | Path, out_dir: Path) -> Tuple[Path, bool]:
    """Resolve background video, rotating cached gameplays cleanly without repeating."""
    from .gameplay import pick_gameplay_segment

    raw_str = str(bg_video or "").strip()
    if raw_str and raw_str.lower() not in {"auto", "gameplay"}:
        p = Path(raw_str)
        if not p.is_absolute() and not p.exists():
            alt = out_dir.parent / p
            if alt.exists():
                p = alt
        may_have_subs = "_short_" in p.name or p.name.startswith(("narrado_", "narrated_"))
        return p, may_have_subs

    picked = pick_gameplay_segment(out_dir, auto_download=(raw_str.lower() == "gameplay"))
    if picked is not None:
        return picked[0], False

    candidates = [
        out_dir / "_work" / "source.mp4",
        *sorted(out_dir.parent.glob("work/*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True),
        *[
            p for p in sorted(out_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
            if "_short_" not in p.name and not p.name.startswith(("narrado_", "narrated_", "mundo_br_"))
        ],
    ]
    for cand in candidates:
        if cand.is_file():
            return cand, False
    # Never hijack an already-rendered anime/podcast clip; generate a clean neutral studio backdrop instead.
    studio_bg = out_dir / "_work" / "clean_studio_bg.mp4"
    studio_bg.parent.mkdir(parents=True, exist_ok=True)
    if not studio_bg.is_file():
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=0x111827:s=720x1280:r=24:d=60",
                "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
                str(studio_bg),
            ],
            check=True,
        )
    return studio_bg, False


def preview_voice(
    script_text: str,
    out_dir: str | Path,
    style_key: str = DEFAULT_STYLE_KEY,
    humanize: bool = True,
) -> Dict:
    """Generate a quick voice preview MP3 for immediate playback in the mobile web UI."""
    out_root = Path(out_dir) / "_preview"
    mp3_path, srt_path = synthesize_narration(
        script_text=script_text,
        out_dir=out_root,
        style_key=style_key,
        stem="voice_preview",
        humanize=humanize,
    )
    dur = _probe_media_duration(mp3_path, fallback_words=len(script_text.split()))
    return {
        "audio_file": mp3_path.name,
        "duration": round(dur, 2),
        "style": style_key if style_key in VOICE_STYLES else DEFAULT_STYLE_KEY,
        "engine": active_tts_engine_label(),
        "cues": len(parse_srt(srt_path.read_text(encoding="utf-8")).get("segments", [])),
    }


def _has_audio_stream(media_path: Path) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                str(media_path),
            ],
            text=True,
            timeout=5,
        ).strip()
        return bool(out)
    except Exception:
        return False


def _ensure_ambient_bgm(out_root: Path) -> Optional[Path]:
    """Create a copyright-free soft ambient pad bed once for sidechain-ducked mixing."""
    bgm_file = out_root / "_bgm" / "ambient_focus.mp3"
    if bgm_file.is_file() and bgm_file.stat().st_size > 10_000:
        return bgm_file
    if not shutil.which("ffmpeg"):
        return None
    try:
        bgm_file.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "anoisesrc=d=25:c=pink:a=0.045",
                "-af", "lowpass=f=360,highpass=f=75,volume=0.22",
                "-c:a", "libmp3lame", "-b:a", "96k",
                str(bgm_file),
            ],
            check=False,
            timeout=15,
        )
        if proc.returncode == 0 and bgm_file.is_file() and bgm_file.stat().st_size > 5_000:
            return bgm_file
    except Exception:
        pass
    return None


def _build_multiscene_broll(
    out_root: Path,
    primary_bg: Path,
    primary_style: str,
    duration: float,
    work_dir: Path,
    width: int = 720,
    height: int = 1280,
) -> Tuple[Path, str]:
    """Assemble dynamic ~4.2s visual scene switches across distinct bright clips (MoneyPrinterTurbo style)."""
    try:
        if duration < 8.0 or not shutil.which("ffmpeg"):
            return primary_bg, primary_style
        if not primary_bg.is_file() or b"ftyp" not in primary_bg.read_bytes()[:64]:
            return primary_bg, primary_style
        from .gameplay import _extract_style_tag, _is_segment_visually_bright, list_gameplay_clips, probe_video_duration
        import random

        clips = [
            c for c in sorted(list_gameplay_clips(out_root), key=lambda p: p.name)
            if c.is_file() and c.stat().st_size > 50_000 and b"ftyp" in c.read_bytes()[:64]
        ]
        others = [c for c in clips if c != primary_bg and _is_segment_visually_bright(c, 5.0)]
        if not others:
            return primary_bg, primary_style
        random.shuffle(others)
        roster = [primary_bg] + others[:3]

        scene_dur = 4.2
        needed_scenes = max(2, int((duration + scene_dur - 0.1) // scene_dur))
        scene_files: List[Path] = []
        used_styles: List[str] = []
        for idx in range(min(needed_scenes, 12)):
            src = roster[idx % len(roster)]
            st_lbl = _extract_style_tag(src)
            if st_lbl and st_lbl not in used_styles:
                used_styles.append(st_lbl)
            tot = probe_video_duration(src)
            off = round(random.uniform(2.0, max(2.1, tot - scene_dur - 2.0)), 2) if tot > scene_dur + 5.0 else 0.5
            seg_mp4 = work_dir / f"_scene_{idx:02d}.mp4"
            p = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-ss", f"{off:.2f}", "-t", f"{scene_dur:.2f}",
                    "-i", str(src), "-an",
                    "-vf", f"crop='min(iw,ih*{width}/{height})':'min(ih,iw*{height}/{width})':(iw-ow)/2:(ih-oh)/2,scale={width}:{height}:flags=lanczos,setsar=1,format=yuv420p",
                    "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                    str(seg_mp4),
                ],
                check=False,
                timeout=20,
            )
            if p.returncode == 0 and seg_mp4.is_file() and seg_mp4.stat().st_size > 20_000:
                scene_files.append(seg_mp4)

        if len(scene_files) >= 2:
            concat_txt = work_dir / "_scenes.txt"
            concat_txt.write_text(
                "\n".join(f"file '{sf.resolve().as_posix()}'" for sf in scene_files),
                encoding="utf-8",
            )
            multi_mp4 = work_dir / "_multiscene_broll.mp4"
            cm = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                    "-c", "copy", str(multi_mp4),
                ],
                check=False,
                timeout=20,
            )
            if cm.returncode == 0 and multi_mp4.is_file() and multi_mp4.stat().st_size > 50_000:
                combo = "+".join(used_styles[:3]) or primary_style
                return multi_mp4, combo
    except Exception:
        pass
    return primary_bg, primary_style


def _build_narrated_title(hook_title: str, script_text: str) -> str:
    acronyms = {"ia": "IA", "arm": "ARM", "eua": "EUA", "stf": "STF", "pib": "PIB", "tv": "TV", "br": "BR", "gpt": "GPT"}
    low_connectors = {"no", "na", "nos", "nas", "do", "da", "dos", "das", "de", "em", "e", "com", "para", "por"}
    clean_hook = " ".join(str(hook_title or "").split()).strip()
    if clean_hook:
        words = []
        for idx, w in enumerate(clean_hook.split()):
            low = w.lower().strip(",.:;!?")
            if low in acronyms:
                words.append(acronyms[low])
            elif idx > 0 and low in low_connectors:
                words.append(low)
            else:
                words.append(w.capitalize())
        return " ".join(words)[:92]
    first_sentence = re.split(r"[.!?]+", humanize_ptbr_script(script_text))[0].strip()
    return (first_sentence or "Destaque em Video")[:92]


def build_narrated_short(
    bg_video: str | Path,
    script_text: str,
    out_mp4: str | Path,
    hook_title: str = "",
    style_key: str = DEFAULT_STYLE_KEY,
    quality: str = "mobile",
    bg_volume: float = 0.06,
    bg_start: float = 0.0,
    layout: str = "center_crop",
    humanize: bool = True,
    niche: str = "podcast",
    burn_hook: bool = True,
    custom_title: str = "",
) -> Dict:
    """Create a vertical 9:16 narrated short with warm studio voice mastering, ASS captions, thumbnail, and validation."""
    out_path = Path(out_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = out_path.parent / f"_narrate_{out_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    mp3_path, srt_path = synthesize_narration(
        script_text, work_dir, style_key=style_key, stem=out_path.stem, humanize=humanize
    )
    parsed = parse_srt(srt_path.read_text(encoding="utf-8"))
    audio_dur = _probe_media_duration(mp3_path, fallback_words=len(script_text.split()))
    duration = max(4.0, audio_dur, float(parsed.get("duration") or 0.0)) + 0.35

    resolved_bg, bg_has_subs = resolve_background_video(bg_video, out_path.parent)
    bg_style_used = ""
    if str(bg_video or "auto").strip().lower() in {"auto", "gameplay"}:
        from .gameplay import _extract_style_tag, pick_evolving_background
        gp_pick = pick_evolving_background(
            out_path.parent,
            niche=niche,
            topic=hook_title or script_text[:80],
            min_duration=duration,
            auto_download=(resolved_bg.name == "clean_studio_bg.mp4" or str(bg_video).lower() == "gameplay"),
        )
        if gp_pick is not None:
            resolved_bg, rand_start, bg_style_used = gp_pick
            bg_has_subs = False
            if bg_start <= 0.0:
                bg_start = rand_start
            multi_bg, multi_style = _build_multiscene_broll(
                out_path.parent, resolved_bg, bg_style_used, duration, work_dir,
                width=int(QUALITY_PRESETS.get(quality, QUALITY_PRESETS["mobile"])["width"]),
                height=int(QUALITY_PRESETS.get(quality, QUALITY_PRESETS["mobile"])["height"]),
            )
            if multi_bg != resolved_bg:
                resolved_bg = multi_bg
                bg_style_used = multi_style
                bg_start = 0.0
    elif bg_start <= 0.0 and "assets" in resolved_bg.parts:
        from .gameplay import _extract_style_tag, probe_video_duration
        import random
        bg_style_used = _extract_style_tag(resolved_bg)
        gp_tot = probe_video_duration(resolved_bg)
        if gp_tot > duration + 5.0:
            bg_start = round(random.uniform(0.0, gp_tot - duration - 2.0), 2)

    q = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["mobile"])
    width, height = int(q["width"]), int(q["height"])
    ass_path = work_dir / f"{out_path.stem}.ass"
    safe_margin_v = 245 if bg_has_subs else 185
    generate_ass_subtitles(
        parsed["segments"],
        0.0,
        duration,
        ass_path,
        width=width,
        height=height,
        max_words=3,
        margin_v=safe_margin_v,
    )

    from .renderer import build_video_filter

    vf = build_video_filter(
        layout=layout,
        width=width,
        height=height,
        ass_path=ass_path,
        hook_title=hook_title if burn_hook else "",
        font_path=find_default_font(),
        punch_zoom=1.05,
    )

    bg_input_flags = ["-stream_loop", "-1"]
    if bg_start > 0:
        bg_input_flags.extend(["-ss", f"{bg_start:.2f}"])

    # Warm broadcast speech chain: keeps crisp breath harmonics above 8.8kHz, softens 3.4kHz
    # metallic nasality, warms body at 145Hz, and levels output cleanly near -16 dB LUFS.
    voice_chain = (
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        "highpass=f=65,equalizer=f=145:t=q:w=1.0:g=2.5,equalizer=f=3400:t=q:w=1.5:g=-1.8,"
        "acompressor=threshold=-18dB:ratio=1.8:attack=15:release=110:makeup=1.2[voice_a]"
    )
    mix_chain = (
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={bg_volume:.2f}[bg_a];"
        "[voice_a][bg_a]amix=inputs=2:duration=first:weights=1 0.25:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=8[aout]"
    )

    cmd: List[str] = [
        "ffmpeg", "-y", "-loglevel", "error",
        *bg_input_flags, "-i", str(resolved_bg),
        "-i", str(mp3_path),
        "-t", f"{duration:.2f}",
        "-filter_complex", f"[0:v]{vf}[vout];{voice_chain};{mix_chain}",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", q["preset"], "-crf", q["crf"],
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        *METADATA_SCRUB,
        str(out_path),
    ]
    solo_voice_af = (
        "aformat=sample_rates=44100:channel_layouts=stereo,"
        "highpass=f=65,equalizer=f=145:t=q:w=1.0:g=2.5,equalizer=f=3400:t=q:w=1.5:g=-1.8,"
        "acompressor=threshold=-18dB:ratio=1.8:attack=15:release=110:makeup=1.2,"
        "loudnorm=I=-16:TP=-1.5:LRA=8"
    )
    no_bg_audio_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        *bg_input_flags, "-i", str(resolved_bg),
        "-i", str(mp3_path),
        "-t", f"{duration:.2f}",
        "-vf", vf,
        "-af", solo_voice_af,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", q["preset"], "-crf", q["crf"],
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        *METADATA_SCRUB,
        str(out_path),
    ]
    ambient_bgm = _ensure_ambient_bgm(out_path.parent) if (shutil.which("ffmpeg") and resolved_bg.is_file() and b"ftyp" in resolved_bg.read_bytes()[:64]) else None
    has_bg_a = bg_volume > 0.0 and _has_audio_stream(resolved_bg)
    if has_bg_a:
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            subprocess.run(no_bg_audio_cmd, check=True)
    elif ambient_bgm is not None:
        duck_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            *bg_input_flags, "-i", str(resolved_bg),
            "-i", str(mp3_path),
            "-stream_loop", "-1", "-i", str(ambient_bgm),
            "-t", f"{duration:.2f}",
            "-filter_complex", (
                f"[0:v]{vf}[vout];"
                f"{voice_chain};"
                "[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.22[bgm_raw];"
                "[voice_a]asplit=2[v_main][v_key];"
                "[bgm_raw][v_key]sidechaincompress=threshold=0.025:ratio=4:attack=20:release=240[bgm_duck];"
                "[v_main][bgm_duck]amix=inputs=2:duration=first:weights=1 0.35:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=8[aout]"
            ),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", q["preset"], "-crf", q["crf"],
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart",
            *METADATA_SCRUB,
            str(out_path),
        ]
        try:
            subprocess.run(duck_cmd, check=True)
        except subprocess.CalledProcessError:
            subprocess.run(no_bg_audio_cmd, check=True)
    else:
        subprocess.run(no_bg_audio_cmd, check=True)

    thumb_16x9 = out_path.with_name(f"{out_path.stem}_thumb_16x9.jpg")
    cover_9x16 = out_path.with_name(f"{out_path.stem}_cover_9x16.jpg")
    title = custom_title.strip()[:92] if custom_title and custom_title.strip() else _build_narrated_title(hook_title, script_text)
    badge = get_niche_badge(niche)
    thumb_ts = min(max(1.0, duration * 0.25), max(1.0, duration - 1.0))
    try:
        generate_advanced_thumbnail(out_path, thumb_16x9, hook_title or title.upper()[:36], badge=badge, timestamp_sec=thumb_ts, vertical_cover=False)
        generate_advanced_thumbnail(out_path, cover_9x16, hook_title or title.upper()[:36], badge=badge, timestamp_sec=thumb_ts, vertical_cover=True)
    except Exception:
        pass

    validation = validate_generated_short(out_path, srt_path=srt_path, ass_path=ass_path)
    human_script = humanize_ptbr_script(script_text) if humanize else script_text
    niche_tag_map = {
        "podcast": "#PodcastBrasil",
        "ia_tech": "#InteligenciaArtificial",
        "entretenimento_animes": "#Animes",
        "financas": "#Financas",
        "saude_fitness": "#Saude",
        "noticias_mundiais": "#Noticias",
    }
    niche_tag = niche_tag_map.get(niche, f"#{re.sub(r'[^A-Za-z0-9]', '', niche)}")
    tags = ["#Shorts", niche_tag, "#Tecnologia" if niche == "ia_tech" else "#Cortes", "#Brasil"]
    has_cta = any(k in human_script.lower() for k in ("comenta", "siga", "inscreva"))
    caption_body = f"{title}\n\n{human_script}\n\n"
    if not has_cta:
        caption_body += "Siga para mais cortes e curiosidades todos os dias!\n\n"
    caption = caption_body + " ".join(tags)
    pack = {
        "title": title,
        "hook_title": hook_title or title.upper()[:36],
        "caption": caption,
        "hashtags": tags,
        "niche": niche,
        "platform": "youtube_shorts",
        "output_path": str(out_path),
        "thumbnail_16x9": str(thumb_16x9) if thumb_16x9.is_file() else None,
        "cover_9x16": str(cover_9x16) if cover_9x16.is_file() else None,
        "validation": validation,
        "tts_engine": active_tts_engine_label(),
        "voice": VOICE_STYLES.get(style_key, VOICE_STYLES[DEFAULT_STYLE_KEY]).voice,
        "background_style": bg_style_used or "custom",
    }
    from .validator import audit_short_end_to_end

    visual_audit = audit_short_end_to_end(out_path, pack=pack, ass_path=ass_path, srt_path=srt_path, vision_check=False)
    if bg_style_used:
        try:
            from .evolution import EvolutionStore
            EvolutionStore(out_path.parent / "shorts_evolution.db").record_background_outcome(
                niche=niche,
                style=bg_style_used,
                quality_score=float(visual_audit.get("quality_score") or 75),
            )
        except Exception:
            pass
    pack["visual_audit"] = visual_audit
    pack["queued_for_auto_publish"] = bool(visual_audit.get("approved"))
    pack["delivery_status"] = "approved_queued" if visual_audit.get("approved") else "rejected_auto_audit"
    out_path.with_suffix(".publish.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Persist .ass alongside out_path and prune heavy intermediate _scene_*/broll MP4s immediately
    if ass_path.is_file():
        try:
            shutil.copy2(ass_path, out_path.with_suffix(".ass"))
        except OSError:
            pass
    for heavy_tmp in list(work_dir.glob("*.mp4")) + list(work_dir.glob("*.wav")):
        try:
            heavy_tmp.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "output": str(out_path),
        "title": title,
        "audio": str(mp3_path),
        "srt": str(srt_path),
        "ass": str(ass_path),
        "style": style_key if style_key in VOICE_STYLES else DEFAULT_STYLE_KEY,
        "voice": pack["voice"],
        "tts_engine": pack["tts_engine"],
        "duration": round(duration, 2),
        "background_used": str(resolved_bg),
        "background_had_subtitles_warning": bg_has_subs,
        "validation": validation,
        "visual_audit": visual_audit,
        "queued_for_auto_publish": pack["queued_for_auto_publish"],
        "delivery_status": pack["delivery_status"],
    }
