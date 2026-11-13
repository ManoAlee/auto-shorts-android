"""Tests for ComfyUI LAN (Wan 2.2), Higgsfield fallback, and organized Google Drive paths."""

import re
from pathlib import Path

from auto_shorts.comfyui_client import (
    build_wan22_text2video_workflow,
    is_comfyui_reachable,
    try_generate_ai_hook_clip,
)
from auto_shorts.downloader import build_drive_niche_folder
from auto_shorts.higgsfield import is_higgsfield_configured


def test_wan22_workflow_vertical_9x16():
    wf = build_wan22_text2video_workflow(
        prompt="Anime cyber samurai in neon rain, dramatic camera push",
        width=480,
        height=832,
        length_frames=81,
        seed=42,
    )
    assert wf["4"]["inputs"]["text"].startswith("Anime cyber samurai")
    assert wf["6"]["inputs"]["width"] == 480
    assert wf["6"]["inputs"]["height"] == 832
    assert wf["6"]["inputs"]["length"] == 81
    assert wf["7"]["inputs"]["seed"] == 42
    assert wf["9"]["class_type"] == "VHS_VideoCombine"


def test_ai_hook_cascade_returns_none_when_unconfigured(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("COMFYUI_URL", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY", raising=False)
    monkeypatch.delenv("HIGGSFIELD_KEY", raising=False)
    assert is_comfyui_reachable() is False
    assert is_higgsfield_configured() is False
    assert try_generate_ai_hook_clip("epic space station", tmp_path) is None


def test_build_drive_niche_folder_structure():
    anime_dir = build_drive_niche_folder("entretenimento_animes")
    news_dir = build_drive_niche_folder("noticias_mundiais")
    tech_dir = build_drive_niche_folder("ia_tech")
    assert re.match(r"^gdrive:Shorts_Finalizados/Animes/\d{4}-\d{2}-\d{2}$", anime_dir)
    assert re.match(r"^gdrive:Shorts_Finalizados/Noticias_Tech/\d{4}-\d{2}-\d{2}$", news_dir)
    assert re.match(r"^gdrive:Shorts_Finalizados/Tech_IA/\d{4}-\d{2}-\d{2}$", tech_dir)

