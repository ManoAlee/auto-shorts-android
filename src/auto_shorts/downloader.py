"""Media & transcript acquisition for mobile Termux (yt-dlp + whisper.cpp fallback)."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_source_metadata(work_dir: Path) -> Dict:
    """Read title/channel/description and YouTube Most-Replayed heatmap from .info.json."""
    for info_file in sorted(work_dir.glob("source*.info.json")):
        try:
            data = json.loads(info_file.read_text(encoding="utf-8"))
            raw_heatmap = data.get("heatmap")
            heatmap = []
            if isinstance(raw_heatmap, list):
                for pt in raw_heatmap:
                    if isinstance(pt, dict) and "start_time" in pt and "end_time" in pt:
                        heatmap.append({
                            "start_time": float(pt.get("start_time", 0.0)),
                            "end_time": float(pt.get("end_time", 0.0)),
                            "value": float(pt.get("value", 0.0)),
                        })
            return {
                "title": str(data.get("title") or "").strip(),
                "channel": str(data.get("channel") or data.get("uploader") or "").strip(),
                "description": str(data.get("description") or "").strip(),
                "webpage_url": str(data.get("webpage_url") or "").strip(),
                "heatmap": heatmap,
            }
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def is_url(target: str) -> bool:
    return target.startswith(("http://", "https://"))


def _find_downloaded_video(work_dir: Path) -> Optional[Path]:
    mp4 = work_dir / "source.mp4"
    if mp4.exists():
        return mp4
    for p in sorted(work_dir.glob("source.*")):
        if p.suffix.lower() in {".mp4", ".mkv", ".webm"}:
            return p
    return None


def download_video_and_subs(
    url: str,
    work_dir: Path,
    max_height: int = 720,
    sub_langs: str = "pt",
    cookies_path: Optional[str] = None,
) -> Tuple[Path, Optional[Path]]:
    """Download video + available subtitles via yt-dlp without requiring heavy Python libs."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_tpl = str(work_dir / "source.%(ext)s")
    fmt = (
        f"bestvideo[height<={max_height}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={max_height}][ext=mp4]/18/best"
    )

    base_cmd: List[str] = ["yt-dlp", "--no-playlist", "-f", fmt, "--merge-output-format", "mp4"]
    if shutil.which("node"):
        base_cmd.extend(["--js-runtimes", "node", "--remote-components", "ejs:github"])

    resolved_cookies = cookies_path or os.getenv("YTDLP_COOKIES", "").strip()
    if resolved_cookies:
        base_cmd.extend(["--cookies", resolved_cookies])

    sub_cmd = [
        *base_cmd,
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", sub_langs,
        "--sub-format", "vtt/srt",
        "-o", out_tpl,
        url,
    ]
    proc = subprocess.run(sub_cmd, check=False)
    video_path = _find_downloaded_video(work_dir)

    # Fallback 1: progressive MP4 via yt-dlp.
    if video_path is None:
        fallback_cmd = [
            "yt-dlp", "--no-playlist",
            "-f", f"best[height<={max_height}][ext=mp4]/18/best",
        ]
        if shutil.which("node"):
            fallback_cmd.extend(["--js-runtimes", "node", "--remote-components", "ejs:github"])
        if resolved_cookies:
            fallback_cmd.extend(["--cookies", resolved_cookies])
        fallback_cmd.extend(["-o", out_tpl, url])
        subprocess.run(fallback_cmd, check=False)
        video_path = _find_downloaded_video(work_dir)

    # Fallback 2 (GitHub pytubefix): adaptive/progressive download when yt-dlp hits 403/PO block
    if video_path is None:
        try:
            from pytubefix import YouTube  # type: ignore
            yt = YouTube(url)
            stream = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
            )
            if stream is not None:
                stream.download(output_path=str(work_dir), filename="source.mp4")
                video_path = _find_downloaded_video(work_dir)
        except Exception:
            pass

    if video_path is None:
        raise FileNotFoundError(f"yt-dlp completed with code {proc.returncode} but no video file found in {work_dir}")

    sub_candidates = sorted(
        list(work_dir.glob("source*.vtt")) + list(work_dir.glob("source*.srt"))
    )
    return video_path, (sub_candidates[0] if sub_candidates else None)


def transcribe_with_whisper_cpp(
    video_path: Path,
    work_dir: Path,
    model_path: Optional[str] = None,
    language: str = "pt",
) -> Path:
    """Extract 16kHz mono WAV and run whisper-cli (whisper.cpp ARM64 binary)."""
    whisper_bin = shutil.which("whisper-cli") or shutil.which("main")
    if not whisper_bin:
        raise RuntimeError(
            "whisper-cli not found. Install whisper.cpp via scripts/install_termux.sh or pass --srt."
        )
    resolved_model = Path(model_path) if model_path else None
    if resolved_model is None:
        for candidate in (
            Path.home() / "models" / "whisper" / "ggml-base-q5_1.bin",
            Path.home() / "models" / "whisper" / "ggml-base.bin",
            Path.home() / "whisper-models" / "ggml-base.bin",
        ):
            if candidate.exists():
                resolved_model = candidate
                break
        if resolved_model is None:
            resolved_model = Path.home() / "models" / "whisper" / "ggml-base-q5_1.bin"
    if not resolved_model.exists():
        raise FileNotFoundError(f"Whisper GGML model not found at {resolved_model}")

    wav_path = work_dir / "audio_16k.wav"
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_path),
    ]
    if os.getenv("WHISPER_FULL", "0") != "1":
        ffmpeg_cmd.extend(["-t", str(int(os.getenv("WHISPER_MAX_SEC", "240")))])
    ffmpeg_cmd.extend([
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(wav_path),
    ])
    subprocess.run(ffmpeg_cmd, check=True)

    out_prefix = work_dir / "whisper_out"
    subprocess.run(
        [
            whisper_bin,
            "-m", str(resolved_model),
            "-f", str(wav_path),
            "-l", language,
            "-osrt", "-ojf",
            "-of", str(out_prefix),
        ],
        check=True,
    )

    json_out = Path(f"{out_prefix}.json")
    if json_out.exists():
        return json_out
    srt_out = Path(f"{out_prefix}.srt")
    if srt_out.exists():
        return srt_out
    raise FileNotFoundError("whisper-cli finished without creating .json or .srt output.")
