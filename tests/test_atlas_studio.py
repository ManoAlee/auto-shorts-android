"""Test Suite for Atlas Studio Creative Production, Design System & Multi-Agent Quality Gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pytest

from auto_shorts.design_system import (
    DesignSystemManager,
    NicheDesignPreset,
    SafeZoneSpec,
)
from auto_shorts.quality_gates import (
    QualityGateResult,
    QualityGatesEngine,
    VideoScorecard7D,
)
from auto_shorts.atlas_studio_harness import (
    AgentTaskContract,
    AtlasStudioMultiAgentHarness,
)
from auto_shorts.cli_anything import cmd_studio


# --- 1. DESIGN SYSTEM TESTS ---

def test_safe_zone_spec():
    sz = SafeZoneSpec(width=1080, height=1920)
    rect = sz.usable_rect
    assert rect == (60, 220, 940, 1540)
    # Check dimensions of usable area
    usable_w = rect[2] - rect[0]
    usable_h = rect[3] - rect[1]
    assert usable_w == 880
    assert usable_h == 1320


def test_design_system_manager_presets():
    mgr = DesignSystemManager()
    presets = mgr.list_presets()
    assert len(presets) >= 6

    # Verify key niche presets exist
    niche_ids = [p["id"] for p in presets]
    assert "news" in niche_ids
    assert "tech" in niche_ids
    assert "gaming" in niche_ids
    assert "storytelling" in niche_ids
    assert "educational" in niche_ids
    assert "podcast" in niche_ids

    # Verify fallback for unknown niche
    unknown = mgr.get_preset("non_existent_niche")
    assert unknown.id == "podcast"

    # Verify safe coordinate validation
    assert mgr.validate_coordinate_safe(500, 1000) is True  # Center screen
    assert mgr.validate_coordinate_safe(10, 10) is False     # Top-left corner (unsafe)
    assert mgr.validate_coordinate_safe(1000, 1800) is False # Bottom-right interaction UI (unsafe)


def test_design_system_ass_style():
    mgr = DesignSystemManager()
    preset = mgr.get_preset("tech")
    ass_style = mgr.generate_ass_style_header(preset)
    assert "Style: Default" in ass_style
    assert preset.font_weight in ass_style or preset.primary_font in ass_style


# --- 2. QUALITY GATES & SCORECARD 7D TESTS ---

def test_quality_gates_engine_evaluations(tmp_path):
    engine = QualityGatesEngine(out_dir=tmp_path)

    # Gate A (Code & System)
    res_a = engine.evaluate_gate_a()
    assert isinstance(res_a, QualityGateResult)
    assert res_a.gate_name == "GATE_A_CODE_AND_SYSTEM"
    assert res_a.passed is True

    # Gate B (Media Integrity with fake mp4)
    fake_mp4 = tmp_path / "test_dummy.mp4"
    fake_mp4.write_bytes(b"\x00" * 200000)
    res_b = engine.evaluate_gate_b(fake_mp4)
    assert isinstance(res_b, QualityGateResult)
    assert res_b.gate_name == "GATE_B_MEDIA_INTEGRITY"

    # Gate C (Visual Validation)
    res_c = engine.evaluate_gate_c(fake_mp4, niche="tech")
    assert isinstance(res_c, QualityGateResult)
    assert res_c.gate_name == "GATE_C_VISUAL_VALIDATION"
    assert res_c.passed is True

    # Gate D (Audio Validation)
    res_d = engine.evaluate_gate_d(fake_mp4)
    assert isinstance(res_d, QualityGateResult)
    assert res_d.gate_name == "GATE_D_AUDIO_VALIDATION"
    assert res_d.passed is True

    # Gate E (Editorial Review)
    res_e = engine.evaluate_gate_e(title="Como a Inteligencia Artificial Mudou o Mundo em 2026", description="Analise completa da revolucao de IA.")
    assert isinstance(res_e, QualityGateResult)
    assert res_e.gate_name == "GATE_E_EDITORIAL_REVIEW"
    assert res_e.passed is True

    # Gate E with bad title
    res_e_bad = engine.evaluate_gate_e(title="Curto", description="")
    assert res_e_bad.passed is False
    assert len(res_e_bad.errors) > 0

    # Gate F (Platform Compliance)
    res_f_ok = engine.evaluate_gate_f(duration_sec=45.0, platform="youtube_shorts")
    assert res_f_ok.passed is True

    res_f_too_long = engine.evaluate_gate_f(duration_sec=75.0, platform="youtube_shorts")
    assert res_f_too_long.passed is False

    # Gate G (Human Approval)
    res_g = engine.evaluate_gate_g(approved_by="tester", approved_at=1700000000.0)
    assert res_g.passed is True
    assert res_g.score == 100


def test_video_scorecard_7d(tmp_path):
    engine = QualityGatesEngine(out_dir=tmp_path)
    fake_mp4 = tmp_path / "valid_test.mp4"
    fake_mp4.write_bytes(b"\x00" * 250000)

    card = engine.evaluate_video(
        mp4_path=fake_mp4,
        title="Novo Desafio de IA no Brasil",
        description="Um olhar detalhado sobre o avanço tecnológico em 2026.",
        niche="tech",
        platform="youtube_shorts",
    )
    assert isinstance(card, VideoScorecard7D)
    assert card.file_name == "valid_test.mp4"
    assert 0 <= card.overall_score <= 100
    assert len(card.gates) == 7
    assert "visual_quality" in card.dimension_scores
    assert "narrative_quality" in card.dimension_scores
    assert "audio_quality" in card.dimension_scores

    d = card.to_dict()
    assert d["file_name"] == "valid_test.mp4"
    assert "gates" in d


# --- 3. ATLAS STUDIO 13-PERSONA HARNESS TESTS ---

def test_atlas_studio_multi_agent_harness(tmp_path):
    harness = AtlasStudioMultiAgentHarness(out_dir=tmp_path)
    res = harness.execute_studio_pipeline(
        job_id="test_job_123",
        niche="news",
        topic="Cimeira Global de Tecnologia 2026",
    )
    assert res["job_id"] == "test_job_123"
    assert res["niche"] == "news"
    assert res["contracts_count"] == 13
    assert res["preset_applied"] == "news"
    assert res["status"] == "APPROVED_FOR_RENDER"

    # Verify audit evidence was written
    evidence_file = tmp_path / "studio_evidence" / "studio_harness_test_job_123.json"
    assert evidence_file.is_file()

    saved = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert saved["job_id"] == "test_job_123"
    assert len(saved["contracts"]) == 13


# --- 4. CLI ANYTHING STUDIO SUBCOMMAND TESTS ---

def test_cli_anything_studio_presets(capsys, tmp_path):
    args = argparse.Namespace(studio_action="presets", json=True)
    ret = cmd_studio(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "presets" in data
    assert len(data["presets"]) >= 6


def test_cli_anything_studio_pipeline(capsys, tmp_path):
    args = argparse.Namespace(
        studio_action="pipeline",
        niche="gaming",
        topic="Novos mapas e detalhes de GTA 6",
        job_id="job_gta6_test",
        operator="agent_tester",
        json=True,
    )
    ret = cmd_studio(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["job_id"] == "job_gta6_test"
    assert data["contracts_count"] == 13
