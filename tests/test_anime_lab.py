"""Tests for Phase 4: Anime & Manga Lab, 2.5D Composition & Procedural FX."""

import json
from pathlib import Path
import shutil
import struct
import subprocess
from unittest.mock import MagicMock

import pytest

from auto_shorts.anime_lab import BUILTIN_TECHNIQUES, MangaAnimeLab, MangaPanelGrammar
from auto_shorts.webapp import make_handler


def test_anime_techniques_catalog_and_sqlite(tmp_path):
    db_file = tmp_path / "anime_test.db"
    lab = MangaAnimeLab(db_path=db_file)

    techs = lab.list_techniques()
    assert len(techs) >= 4
    tech_ids = {t["technique_id"] for t in techs}
    assert "kanzen_zoom_rtl" in tech_ids
    assert "tri_layer_float" in tech_ids
    assert "shonen_speed_lines" in tech_ids

    shonen_techs = lab.list_techniques(genre="dark_shonen")
    assert any(t["technique_id"] == "kanzen_zoom_rtl" for t in shonen_techs)


def test_manga_rtl_filter_generation():
    filter_str = MangaAnimeLab.build_manga_rtl_filter(duration_sec=3.5, target_w=720, target_h=1280, fps=30)
    assert "scale=" in filter_str
    assert "zoompan=" in filter_str
    assert "720x1280" in filter_str
    assert "d=105" in filter_str  # 3.5s * 30fps


def test_tri_layer_filter_generation():
    filter_complex = MangaAnimeLab.build_tri_layer_filter(
        card_w=620, target_w=720, target_h=1280, blur_radius=25, add_speed_lines=True
    )
    assert "boxblur=" in filter_complex
    assert "drawgrid=" in filter_complex
    assert "overlay=" in filter_complex
    assert "[outv]" in filter_complex


def test_render_manga_panel_video_execution(tmp_path):
    img_path = tmp_path / "panel_test.jpg"
    out_mp4 = tmp_path / "manga_clip.mp4"

    if shutil.which("ffmpeg"):
        gen_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=0x111622:s=400x600:d=1",
            "-frames:v", "1", str(img_path),
        ]
        subprocess.run(gen_cmd, check=True)
    else:
        # Synthetic PNG stub (400x600)
        img_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            + struct.pack(">II", 400, 600)
            + b"\x08\x02\x00\x00\x00"
            + b"\x00" * 500
        )
    assert img_path.is_file()

    # 1. Render in TRI_LAYER mode
    res = MangaAnimeLab.render_manga_panel_video(
        image_path=img_path,
        out_mp4=out_mp4,
        duration_sec=1.0,
        mode="TRI_LAYER",
        add_speed_lines=True,
        quality="mobile",
    )
    assert res["ok"] is True
    assert out_mp4.is_file()
    assert res["resolution"] == "720x1280"

    # 2. Render in RTL_PAN mode
    out_rtl = tmp_path / "manga_rtl.mp4"
    res_rtl = MangaAnimeLab.render_manga_panel_video(
        image_path=img_path,
        out_mp4=out_rtl,
        duration_sec=1.0,
        mode="RTL_PAN",
        quality="mobile",
    )
    assert res_rtl["ok"] is True
    assert out_rtl.is_file()


