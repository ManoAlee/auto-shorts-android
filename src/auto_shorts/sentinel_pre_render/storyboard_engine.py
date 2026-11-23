"""Storyboard-First Production Engine.

Builds pre-render storyboard manifests, representative frame extracts, contact sheets,
and interactive visual HTML reviews before executing any heavy video compilation.
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

from .contracts import SceneContract, StoryboardManifest

logger = logging.getLogger("autoshorts.sentinel.storyboard_engine")


class StoryboardEngine:
    """Orchestrates storyboard construction, contact sheet mosaic, and visual inspection."""

    def __init__(self, out_dir: Path | str = "output/sentinel_previews") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.stills_dir = self.out_dir / "stills"
        self.stills_dir.mkdir(parents=True, exist_ok=True)

    def extract_scene_frame(
        self,
        media_path: Path | str,
        out_frame_path: Path,
        seek_sec: float = 1.0,
    ) -> bool:
        """Extract a clean representative visual still from a video asset or copy an image."""
        src = Path(media_path)
        if not src.is_file():
            return False

        out_frame_path.parent.mkdir(parents=True, exist_ok=True)
        ext = src.suffix.lower()

        # If already an image, copy/resize
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            try:
                shutil.copyfile(src, out_frame_path)
                return True
            except OSError:
                return False

        # Extract frame via ffmpeg
        if not shutil.which("ffmpeg"):
            return False

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{seek_sec:.2f}",
            "-i", str(src),
            "-frames:v", "1",
            "-q:v", "3",
            str(out_frame_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=12.0, check=False)
            return res.returncode == 0 and out_frame_path.is_file()
        except Exception as exc:
            logger.warning("Failed to extract frame from %s: %s", src, exc)
            return False

    def generate_contact_sheet(
        self,
        manifest: StoryboardManifest,
        grid: str = "3x2",
        thumb_width: int = 240,
    ) -> Optional[Path]:
        """Combine representative scene stills into a single contact sheet image mosaic."""
        stills = [Path(s.representative_frame) for s in manifest.scenes if s.representative_frame and Path(s.representative_frame).is_file()]
        if not stills:
            return None

        out_sheet = self.out_dir / f"{manifest.project_id}_contact_sheet.jpg"
        
        # If FFmpeg is available and we have multiple stills, tile them
        if shutil.which("ffmpeg") and len(stills) >= 2:
            try:
                inputs = []
                for st in stills[:6]:
                    inputs.extend(["-i", str(st)])
                
                num_in = min(len(stills), 6)
                # Build xstack or vstack filter
                filter_complex = "".join(f"[{i}:v]scale={thumb_width}:426[v{i}];" for i in range(num_in))
                if num_in == 2:
                    filter_complex += "[v0][v1]hstack=inputs=2[out]"
                elif num_in == 3:
                    filter_complex += "[v0][v1][v2]hstack=inputs=3[out]"
                elif num_in == 4:
                    filter_complex += "[v0][v1]hstack[row1];[v2][v3]hstack[row2];[row1][row2]vstack[out]"
                else:
                    filter_complex += "[v0][v1][v2]hstack=inputs=3[row1];[v3][v4]hstack=inputs=2[row2];[row1][row2]vstack[out]"

                cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[out]", "-q:v", "3", str(out_sheet)]
                res = subprocess.run(cmd, capture_output=True, timeout=15.0, check=False)
                if res.returncode == 0 and out_sheet.is_file():
                    return out_sheet
            except Exception as exc:
                logger.warning("Contact sheet tiling failed: %s", exc)

        # Fallback: copy first still
        try:
            shutil.copyfile(stills[0], out_sheet)
            return out_sheet
        except OSError:
            return None

    def generate_html_storyboard(self, manifest: StoryboardManifest) -> Path:
        """Create a clean, responsive HTML visual inspection board for the planned video."""
        out_html = self.out_dir / f"{manifest.project_id}_storyboard.html"

        scenes_html = []
        for idx, sc in enumerate(manifest.scenes, 1):
            badge_color = "#10b981" if sc.validation_status == "PASS" else ("#f59e0b" if sc.validation_status == "REQUIRES_REVIEW" else "#ef4444")
            still_rel = Path(sc.representative_frame).name if sc.representative_frame else ""
            img_tag = f'<img src="stills/{still_rel}" alt="Frame {idx}" class="thumb">' if still_rel else '<div class="no-thumb">Sem Frame</div>'

            scenes_html.append(f"""
            <div class="scene-card" id="{sc.scene_id}">
                <div class="scene-header">
                    <span class="scene-idx">Cena {idx} ({sc.scene_id})</span>
                    <span class="scene-time">{sc.timestamp_start:.1f}s - {sc.timestamp_end:.1f}s ({sc.duration_seconds:.1f}s)</span>
                    <span class="badge" style="background-color: {badge_color}">{sc.validation_status} ({sc.alignment_score}/100)</span>
                </div>
                <div class="scene-body">
                    <div class="thumb-container">
                        {img_tag}
                        <div class="asset-label">{Path(sc.media_asset).name}</div>
                    </div>
                    <div class="scene-info">
                        <p class="narration"><strong>Narração:</strong> "{sc.narration}"</p>
                        <p class="intent"><strong>Intenção Visual:</strong> {sc.visual_intent}</p>
                        <p class="objects"><strong>Objetos Esperados:</strong> {", ".join(sc.expected_objects) or "Nenhum"}</p>
                        {f'<p class="notes" style="color: #ef4444"><strong>Observações:</strong> {"; ".join(sc.alignment_notes)}</p>' if sc.alignment_notes else ''}
                    </div>
                </div>
            </div>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoShorts Sentinel — Storyboard: {manifest.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ font-size: 22px; color: #38bdf8; margin-bottom: 6px; }}
        .meta {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
        .scene-card {{ background: #1e293b; border-radius: 8px; border: 1px solid #334155; margin-bottom: 16px; overflow: hidden; }}
        .scene-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: #0f172a; border-bottom: 1px solid #334155; }}
        .scene-idx {{ font-weight: bold; font-size: 15px; color: #f8fafc; }}
        .scene-time {{ color: #94a3b8; font-size: 13px; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: #fff; }}
        .scene-body {{ display: flex; gap: 16px; padding: 14px 16px; }}
        .thumb-container {{ width: 140px; flex-shrink: 0; text-align: center; }}
        .thumb {{ width: 140px; height: 248px; object-fit: cover; border-radius: 6px; background: #000; }}
        .no-thumb {{ width: 140px; height: 248px; background: #334155; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 12px; color: #94a3b8; }}
        .asset-label {{ font-size: 11px; color: #94a3b8; margin-top: 6px; word-break: break-all; }}
        .scene-info {{ flex: 1; font-size: 14px; line-height: 1.5; }}
        .narration {{ color: #e2e8f0; margin: 0 0 8px 0; }}
        .intent {{ color: #cbd5e1; margin: 0 0 8px 0; }}
        .objects {{ color: #94a3b8; margin: 0 0 8px 0; font-size: 13px; }}
        .notes {{ margin: 0; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Storyboard Pre-Render: {manifest.title}</h1>
        <div class="meta">Projeto: {manifest.project_id} • Duração Planejada: {manifest.total_duration:.1f}s • {len(manifest.scenes)} Cenas</div>
        {''.join(scenes_html)}
    </div>
</body>
</html>"""
        out_html.write_text(html_content, encoding="utf-8")
        return out_html

    def build_storyboard(
        self,
        project_id: str,
        title: str,
        scenes: List[SceneContract],
    ) -> StoryboardManifest:
        """Construct the complete storyboard manifest and inspect all scene frames."""
        total_duration = sum(s.duration_seconds for s in scenes)
        
        # Extract frame stills for each scene
        for idx, sc in enumerate(scenes, 1):
            still_name = f"{project_id}_scene_{idx:02d}.jpg"
            still_path = self.stills_dir / still_name
            if sc.media_asset and Path(sc.media_asset).is_file():
                success = self.extract_scene_frame(sc.media_asset, still_path, seek_sec=min(1.0, sc.duration_seconds / 2))
                if success:
                    sc.representative_frame = str(still_path)

        manifest = StoryboardManifest(
            project_id=project_id,
            title=title,
            total_duration=total_duration,
            scenes=scenes,
        )

        # Generate contact sheet and HTML inspection board
        sheet_path = self.generate_contact_sheet(manifest)
        if sheet_path:
            manifest.contact_sheet_path = str(sheet_path)

        html_path = self.generate_html_storyboard(manifest)
        manifest.html_preview_path = str(html_path)

        # Save manifest JSON
        manifest_json_path = self.out_dir / f"{project_id}_storyboard.json"
        manifest_json_path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        return manifest
