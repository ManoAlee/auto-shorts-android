"""Native Android Intent dispatcher for 1-tap upload to YouTube, TikTok, and Instagram."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Dict, Optional

ANDROID_UPLOAD_COMPONENTS: Dict[str, str] = {
    "youtube": "com.google.android.youtube/com.google.android.apps.youtube.app.application.Shell_UploadActivity",
    "tiktok": "com.zhiliaoapp.musically/com.ss.android.ugc.aweme.share.SystemShareActivity",
    "instagram": "com.instagram.android/com.instagram.share.handleractivity.ShareHandlerActivity",
}


def resolve_android_component(platform: str) -> str:
    """Resolve exact Android Activity component for a target platform."""
    key = str(platform or "").strip().lower()
    if key in {"youtube", "youtube_shorts", "yt"}:
        return ANDROID_UPLOAD_COMPONENTS["youtube"]
    if key in {"tiktok", "tiktok_rewards", "tt"}:
        return ANDROID_UPLOAD_COMPONENTS["tiktok"]
    if key in {"instagram", "instagram_reels", "ig"}:
        return ANDROID_UPLOAD_COMPONENTS["instagram"]
    raise ValueError(f"Unsupported native Android target platform: {platform}")


def share_video_to_native_app(
    video_path: str | Path,
    platform: str,
    caption: str = "",
    shared_dir: str | Path = "/sdcard/Movies/AutoShorts",
) -> Dict[str, object]:
    """Copy MP4 to shared Android Movies folder, copy caption, and launch native upload Activity."""
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video not found: {src}")

    component = resolve_android_component(platform)
    dest_dir = Path(shared_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    if caption and shutil.which("termux-clipboard-set"):
        subprocess.run(["termux-clipboard-set"], input=caption, text=True, check=False)

    if shutil.which("termux-media-scan"):
        subprocess.run(["termux-media-scan", str(dest)], check=False)

    uri = f"file://{dest}"
    launched = False
    method = "prepared_only"
    if shutil.which("am"):
        proc = subprocess.run(
            [
                "am", "start",
                "-a", "android.intent.action.SEND",
                "-t", "video/mp4",
                "--eu", "android.intent.extra.STREAM", uri,
                "-n", component,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        launched = proc.returncode == 0
        method = "am_start_intent" if launched else "am_start_failed"

    if not launched and shutil.which("termux-share"):
        proc = subprocess.run(
            ["termux-share", "-a", "send", "-c", "video/mp4", str(dest)],
            capture_output=True,
            text=True,
            check=False,
        )
        launched = proc.returncode == 0
        if launched:
            method = "termux_share"

    return {
        "ok": True,
        "launched": launched,
        "method": method,
        "component": component,
        "shared_path": str(dest),
        "clipboard_set": bool(caption and shutil.which("termux-clipboard-set")),
    }