def test_analyze_panel_and_reference_library(tmp_path):
    db_file = tmp_path / "anime_analysis_test.db"
    lab = MangaAnimeLab(db_path=db_file)

    # 1. Wide panel test (16:9 -> 1600x900)
    wide_img = tmp_path / "wide_panel.png"
    wide_img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + struct.pack(">II", 1600, 900)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00" * 500
    )
    analysis_wide = lab.analyze_panel(wide_img, name="Batalha Climax", tags="shonen,luta", license_type="PRIVATE_STUDY")
    assert analysis_wide.panel_category == "HORIZONTAL_WIDE"
    assert analysis_wide.recommended_mode == "RTL_PAN"
    assert "PAN_RIGHT_TO_LEFT" in analysis_wide.director_instructions["camera_movement"]

    # 2. Tall panel test (9:16 -> 720x1280)
    tall_img = tmp_path / "tall_panel.png"
    tall_img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + struct.pack(">II", 720, 1280)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00" * 500
    )
    analysis_tall = lab.analyze_panel(tall_img, name="Heroi Revelacao", tags="shonen,close", license_type="PROCEDURAL_ORIGINAL")
    assert analysis_tall.panel_category == "VERTICAL_TALL"
    assert analysis_tall.recommended_mode == "TRI_LAYER"

    # 3. Check reference library
    refs = lab.list_references()
    assert len(refs) == 2
    refs_tagged = lab.list_references(tag="luta")
    assert len(refs_tagged) == 1
    assert refs_tagged[0]["name"] == "Batalha Climax"


def test_webapp_anime_lab_endpoints(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    HandlerClass = make_handler(out_dir)

    # 1. Test GET /api/anime-lab/techniques
    handler_get = MagicMock(spec=HandlerClass)
    handler_get.path = "/api/anime-lab/techniques?genre=dark_shonen"
    handler_get.headers = {}
    get_res = []
    handler_get._send_json = lambda code, payload: get_res.append((code, payload))
    handler_get._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_GET(handler_get)
    assert len(get_res) == 1
    code, payload = get_res[0]
    assert code == 200
    assert payload["total"] >= 1
    assert any(t["technique_id"] == "kanzen_zoom_rtl" for t in payload["techniques"])

    # 2. Test POST /api/anime-lab/analyze-panel
    img_path = out_dir / "sample_manga_page.png"
    img_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + struct.pack(">II", 1200, 800)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00" * 500
    )

    handler_analyze = MagicMock(spec=HandlerClass)
    handler_analyze.path = "/api/anime-lab/analyze-panel"
    handler_analyze.headers = {"Content-Length": "120"}
    analyze_body = json.dumps({
        "image_filename": "sample_manga_page.png",
        "name": "Pagina Analisada",
        "tags": "manga,shonen",
    }).encode("utf-8")
    handler_analyze.rfile = MagicMock()
    handler_analyze.rfile.read = lambda n: analyze_body
    analyze_res = []
    handler_analyze._send_json = lambda code, payload: analyze_res.append((code, payload))
    handler_analyze._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_POST(handler_analyze)
    assert len(analyze_res) == 1
    a_code, a_payload = analyze_res[0]
    assert a_code == 200
    assert a_payload["ok"] is True
    assert a_payload["analysis"]["panel_category"] == "HORIZONTAL_WIDE"

    # 3. Test GET /api/anime-lab/references
    handler_refs = MagicMock(spec=HandlerClass)
    handler_refs.path = "/api/anime-lab/references"
    handler_refs.headers = {}
    refs_res = []
    handler_refs._send_json = lambda code, payload: refs_res.append((code, payload))
    handler_refs._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_GET(handler_refs)
    assert len(refs_res) == 1
    r_code, r_payload = refs_res[0]
    assert r_code == 200
    assert r_payload["total"] >= 1

    # 4. Test POST /api/anime-lab/render-panel
    handler_post = MagicMock(spec=HandlerClass)
    handler_post.path = "/api/anime-lab/render-panel"
    handler_post.headers = {"Content-Length": "120"}
    post_body = json.dumps({
        "image_filename": "sample_manga_page.png",
        "duration": 1.0,
        "mode": "TRI_LAYER",
        "add_speed_lines": True,
        "quality": "mobile",
    }).encode("utf-8")
    handler_post.rfile = MagicMock()
    handler_post.rfile.read = lambda n: post_body
    post_res = []
    handler_post._send_json = lambda code, payload: post_res.append((code, payload))
    handler_post._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_POST(handler_post)
    assert len(post_res) == 1
    p_code, p_payload = post_res[0]
    assert p_code == 200
    assert p_payload["ok"] is True
    assert p_payload["resolution"] == "720x1280"
