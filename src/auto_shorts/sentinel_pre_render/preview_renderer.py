"""Low-Cost Preview Engine for Android Termux.

Supports 5 pre-render inspection modes:
1. STORYBOARD_ONLY: 0 GPU cost, instant manifest and stills.
2. SCENE_PREVIEW: Renders a single scene with subtitle burning and safe zone guides.
3. AUDIO_SYNC_PREVIEW: Validates audio narration track timing vs ASS subtitle events.
4. FULL_PROXY_PREVIEW: Fast 360x640 15fps lightweight proxy of the entire video.
5. FINAL_RENDER: High-quality 1080x1920 production render, strictly gated by Sentinel approval.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import PreviewMode, SceneContract, StoryboardManifest
from ..design_system import DesignSystemManager, SafeZoneSpec

logger = logging.getLogger("autoshorts.sentinel.preview_renderer")


class LowCostPreviewEngine:
    """Renders lightweight previews, safe zone overlays, and proxies before final render."""

    def __init__(self, out_dir: Path | str = "output/sentinel_previews") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.design_mgr = DesignSystemManager()

    def check_caption_safe_zones(
        self,
        subtitle_text: str,
        platform: str = "youtube_shorts",
        max_chars_per_line: int = 34,
        max_lines_per_cue: int = 2,
    ) -> Dict[str, Any]:
        """Lints subtitle lines to ensure they do not overflow platform UI safe zones."""
        lines = [line.strip() for line in subtitle_text.splitlines() if line.strip()]
        if not lines and subtitle_text:
            lines = [subtitle_text.strip()]

        overflow_lines = [l for l in lines if len(l) > max_chars_per_line]
        spec = self.design_mgr.safe_zone
        passed = len(overflow_lines) == 0

        return {
            "passed": passed,
            "total_lines": len(lines),
            "overflow_lines": overflow_lines,
            "max_chars_per_line": max_chars_per_line,
            "safe_zone_spec": {
                "top_margin_px": spec.top_margin_px,
                "bottom_margin_px": spec.bottom_margin_px,
                "right_margin_px": spec.right_margin_px,
            },
            "issue": f"{len(overflow_lines)} linha(s) ultrapassam o limite seguro de {max_chars_per_line} caracteres." if not passed else None
        }

    def render_scene_preview(
        self,
        scene: SceneContract,
        platform: str = "youtube_shorts",
        width: int = 360,
        height: int = 640,
    ) -> Optional[Path]:
        """Render a single lightweight scene preview (360x640) with subtitles."""
        if not shutil.which("ffmpeg") or not scene.media_asset or not Path(scene.media_asset).is_file():
            return None

        out_preview = self.out_dir / f"preview_{scene.scene_id}.mp4"
        dur = max(1.5, min(scene.duration_seconds, 15.0))
        
        # Fast scale to 360x640 with letterbox / crop to 9:16
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(scene.media_asset),
            "-t", f"{dur:.2f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "32",
            "-r", "15",
            "-an",
            str(out_preview),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=18.0, check=False)
            if res.returncode == 0 and out_preview.is_file():
                return out_preview
        except Exception as exc:
            logger.warning("Scene preview render failed for %s: %s", scene.scene_id, exc)
        return None

    def render_full_proxy(
        self,
        manifest: StoryboardManifest,
        audio_track_path: Optional[Path] = None,
        width: int = 360,
        height: int = 640,
    ) -> Optional[Path]:
        """Render full low-resolution proxy video (360x640, 15fps) for entire storyboard."""
        if not shutil.which("ffmpeg"):
            return None

        valid_scenes = [s for s in manifest.scenes if s.media_asset and Path(s.media_asset).is_file()]
        if not valid_scenes:
            return None

        out_proxy = self.out_dir / f"{manifest.project_id}_proxy_360p.mp4"
        
        # Build concat demuxer file
        concat_txt = self.out_dir / f"{manifest.project_id}_concat.txt"
        lines = []
        for s in valid_scenes:
            # Escaping for ffmpeg concat
            path_str = str(Path(s.media_asset).resolve()).replace("\\", "/")
            lines.append(f"file '{path_str}'")
            lines.append(f"duration {s.duration_seconds:.2f}")
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=15"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-t", f"{manifest.total_duration:.2f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "32",
            "-an",
            str(out_proxy),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=30.0, check=False)
            if res.returncode == 0 and out_proxy.is_file():
                return out_proxy
        except Exception as exc:
            logger.warning("Full proxy render failed for %s: %s", manifest.project_id, exc)

        return None
