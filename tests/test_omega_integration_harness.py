"""Test Suite for Omega Ultimate Repository Integration Harness & Video Intelligence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import pytest

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_shorts.live_clipping_multimodal import (
    HighlightCandidate,
    MultimodalHighlightScorer,
)
from auto_shorts.viral_forensics import (
    HookForensicAnalysis,
    PacingForensicAnalysis,
    ViralForensicDossier,
    ViralForensicsEngine,
)
from auto_shorts.visual_qa_engine import VisualQAEngine
from auto_shorts.cli_anything import cmd_omega
from scripts.omega_repo_harness import OmegaRepoHarness


# --- 1. MULTIMODAL LIVE CLIPPING TESTS ---

def test_multimodal_highlight_scorer():
    scorer = MultimodalHighlightScorer(min_clip_sec=20.0, max_clip_sec=58.0, cooldown_sec=30.0)

    # 10 samples per sec for 120s
    # Generate background noise (0.1 to 0.2) and a strong reaction spike at 40s (index 400)
    audio_samples = [0.15] * 1200
    for i in range(400, 480):
        audio_samples[i] = 1.8  # Strong spike

    scene_changes = [15.0, 42.0, 55.0, 90.0]
    speech_intervals = [(10.0, 35.0), (38.0, 70.0), (75.0, 110.0)]

    candidates = scorer.evaluate_live_window(
        audio_rms_samples=audio_samples,
        scene_changes=scene_changes,
        speech_intervals=speech_intervals,
        sample_rate_hz=10.0,
        window_duration_sec=120.0,
    )

    assert len(candidates) >= 1
    top = candidates[0]
    assert isinstance(top, HighlightCandidate)
    assert top.overall_score >= 50.0
    assert top.audio_energy_score > 60.0
    assert top.trigger_type in {"SCREAM_REACTION", "MULTIMODAL_SPIKE", "VIRAL_SPEECH"}
    assert top.context_preserved is True
    assert top.snapped_to_sentence is True


# --- 2. VIRAL FORENSICS ENGINE TESTS ---

def test_viral_forensics_engine(tmp_path):
    engine = ViralForensicsEngine()

    transcript = (
        "Como a nova inteligencia artificial consegue rodar dentro do seu celular em 2026. "
        "Engenheiros conseguiram otimizar os modelos neurais para gastar menos de 2 watts de bateria. "
        "Isso muda completamente a privacidade e o futuro dos smartphones."
    )

    dossier = engine.analyze_short_structure(
        video_id="test_viral_video_99",
        title="O Futuro da IA no Celular",
        transcript_text=transcript,
        duration_sec=35.0,
        niche="tech",
        cut_timestamps=[0.0, 3.5, 7.8, 12.0, 18.2, 24.0, 29.5],
    )

    assert isinstance(dossier, ViralForensicDossier)
    assert dossier.video_id == "test_viral_video_99"
    assert dossier.hook_analysis.retention_score >= 80
    assert dossier.hook_analysis.has_banned_cliche is False
    assert dossier.pacing_analysis.cuts_per_minute > 10.0
    assert len(dossier.empirical_facts) >= 4
    assert len(dossier.logical_inferences) >= 3
    assert len(dossier.testable_hypotheses) >= 3

    # Export reports
    json_path, md_path = engine.export_reports(dossier, out_dir=tmp_path)
    assert json_path.is_file()
    assert md_path.is_file()

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_json["video_id"] == "test_viral_video_99"

    md_text = md_path.read_text(encoding="utf-8")
    assert "LAUDO PERICIAL DE ENGENHARIA REVERSA" in md_text


def test_viral_forensics_banned_cliche():
    engine = ViralForensicsEngine()
    bad_transcript = "No vídeo de hoje vamos ver as maiores novidades tecnológicas."
    dossier = engine.analyze_short_structure(
        video_id="bad_01",
        title="Video Com Cliche",
        transcript_text=bad_transcript,
        duration_sec=20.0,
    )
    assert dossier.hook_analysis.has_banned_cliche is True
    assert dossier.hook_analysis.retention_score < 70


# --- 3. VISUAL QA ENGINE TESTS ---

def test_visual_qa_engine_diagnostics(tmp_path):
    engine = VisualQAEngine(out_dir=tmp_path)
    fake_mp4 = tmp_path / "qa_test.mp4"
    fake_mp4.write_bytes(b"\x00" * 300000)

    res = engine.run_deep_diagnostics(fake_mp4)
    assert isinstance(res, dict)
    assert res["file_name"] == "qa_test.mp4"
    assert "black_frames_detected" in res
    assert "frozen_frames_detected" in res
    assert "silence_intervals_detected" in res


# --- 4. OMEGA REPO HARNESS TESTS ---

def test_omega_repo_harness_audit(tmp_path):
    harness = OmegaRepoHarness(lab_dir=tmp_path)
    audit_res = harness.run_audit()
    assert audit_res["mode"] == "AUDIT"
    assert audit_res["total"] >= 20
    assert len(audit_res["audits"]) >= 20

    # Ensure all repos have commercial safety evaluation
    for a in audit_res["audits"]:
        assert "commercial_safe" in a
        assert "arm64_compatibility" in a


def test_omega_repo_harness_dry_run(tmp_path):
    harness = OmegaRepoHarness(lab_dir=tmp_path)
    dry_res = harness.run_dry_run()
    assert dry_res["mode"] == "DRY_RUN"
    assert dry_res["total_repositories"] >= 20
    assert "plan" in dry_res


def test_omega_repo_harness_report(tmp_path):
    harness = OmegaRepoHarness(lab_dir=tmp_path)
    rep = harness.run_report()
    assert rep["title"] == "AutoShorts Omega Repository Integration Report"
    assert rep["catalog_summary"]["total_repos"] >= 20
    assert (tmp_path / "reports" / "repository_integration_report.json").is_file()


# --- 5. CLI ANYTHING OMEGA SUBCOMMAND TESTS ---

def test_cli_anything_omega_inventory(capsys, tmp_path):
    args = argparse.Namespace(omega_action="inventory", json=True)
    ret = cmd_omega(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "system_health" in data
    assert "compliance" in data


def test_cli_anything_omega_repos(capsys, tmp_path):
    args = argparse.Namespace(omega_action="repos", repo_action="audit", json=True)
    ret = cmd_omega(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["mode"] == "AUDIT"


def test_cli_anything_omega_live(capsys, tmp_path):
    args = argparse.Namespace(omega_action="live", json=True)
    ret = cmd_omega(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "watchlist" in data
    assert data["count"] >= 5


def test_cli_anything_omega_clips(capsys, tmp_path):
    args = argparse.Namespace(omega_action="clips", json=True)
    ret = cmd_omega(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "candidates" in data


def test_cli_anything_omega_forensics(capsys, tmp_path):
    args = argparse.Namespace(
        omega_action="forensics",
        video_id="v_test_01",
        title="Descoberta Revolucionaria",
        transcript="Como a tecnologia transformou o Brasil.",
        duration=40.0,
        niche="tech",
        json=True,
    )
    ret = cmd_omega(args, out_dir=tmp_path)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "dossier" in data
    assert Path(data["json_report"]).is_file()
