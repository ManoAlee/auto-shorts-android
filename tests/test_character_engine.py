"""Tests for Phase 3: Character Engine, Visual Identity & Drift Detection."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auto_shorts.character_engine import (
    CharacterBibleEntry,
    CharacterDatabase,
    CharacterVisualAuditor,
    CostumeDetails,
    PhysicalTraits,
)
from auto_shorts.webapp import make_handler


def test_character_bible_entry_and_prompt_compilation():
    phy = PhysicalTraits(
        gender="MALE",
        apparent_age=22,
        height_build="Alto atlético",
        hair_color="Prateado",
        hair_style="Longo amarrado",
        eye_color="Vermelho carmesim",
        skin_tone="Pálido",
        distinguishing_features="Marca de maldição no pescoço",
    )
    cos = CostumeDetails(
        primary_outfit="Quimono escuro de combate",
        secondary_elements="Faixa vermelha na cintura",
        accessories="Espada selada nas costas",
        color_palette_hex=["#101015", "#E63946", "#F1FAEE"],
    )
    entry = CharacterBibleEntry(
        char_id="char_kage_01",
        name="Kage",
        role="ANTAGONIST",
        archetype="Espadachim Maldito",
        personality_summary="Frio, calculista e impiedoso",
        physical=phy,
        costume=cos,
        voice_key="pm_santa",
        expressions_map={"ENRAGED": "olhar assassino com veias pulsando"},
        poses_map={"COMBAT_READY": "empunhando a lâmina com as duas mãos em guarda baixa"},
    )

    data = entry.to_dict()
    assert data["char_id"] == "char_kage_01"
    assert data["physical"]["hair_color"] == "Prateado"
    assert data["costume"]["color_palette_hex"][1] == "#E63946"

    # Test prompt compilation
    compiled = entry.compile_visual_prompt(expression="ENRAGED", pose="COMBAT_READY")
    assert "Kage" in compiled
    assert "Prateado" in compiled
    assert "olhar assassino" in compiled
    assert "empunhando a lâmina" in compiled
    assert "9:16" in compiled


def test_character_database_crud_and_appearances(tmp_path):
    db_file = tmp_path / "char_test.db"
    cdb = CharacterDatabase(db_path=db_file)

    entry = CharacterBibleEntry(
        char_id="char_ren_test",
        name="Ren",
        role="PROTAGONIST",
        archetype="Herói Shonen",
        personality_summary="Determinado e leal",
        voice_key="pm_alex",
    )
    cdb.save_character(entry)

    loaded = cdb.get_character("char_ren_test")
    assert loaded is not None
    assert loaded.name == "Ren"
    assert loaded.voice_key == "pm_alex"

    all_chars = cdb.list_all_characters()
    assert len(all_chars) == 1
    assert all_chars[0].char_id == "char_ren_test"

    # Record appearance
    cdb.record_appearance("char_ren_test", story_id="story_01", season=1, episode=1, scene_id=3)
    updated = cdb.get_character("char_ren_test")
    assert len(updated.appearance_history) == 1
    assert updated.appearance_history[0]["episode"] == 1
    assert updated.appearance_history[0]["scene_id"] == 3


def test_palette_alignment_and_drift_detection():
    # Synthetic RGB bytes matching dark black (#0B0E14 -> 11, 14, 20)
    dark_pixel = bytes([12, 15, 21]) * 400
    res_match = CharacterVisualAuditor.analyze_frame_palette_alignment(
        dark_pixel, target_palette_hex=["#0B0E14", "#00F0FF"]
    )
    assert res_match["passed"] is True
    assert res_match["status"] == "CONSISTENT"
    assert res_match["match_percentage"] >= 90.0

    # Synthetic RGB bytes matching bright yellow (#FFFF00 -> 255, 255, 0) - should drift
    yellow_pixel = bytes([255, 255, 0]) * 400
    res_drift = CharacterVisualAuditor.analyze_frame_palette_alignment(
        yellow_pixel, target_palette_hex=["#0B0E14", "#00F0FF"]
    )
    assert res_drift["passed"] is False
    assert res_drift["status"] == "PALETTE_DRIFT_DETECTED"
    assert res_drift["match_percentage"] < 5.0


def test_scene_continuity_pixel_comparator():
    frame_a = bytes([50] * 1024)
    frame_b_similar = bytes([58] * 1024)
    frame_c_drastic = bytes([230] * 1024)

    # Similar frames (healthy motion delta)
    res_healthy = CharacterVisualAuditor.compare_scene_frames_consistency(frame_a, frame_b_similar)
    assert res_healthy["status"] == "HEALTHY_CONTINUITY"
    assert res_healthy["continuity_score"] >= 90

    # Drastic frames (jarring break)
    res_break = CharacterVisualAuditor.compare_scene_frames_consistency(frame_a, frame_c_drastic)
    assert res_break["status"] == "EXTREME_DISCONTINUITY"
    assert res_break["continuity_score"] <= 60


def test_webapp_character_endpoints(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    HandlerClass = make_handler(out_dir)

    # 1. POST /api/character/create
    handler_post = MagicMock(spec=HandlerClass)
    handler_post.path = "/api/character/create"
    handler_post.headers = {"Content-Length": "200"}
    post_body = json.dumps({
        "char_id": "char_yuki_test",
        "name": "Yuki",
        "role": "MENTOR",
        "archetype": "Cientista Hacker",
        "personality": "Fria e genial",
        "voice_key": "pf_dora",
        "physical": {"hair_color": "Branco", "eye_color": "Violeta"},
        "costume": {"primary_outfit": "Jaleco cibernético"},
    }).encode("utf-8")
    handler_post.rfile = MagicMock()
    handler_post.rfile.read = lambda n: post_body
    post_responses = []
    handler_post._send_json = lambda code, payload: post_responses.append((code, payload))
    handler_post._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_POST(handler_post)
    assert len(post_responses) == 1
    code, payload = post_responses[0]
    assert code == 200
    assert payload["ok"] is True
    assert payload["character"]["name"] == "Yuki"

    # 2. GET /api/character/list
    handler_get = MagicMock(spec=HandlerClass)
    handler_get.path = "/api/character/list"
    handler_get.headers = {}
    get_responses = []
    handler_get._send_json = lambda code, payload: get_responses.append((code, payload))
    handler_get._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_GET(handler_get)
    assert len(get_responses) == 1
    g_code, g_payload = get_responses[0]
    assert g_code == 200
    assert g_payload["total"] >= 1
    assert any(c["char_id"] == "char_yuki_test" for c in g_payload["characters"])

    # 3. POST /api/character/prompt
    prompt_post = MagicMock(spec=HandlerClass)
    prompt_post.path = "/api/character/prompt"
    prompt_post.headers = {"Content-Length": "100"}
    prompt_body = json.dumps({
        "char_id": "char_yuki_test",
        "expression": "INTENSE_FOCUS",
        "pose": "COMBAT_READY",
    }).encode("utf-8")
    prompt_post.rfile = MagicMock()
    prompt_post.rfile.read = lambda n: prompt_body
    prompt_res = []
    prompt_post._send_json = lambda code, payload: prompt_res.append((code, payload))
    prompt_post._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_POST(prompt_post)
    assert len(prompt_res) == 1
    pr_code, pr_payload = prompt_res[0]
    assert pr_code == 200
    assert "Yuki" in pr_payload["compiled_prompt"]
    assert "Branco" in pr_payload["compiled_prompt"]

