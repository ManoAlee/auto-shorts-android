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


def is_gdrive_url(url: str) -> bool:
    """Check if URL is a Google Drive shareable link."""
    u = (url or "").lower()
    return "drive.google.com" in u or "docs.google.com" in u


def is_rclone_target(target: str) -> bool:
    """Check if target is an rclone remote path (e.g. 'gdrive:animes/ep01.mp4')."""
    t = str(target or "").strip()
    return ":" in t and not t.startswith(("http://", "https://", "file://")) and not (len(t) > 2 and t[1:3] == ":\\")


def download_from_gdrive(url: str, work_dir: Path) -> Path:
    """Download file from Google Drive via gdown or rclone."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_target = work_dir / "source.mp4"
    try:
        import gdown  # type: ignore
        res = gdown.download(url, str(out_target), quiet=False, fuzzy=True)
        if res and Path(res).is_file() and Path(res).stat().st_size > 1000:
            return Path(res)
    except Exception:
        pass

    # Fallback to rclone if configured
    if shutil.which("rclone"):
        cmd = ["rclone", "copyto", url, str(out_target)]
        subprocess.run(cmd, check=False)
        if out_target.is_file() and out_target.stat().st_size > 1000:
            return out_target

    cand = _find_downloaded_video(work_dir)
    if cand and cand.is_file():
        return cand
    raise RuntimeError(f"Falha ao baixar video do Google Drive via URL: {url}")


def download_from_rclone(remote_path: str, work_dir: Path) -> Path:
    """Download video from configured rclone remote (e.g. 'gdrive:animes/ep1.mp4')."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_target = work_dir / "source.mp4"
    rclone_bin = shutil.which("rclone")
    if not rclone_bin:
        raise RuntimeError("rclone não está instalado no sistema.")
    cmd = [rclone_bin, "copyto", remote_path, str(out_target), "--stats", "5s", "-P"]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode == 0 and out_target.is_file() and out_target.stat().st_size > 1000:
        return out_target
    cand = _find_downloaded_video(work_dir)
    if cand and cand.is_file():
        return cand
    raise RuntimeError(f"Falha ao copiar arquivo via rclone '{remote_path}' (codigo {proc.returncode})")


def upload_to_rclone(local_path: Path, remote_folder: str) -> bool:
    """Upload completed short to Google Drive via rclone."""
    rclone_bin = shutil.which("rclone")
    if not rclone_bin or not local_path.is_file():
        return False
    cmd = [rclone_bin, "copy", str(local_path), remote_folder]
    proc = subprocess.run(cmd, check=False)
    return proc.returncode == 0


def refresh_gdrive_token() -> bool:
    """Automatically refresh Google Drive OAuth2 token so it never expires."""
    rclone_bin = shutil.which("rclone")
    if not rclone_bin:
        return False
    # rclone about or lsd triggers internal automatic OAuth refresh & saves renewed token to rclone.conf
    proc = subprocess.run([rclone_bin, "about", "gdrive:"], capture_output=True, text=True, check=False)
    return proc.returncode == 0


def list_gdrive_episodes(folder: str = "gdrive:Animes_Para_Cortar") -> List[str]:
    """List pending anime video files in Google Drive folder."""
    rclone_bin = shutil.which("rclone")
    if not rclone_bin:
        return []
    cmd = [rclone_bin, "lsf", folder]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    valid_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
    files = []
    for line in proc.stdout.splitlines():
        fname = line.strip().rstrip("/")
        if any(fname.lower().endswith(ext) for ext in valid_exts):
            files.append(f"{folder.rstrip('/')}/{fname}")
    return files


