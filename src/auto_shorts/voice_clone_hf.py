"""Zero-cost PT-BR voice cloning via HuggingFace Chatterbox-Multilingual-TTS-pt-br Space."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import List, Optional

DEFAULT_SPACE_ID = "ResembleAI/Chatterbox-Multilingual-TTS-pt-br"
MAX_CHUNK_CHARS = 260


def split_text_for_chatterbox(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split PT-BR narration into <= max_chars sentence chunks without cutting words."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    chunks: List[str] = []
    cur = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) > max_chars:
            # Break long sentence at word boundaries
            words = sent.split()
            for w in words:
                cand = f"{cur} {w}".strip() if cur else w
                if len(cand) <= max_chars:
                    cur = cand
                else:
                    if cur:
                        chunks.append(cur)
                    cur = w
            continue
        cand = f"{cur} {sent}".strip() if cur else sent
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = sent
    if cur:
        chunks.append(cur)
    return chunks


def resolve_user_voice_ref() -> Optional[Path]:
    """Locate the cleaned 24kHz user voice reference WAV."""
    env_p = os.getenv("USER_VOICE_CLONE_WAV", "").strip()
    if env_p and Path(env_p).is_file():
        return Path(env_p)
    repo_root = Path(__file__).resolve().parents[2]
    default_p = repo_root / "assets" / "voice_clone" / "alessandro_voice_24k.wav"
    return default_p if default_p.is_file() else None


def synthesize_chatterbox_hf_space(
    text: str,
    out_mp3: Path,
    ref_wav: Optional[Path] = None,
    space_id: str = DEFAULT_SPACE_ID,
) -> bool:
    """Synthesize cloned PT-BR speech via free HuggingFace Chatterbox Space + FFmpeg concat."""
    ref = ref_wav or resolve_user_voice_ref()
    if ref is None or not ref.is_file():
        return False

    try:
        from gradio_client import Client, handle_file  # type: ignore
    except ImportError:
        return False

    chunks = split_text_for_chatterbox(text)
    if not chunks:
        return False

    token = os.getenv("HF_TOKEN", "").strip().strip('"').strip("'") or None
    client = Client(space_id, token=token)
    ref_handle = handle_file(str(ref))

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        wav_parts: List[Path] = []
        for idx, chunk in enumerate(chunks):
            gen_path = client.predict(
                text_input=chunk,
                audio_prompt_path_input=ref_handle,
                exaggeration_input=0.55,
                temperature_input=0.75,
                seed_num_input=0,
                cfgw_input=0.5,
                api_name="/generate_tts_audio",
            )
            part_src = Path(str(gen_path))
            if not part_src.is_file() or part_src.stat().st_size < 1000:
                return False
            wav_parts.append(part_src)

        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        if len(wav_parts) == 1:
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(wav_parts[0]),
                "-ar", "44100", "-ac", "1", "-b:a", "192k",
                str(out_mp3),
            ]
        else:
            concat_txt = tmp_root / "parts.txt"
            concat_txt.write_text(
                "\n".join(f"file '{str(p).replace(chr(39), '')}'" for p in wav_parts),
                encoding="utf-8",
            )
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-ar", "44100", "-ac", "1", "-b:a", "192k",
                str(out_mp3),
            ]
        subprocess.run(cmd, check=True)

    return out_mp3.is_file() and out_mp3.stat().st_size > 1500
