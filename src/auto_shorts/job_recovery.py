"""
AutoShorts Aegis — Persistent Job State Machine & Crash Recovery
Garante idempotência, escrita atômica de checkpoints e retomada de produções
interrompidas pelo Android Low Memory Killer (LMK) ou quedas de sessão.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("autoshorts.aegis.recovery")


class JobState(str, enum.Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    DISCOVERING = "DISCOVERING"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    SCRIPTING = "SCRIPTING"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    RENDERING = "RENDERING"
    RENDER_FAILED = "RENDER_FAILED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RECOVERABLE = "RECOVERABLE"
    RECOVERING = "RECOVERING"


VALID_TRANSITIONS: Dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.QUEUED, JobState.FAILED},
    JobState.QUEUED: {JobState.DISCOVERING, JobState.DOWNLOADING, JobState.FAILED},
    JobState.DISCOVERING: {JobState.DOWNLOADING, JobState.FAILED},
    JobState.DOWNLOADING: {JobState.DOWNLOADED, JobState.TRANSCRIBING, JobState.RENDERING, JobState.FAILED},
    JobState.DOWNLOADED: {JobState.TRANSCRIBING, JobState.RENDERING, JobState.FAILED},
    JobState.TRANSCRIBING: {JobState.SCRIPTING, JobState.RENDERING, JobState.FAILED},
    JobState.SCRIPTING: {JobState.GENERATING_AUDIO, JobState.RENDERING, JobState.FAILED},
    JobState.GENERATING_AUDIO: {JobState.RENDERING, JobState.FAILED},
    JobState.RENDERING: {JobState.VALIDATING, JobState.READY, JobState.RENDER_FAILED, JobState.FAILED},
    JobState.RENDER_FAILED: {JobState.RECOVERING, JobState.RECOVERABLE, JobState.FAILED},
    JobState.VALIDATING: {JobState.READY, JobState.FAILED, JobState.RECOVERABLE},
    JobState.READY: {JobState.PUBLISHING, JobState.FAILED},
    JobState.PUBLISHING: {JobState.PUBLISHED, JobState.FAILED, JobState.RECOVERABLE},
    JobState.RECOVERING: {JobState.QUEUED, JobState.DOWNLOADING, JobState.RENDERING, JobState.FAILED},
    JobState.RECOVERABLE: {JobState.RECOVERING, JobState.QUEUED, JobState.FAILED},
    JobState.PUBLISHED: set(),
    JobState.FAILED: {JobState.RECOVERABLE, JobState.RECOVERING},
}


@dataclass
class JobCheckpoint:
    job_id: str
    niche: str = "podcast"
    platform: str = "tiktok_rewards"
    state: JobState = JobState.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_url: str = ""
    raw_video_path: str = ""
    transcript_path: str = ""
    audio_path: str = ""
    rendered_video_path: str = ""
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    quality_score: int = 0
    retry_count: int = 0
    max_retries: int = 3
    last_error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        d = self.to_dict()
        if item in d:
            return d[item]
        if item == "error":
            return self.last_error
        raise KeyError(item)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, JobState) else str(self.state)
        d["error"] = self.last_error
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JobCheckpoint:
        clean_data = dict(data)
        state_str = clean_data.get("state", JobState.CREATED.value)
        try:
            state = JobState(state_str)
        except ValueError:
            state = JobState.FAILED
        clean_data["state"] = state
        if "error" in clean_data and not clean_data.get("last_error"):
            clean_data["last_error"] = clean_data.pop("error")
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in clean_data.items() if k in valid_keys}
        return cls(**filtered)


class JobRecoveryManager:
    """Gerencia checkpoints atômicos persistidos em disco para cada produção."""

    def __init__(self, out_dir: Optional[str | Path] = None, jobs_dir: Optional[str | Path] = None):
        if jobs_dir is not None:
            self.jobs_dir = Path(jobs_dir)
            self.out_dir = self.jobs_dir.parent
        elif out_dir is not None:
            self.out_dir = Path(out_dir)
            self.jobs_dir = self.out_dir / "jobs"
        else:
            self.out_dir = Path("output")
            self.jobs_dir = self.out_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        clip_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        niche: str = "podcast",
        platform: str = "tiktok_rewards",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JobCheckpoint:
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        meta = dict(metadata or {})
        if clip_id:
            meta["clip_id"] = clip_id
        if payload:
            meta.update(payload)
            niche = payload.get("niche", niche)
            platform = payload.get("platform", platform)
            title = payload.get("title", "")
        else:
            title = ""

        job = JobCheckpoint(
            job_id=job_id,
            niche=niche,
            platform=platform,
            state=JobState.CREATED,
            title=title,
            metadata=meta,
        )
        self.save_checkpoint(job)
        return job

    def get_job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def save_checkpoint(self, job: JobCheckpoint) -> None:
        """Escrita atômica em 2 fases: grava em arquivo temporário e faz atomic rename."""
        job.updated_at = time.time()
        target_path = self.get_job_path(job.job_id)

        data = job.to_dict()
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.jobs_dir, prefix=f"{job.job_id}_", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, target_path)
        except Exception as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            logger.error("Falha ao salvar checkpoint atômico do job %s: %s", job.job_id, exc)
            raise

    def load_job(self, job_id: str) -> Optional[JobCheckpoint]:
        path = self.get_job_path(job_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return JobCheckpoint.from_dict(data)
        except Exception as exc:
            logger.warning("Checkpoint do job %s corrompido: %s", job_id, exc)
            return None

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.load_job(job_id)
        return job.to_dict() if job else None

    def list_jobs(self, limit: int = 50) -> List[JobCheckpoint]:
        jobs: List[JobCheckpoint] = []
        for file in sorted(self.jobs_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                jobs.append(JobCheckpoint.from_dict(data))
            except Exception:
                continue
        return jobs

    def transition(
        self,
        job_or_id: str | JobCheckpoint,
        new_state: JobState,
        metadata: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> JobCheckpoint:
        """Atualiza estado com auditoria e validação de transição válida."""
        if isinstance(job_or_id, str):
            job = self.load_job(job_or_id)
            if job is None:
                raise ValueError(f"Job not found: {job_or_id}")
        else:
            job = job_or_id

        target_state = JobState(new_state)
        curr_state = job.state if isinstance(job.state, JobState) else JobState(job.state)

        # Validar transição
        allowed = VALID_TRANSITIONS.get(curr_state, set())
        if target_state not in allowed:
            raise ValueError(
                f"Transicao de estado invalida: {curr_state.value} -> {target_state.value}"
            )

        job.state = target_state
        if metadata:
            job.metadata.update(metadata)
            if "error" in metadata:
                job.last_error = str(metadata["error"])
        if error:
            job.last_error = error

        self.save_checkpoint(job)
        logger.info("Job %s migrou para o estado %s", job.job_id, target_state.value)
        return job

    def find_recoverable_jobs(self) -> List[JobCheckpoint]:
        """Localiza jobs que estavam em processamento quando houve queda do processo."""
        recoverable: List[JobCheckpoint] = []
        in_progress_states = {
            JobState.DOWNLOADING,
            JobState.DOWNLOADED,
            JobState.TRANSCRIBING,
            JobState.SCRIPTING,
            JobState.GENERATING_AUDIO,
            JobState.RENDERING,
            JobState.RENDER_FAILED,
            JobState.VALIDATING,
        }
        for job in self.list_jobs(limit=50):
            if job.state in in_progress_states:
                # Se o job ficou mais de 5 minutos sem atualizacao ou falhou na renderizacao
                if job.state == JobState.RENDER_FAILED or (time.time() - job.updated_at > 300):
                    job.state = JobState.RECOVERABLE
                    self.save_checkpoint(job)
                    recoverable.append(job)
            elif job.state == JobState.RECOVERABLE:
                recoverable.append(job)
        return recoverable

    def list_recoverable_jobs(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self.find_recoverable_jobs()]

    def recover_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.load_job(job_id)
        if not job:
            return None
        job.state = JobState.RECOVERING
        job.retry_count += 1
        self.save_checkpoint(job)
        return job.to_dict()


# Alias HKUDS / CLI-Anything
JobRecoveryEngine = JobRecoveryManager
