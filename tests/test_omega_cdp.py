"""Test Suite for Omega CDP Native Control Engine."""

import argparse
import json
from pathlib import Path
import pytest

from auto_shorts.omega_cdp import (
    AdapterType,
    OmegaControlOrchestrator,
    Platform,
    PlatformCapabilityRegistry,
    PublishState,
    PublishTask,
    SecureSessionManager,
    UserApprovalGateway,
    VALID_PUBLISH_TRANSITIONS,
)
from auto_shorts.cli_anything import cmd_omega


def test_platform_capability_registry():
    reg = PlatformCapabilityRegistry()
    assert reg.is_operation_allowed(Platform.YOUTUBE, "upload_video") is True
    assert reg.is_operation_allowed(Platform.TIKTOK, "set_caption") is True
    assert reg.is_operation_allowed(Platform.INSTAGRAM, "upload_reels_meta_graph_api") is True

    # Prohibited operations must ALWAYS return False
    assert reg.is_operation_allowed(Platform.YOUTUBE, "captcha_bypass") is False
    assert reg.is_operation_allowed(Platform.TIKTOK, "credential_stuffing") is False
    assert reg.is_operation_allowed(Platform.INSTAGRAM, "mfa_bypass") is False


def test_secure_session_manager(tmp_path):
    mgr = SecureSessionManager(base_dir=tmp_path / "browser_profiles")

    # 1. Isolated profile dirs
    yt_dir = mgr.get_profile_dir(Platform.YOUTUBE)
    tt_dir = mgr.get_profile_dir(Platform.TIKTOK)
    assert yt_dir != tt_dir
    assert yt_dir.is_dir()

    # 2. Cookie save & load
    test_cookies = [
        {"name": "sessionid", "value": "xyz123", "domain": ".tiktok.com"},
        {"name": "tt_csrf", "value": "csrf_token_val", "domain": ".tiktok.com"},
    ]
    res = mgr.save_cookies(Platform.TIKTOK, test_cookies)
    assert res["ok"] is True
    assert res["count"] == 2

    loaded = mgr.load_cookies(Platform.TIKTOK)
    assert len(loaded) == 2
    assert loaded[0]["name"] == "sessionid"

    # 3. Session profile state
    prof = mgr.get_session_profile(Platform.TIKTOK)
    assert prof.is_authenticated is True

    # 4. Human challenge detection (Never bypass - flag for human intervention)
    challenge1 = mgr.detect_human_challenge("https://www.tiktok.com/verify-center/puzzle")
    assert challenge1 is not None
    assert challenge1["challenge_type"] == "TIKTOK_CAPTCHA_VERIFY"

    challenge2 = mgr.detect_human_challenge("https://accounts.google.com/signin/v2/challenge/pwd")
    assert challenge2 is not None
    assert challenge2["challenge_type"] == "GOOGLE_AUTH_CHALLENGE"

    no_challenge = mgr.detect_human_challenge("https://studio.youtube.com/channel/videos")
    assert no_challenge is None


def test_user_approval_gateway(tmp_path):
    gateway = UserApprovalGateway(audit_dir=tmp_path / "reviews")
    task = PublishTask(
        task_id="test_task_01",
        platform=Platform.YOUTUBE,
        video_path="clip.mp4",
        title="Video de Teste",
        description="Descricao do teste",
    )

    # 1. Submit for review
    task = gateway.submit_for_review(task, auto_review_notes="Revisão inicial")
    assert task.state == PublishState.READY_FOR_REVIEW

    # 2. Approve
    task = gateway.approve(task, operator="lead_editor", comment="Aprovado para postagem")
    assert task.state == PublishState.APPROVED
    assert task.approved_by == "lead_editor"

    # Audit log exists
    assert (tmp_path / "reviews" / "approval_audit.jsonl").is_file()


def test_omega_control_orchestrator(tmp_path, monkeypatch):
    orch = OmegaControlOrchestrator(base_output_dir=tmp_path)

    # Mock MP4 file
    test_video = tmp_path / "short_test.mp4"
    test_video.write_bytes(b"\x00" * 1024)

    # 1. Create task with required approval
    task = orch.create_task(
        platform=Platform.YOUTUBE,
        video_path=test_video,
        title="Luffy Nova Transformacao One Piece",
        description="Teoria completa sobre o novo poder",
        require_approval=True,
    )
    assert task.state == PublishState.READY_FOR_REVIEW
    assert task.task_id.startswith("omega_youtube_")

    # 2. Approve task -> moves to QUEUED
    approved_task = orch.approve_task(task.task_id, operator="reviewer_01")
    assert approved_task.state == PublishState.QUEUED

    # 3. Telemetry
    telemetry = orch.get_dashboard_telemetry()
    assert telemetry["status"] == "OPERATIONAL"
    assert telemetry["task_counts"]["queued"] >= 1


def test_cli_anything_omega_subcommands(tmp_path, capsys):
    args = argparse.Namespace(
        json=True,
        omega_action="capabilities",
    )
    rc = cmd_omega(args, tmp_path)
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "capabilities" in data
    assert len(data["capabilities"]) >= 3

    # Test status
    args_status = argparse.Namespace(json=True, omega_action="status")
    rc_status = cmd_omega(args_status, tmp_path)
    assert rc_status == 0
    out_status = capsys.readouterr().out
    data_status = json.loads(out_status)
    assert data_status["status"] == "OPERATIONAL"