def move_gdrive_episode(source_remote_path: str, dest_folder: str = "gdrive:Animes_Processados") -> bool:
    """Move processed episode within Google Drive to processed folder without downloading bytes."""
    rclone_bin = shutil.which("rclone")
    if not rclone_bin or not str(source_remote_path).strip():
        return False
    fname = Path(source_remote_path).name
    dest_path = f"{dest_folder.rstrip('/')}/{fname}"
    cmd = [rclone_bin, "moveto", source_remote_path, dest_path]
    proc = subprocess.run(cmd, check=False)
    return proc.returncode == 0


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

    # Fallback 3: direct streaming download for Archive.org and direct media links
    if video_path is None and (url.startswith("http://") or url.startswith("https://")):
        try:
            from .anime_archive_downloader import download_episode_direct
            out_mp4 = work_dir / "source.mp4"
            download_episode_direct(url, out_mp4)
            if out_mp4.is_file() and out_mp4.stat().st_size > 500000:
                video_path = out_mp4
        except Exception:
            pass

    if video_path is None:
        raise FileNotFoundError(f"yt-dlp completed with code {proc.returncode} but no video file found in {work_dir}")

    sub_candidates = sorted(
        list(work_dir.glob("source*.vtt")) + list(work_dir.glob("source*.srt"))
    )
    return video_path, (sub_candidates[0] if sub_candidates else None)


def _probe_video_duration(video_path: Path) -> float:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(video_path),
            ],
            capture_output=True, text=True, check=False, timeout=10,
        )
        return float((proc.stdout or "0").strip())
    except Exception:
        return 0.0


def _offset_whisper_json(json_path: Path, offset_sec: float) -> None:
    if offset_sec <= 0.1 or not json_path.is_file():
        return
    try:
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        offset_ms = int(round(offset_sec * 1000.0))
        for item in data.get("transcription", []):
            offs = item.get("offsets")
            if isinstance(offs, dict):
                offs["from"] = int(offs.get("from", 0)) + offset_ms
                offs["to"] = int(offs.get("to", 0)) + offset_ms
            for tok in item.get("tokens", []):
                t_offs = tok.get("offsets")
                if isinstance(t_offs, dict):
                    t_offs["from"] = int(t_offs.get("from", 0)) + offset_ms
                    t_offs["to"] = int(t_offs.get("to", 0)) + offset_ms
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


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

    total_dur = _probe_video_duration(video_path)
    # Skip opening theme/recap (first ~2m40s) on full episodes / long videos (> 6 mins)
    start_offset = 160.0 if total_dur > 360.0 else 0.0

    wav_path = work_dir / "audio_16k.wav"
    ffmpeg_cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if start_offset > 0:
        ffmpeg_cmd.extend(["-ss", f"{start_offset:.1f}"])
    ffmpeg_cmd.extend(["-i", str(video_path)])
    if os.getenv("WHISPER_FULL", "0") != "1":
        max_sec = int(os.getenv("WHISPER_MAX_SEC", "420" if total_dur > 360.0 else "240"))
        ffmpeg_cmd.extend(["-t", str(max_sec)])
    elif total_dur > 360.0:
        # Leave out the final ~100s ending credits when doing full-episode transcription
        usable_dur = max(120.0, total_dur - start_offset - 100.0)
        ffmpeg_cmd.extend(["-t", f"{usable_dur:.1f}"])
    ffmpeg_cmd.extend([
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(wav_path),
    ])
    subprocess.run(ffmpeg_cmd, check=True)

    out_prefix = work_dir / "whisper_out"
    domain_prompt = (
        "Português do Brasil. Jujutsu Kaisen, Sukuna, Gojo, Solo Leveling, Demon Slayer, Tanjiro, "
        "One Piece, Luffy, Zoro, Chainsaw Man, Attack on Titan, Yu Yu Hakusho, Yusuke, batalha, poder."
    )
    subprocess.run(
        [
            whisper_bin,
            "-m", str(resolved_model),
            "-f", str(wav_path),
            "-l", language,
            "--prompt", domain_prompt,
            "-osrt", "-ojf",
            "-of", str(out_prefix),
        ],
        check=True,
    )

    json_out = Path(f"{out_prefix}.json")
    if json_out.exists():
        _offset_whisper_json(json_out, start_offset)
        return json_out
    srt_out = Path(f"{out_prefix}.srt")
    if srt_out.exists():
        return srt_out
    raise FileNotFoundError("whisper-cli finished without creating .json or .srt output.")
