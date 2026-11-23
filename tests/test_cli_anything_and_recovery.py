"""Tests for HKUDS/CLI-Anything compliance and Job Recovery State Machine."""

import argparse
import json
from pathlib import Path
import pytest

from auto_shorts.job_recovery import (
    JobRecoveryEngine,
    JobRecoveryManager,
    JobState,
    VALID_TRANSITIONS,
)
from auto_shorts.cli_anything import (
    get_system_health,
    cmd_status,
    cmd_health,
    cmd_jobs,
)


def test_job_recovery_lifecycle(tmp_path):
    jobs_dir = tmp_path / "output" / "jobs"
    engine = JobRecoveryEngine(jobs_dir=jobs_dir)

    # 1. Create job
    job = engine.create_job(
        clip_id="clip_test_001",
        payload={"niche": "ia_tech", "title": "IA Revolucionaria"},
    )
    assert job["job_id"].startswith("job_")
    assert job["state"] == JobState.CREATED.value
    assert (jobs_dir / f"{job['job_id']}.json").is_file()

    # 2. Valid transitions
    job_id = job["job_id"]
    engine.transition(job_id, JobState.QUEUED)
    assert engine.get_job(job_id)["state"] == JobState.QUEUED.value

    engine.transition(job_id, JobState.DOWNLOADING)
    engine.transition(job_id, JobState.DOWNLOADED)
    engine.transition(job_id, JobState.RENDERING)

    # 3. Simulate failure during render
    engine.transition(
        job_id,
        JobState.RENDER_FAILED,
        metadata={"error": "SIGKILL OOM simulation"},
    )
    failed_job = engine.get_job(job_id)
    assert failed_job["state"] == JobState.RENDER_FAILED.value
    assert failed_job["error"] == "SIGKILL OOM simulation"

    # 4. Recoverable list
    recoverable = engine.list_recoverable_jobs()
    assert any(j["job_id"] == job_id for j in recoverable)

    # 5. Recover job
    recovered = engine.recover_job(job_id)
    assert recovered is not None
    assert recovered["state"] == JobState.RECOVERING.value
    assert recovered["retry_count"] == 1


def test_job_recovery_invalid_transition(tmp_path):
    jobs_dir = tmp_path / "output" / "jobs"
    engine = JobRecoveryEngine(jobs_dir=jobs_dir)
    job = engine.create_job("clip_bad_001", {})

    with pytest.raises(ValueError, match="Transicao de estado invalida"):
        engine.transition(job["job_id"], JobState.PUBLISHED)


def test_cli_anything_health_and_status(tmp_path, capsys):
    health = get_system_health(tmp_path)
    assert isinstance(health, dict)
    assert "status" in health
    assert "memory" in health
    assert "services" in health

    args = argparse.Namespace(json=True)
    rc = cmd_health(args, tmp_path)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] in ("HEALTHY", "DEGRADED")


def test_cli_anything_jobs(tmp_path, capsys):
    out_dir = tmp_path
    mgr = JobRecoveryManager(out_dir=out_dir)
    mgr.create_job("test_clip_01", {"title": "Short 1"})

    args = argparse.Namespace(json=True, job_action="list", limit=10)
    rc = cmd_jobs(args, out_dir)
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["count"] >= 1
    assert "jobs" in data
