"""Tests for Phase 2: Story Engine, Director Engine & Retention Engine."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auto_shorts.story_engine import (
    CAMERA_MOVEMENTS,
    LIGHTING_MOODS,
    SHOT_TYPES,
    STORY_GENRES,
    VFX_CUES,
    CameraDirection,
    CharacterProfile,
    CinematicScene,
    CinematicScript,
    DirectorEngine,
    NarrativeContinuityStore,
    RetentionEngine,
    StoryEngine,
)
from auto_shorts.webapp import make_handler


def test_story_engine_data_models_and_json_serialization():
    cam = CameraDirection(
        shot_type="CLOSE_UP",
        movement="SLOW_ZOOM_IN",
        lighting="DRAMATIC_NEON",
        focus_target="FACE_CENTER",
        duration_sec=3.5,
    )
    assert cam.shot_type in SHOT_TYPES
    assert cam.movement in CAMERA_MOVEMENTS
    assert cam.lighting in LIGHTING_MOODS

    scene = CinematicScene(
        scene_id=1,
        act="HOOK",
        speaker="Ren",
        voice_profile="pm_alex",
        dialogue="O segredo que ninguém percebeu...",
        visual_description="Close-up nos olhos de Ren refletindo luz azul.",
        camera=cam,
        vfx="IMPACT_LINES",
        sfx="WHOOSH",
    )
    assert scene.vfx in VFX_CUES
    s_dict = scene.to_dict()
    assert s_dict["camera"]["shot_type"] == "CLOSE_UP"

    char = CharacterProfile(
        char_id="protagonist",
        name="Ren",
        role="PROTAGONIST",
        archetype="Espadachim",
        visual_traits="Cabelo preto",
        costume="Manto negro",
        voice_key="pm_alex",
    )
    script = CinematicScript(
        story_id="story_test_1",
        title="O Despertar",
        genre="dark_shonen",
        season=1,
        episode=1,
        hook_sentence="O segredo que ninguém percebeu...",
        loop_sentence="E foi assim que começou.",
        target_duration_sec=35.0,
        characters=[char],
        scenes=[scene],
    )
    raw_json = script.to_json()
    parsed = json.loads(raw_json)
    assert parsed["story_id"] == "story_test_1"
    assert len(parsed["scenes"]) == 1
    assert parsed["characters"][0]["name"] == "Ren"


def test_narrative_continuity_store_sqlite(tmp_path):
    db_file = tmp_path / "test_continuity.db"
    store = NarrativeContinuityStore(db_path=db_file)

    # Register story and characters
    store.register_story("story_cyber_01", "Neon São Paulo", "cyberpunk_br", "Distopia 2077")
    char_a = CharacterProfile(
        char_id="maya_01",
        name="Maya",
        role="PROTAGONIST",
        archetype="Hacker",
        visual_traits="Cabelo roxo",
        costume="Jaqueta grafitada",
        voice_key="pf_dora",
    )
    store.save_character("story_cyber_01", char_a)

    chars = store.list_characters("story_cyber_01")
    assert len(chars) == 1
    assert chars[0].name == "Maya"
    assert chars[0].voice_key == "pf_dora"

    # Episode counter
    assert store.get_latest_episode_number("story_cyber_01", season=1) == 0

    script = CinematicScript(
        story_id="story_cyber_01",
        title="Episódio 1: Protocolo Zero",
        genre="cyberpunk_br",
        season=1,
        episode=1,
        hook_sentence="O código proibido foi quebrado.",
        loop_sentence="E a rede nunca mais foi a mesma.",
        target_duration_sec=42.0,
        characters=[char_a],
        scenes=[],
    )
    store.record_episode(script)
    assert store.get_latest_episode_number("story_cyber_01", season=1) == 1


def test_director_engine_camera_shots_and_timing():
    cam_hook = DirectorEngine.apply_cinematic_direction("HOOK", "O segredo foi finalmente revelado para o mundo!")
    assert cam_hook.shot_type == "CLOSE_UP"
    assert cam_hook.movement == "SLOW_ZOOM_IN"
    assert cam_hook.duration_sec >= 2.5

    cam_climax = DirectorEngine.apply_cinematic_direction("CLIMAX", "O golpe final!")
    assert cam_climax.shot_type == "EXTREME_CLOSE_UP"
    assert cam_climax.movement == "SHAKE_IMPACT"


def test_retention_engine_hook_and_pacing_evaluation():
    engine = StoryEngine(continuity_store=NarrativeContinuityStore(Path(":memory:")))
    script = engine.generate_story_script(
        prompt="A Batalha dos Titãs Proibidos",
        genre="dark_shonen",
        season=1,
        episode=1,
        target_duration_sec=30.0,
    )
    scorecard = RetentionEngine.evaluate_script_retention(script)
    assert "overall_retention_score" in scorecard
    assert scorecard["overall_retention_score"] >= 70
    assert scorecard["decision"] in ("APPROVED_VIRAL", "NEEDS_OPTIMIZATION")
    assert "pacing_score" in scorecard
    assert len(scorecard["hook_triggers"]) >= 1


def test_story_engine_multi_episode_continuity(tmp_path):
    store = NarrativeContinuityStore(db_path=tmp_path / "continuity.db")
    engine = StoryEngine(continuity_store=store)

    ep1 = engine.generate_story_script("O Poder dos Olhos Carmesim", genre="dark_shonen", season=1)
    assert ep1.episode == 1
    assert len(ep1.characters) >= 2
    assert len(ep1.scenes) >= 5

    # Second episode of same prompt should automatically increment episode number and keep cast
    ep2 = engine.generate_story_script("O Poder dos Olhos Carmesim", genre="dark_shonen", season=1)
    assert ep2.episode == 2
    assert ep2.story_id == ep1.story_id
    assert [c.char_id for c in ep2.characters] == [c.char_id for c in ep1.characters]


def test_webapp_story_endpoints_api(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    HandlerClass = make_handler(out_dir)

    # 1. Test GET /api/story/genres
    handler_get = MagicMock(spec=HandlerClass)
    handler_get.path = "/api/story/genres"
    handler_get.headers = {}
    json_responses = []
    handler_get._send_json = lambda code, payload: json_responses.append((code, payload))
    handler_get._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_GET(handler_get)
    assert len(json_responses) == 1
    code, payload = json_responses[0]
    assert code == 200
    assert "dark_shonen" in payload["genres"]

    # 2. Test POST /api/story/generate
    handler_post = MagicMock(spec=HandlerClass)
    handler_post.path = "/api/story/generate"
    handler_post.headers = {"Content-Length": "120"}
    post_body = json.dumps({"prompt": "A Queda do Satélite", "genre": "cyberpunk_br", "season": 1}).encode("utf-8")
    handler_post.rfile = MagicMock()
    handler_post.rfile.read = lambda n: post_body
    post_responses = []
    handler_post._send_json = lambda code, payload: post_responses.append((code, payload))
    handler_post._check_tunnel_auth = lambda parsed: None

    HandlerClass.do_POST(handler_post)
    assert len(post_responses) == 1
    p_code, p_payload = post_responses[0]
    assert p_code == 200
    assert p_payload["ok"] is True
    assert "script" in p_payload
    assert p_payload["script"]["genre"] == "cyberpunk_br"
    assert len(p_payload["script"]["scenes"]) >= 5

