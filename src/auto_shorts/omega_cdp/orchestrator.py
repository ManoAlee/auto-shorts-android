"""Omega Control Orchestrator — Central Director for Multiplatform Publishing, Session Guarding and Visual QA."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adapters import (
    BasePlatformAdapter,
    InstagramOmegaAdapter,
    TikTokOmegaAdapter,
    TwitchKickAdapter,
    YouTubeOmegaAdapter,
)
from .approval_gateway import UserApprovalGateway
from .engine import OmegaCDPEngine
from .models import Platform, PublishState, PublishTask
from .registry import PlatformCapabilityRegistry
from .session_manager import SecureSessionManager
from .visual_qa import VisualQAInspector

logger = logging.getLogger("autoshorts.omega_cdp.orchestrator")


class OmegaControlOrchestrator:
    """Orquestrador mestre do subsistema Omega CDP Control Engine."""

    def __init__(self, base_output_dir: Path | str = "output") -> None:
        self.out_dir = Path(base_output_dir)
        self.tasks_dir = self.out_dir / "omega_tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        self.registry = PlatformCapabilityRegistry()
        self.session_manager = SecureSessionManager(self.out_dir / "browser_profiles")
        self.approval_gateway = UserApprovalGateway(self.out_dir / "reviews")
        self.visual_qa = VisualQAInspector(self.out_dir / "evidence")

        self.adapters: Dict[Platform, BasePlatformAdapter] = {
            Platform.YOUTUBE: YouTubeOmegaAdapter(self.session_manager),
            Platform.TIKTOK: TikTokOmegaAdapter(self.session_manager),
            Platform.INSTAGRAM: InstagramOmegaAdapter(self.session_manager),
            Platform.TWITCH: TwitchKickAdapter(self.session_manager, Platform.TWITCH),
            Platform.KICK: TwitchKickAdapter(self.session_manager, Platform.KICK),
        }

    def _get_task_file(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def save_task(self, task: PublishTask) -> None:
        """Escrita transacional atômica em 2 fases."""
        task.updated_at = time.time()
        target = self._get_task_file(task.task_id)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.tasks_dir, prefix=f"{task.task_id}_", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, target)
        except Exception as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            logger.error("Falha ao persistir tarefa Omega %s: %s", task.task_id, exc)
            raise

    def load_task(self, task_id: str) -> Optional[PublishTask]:
        target = self._get_task_file(task_id)
        if not target.is_file():
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return PublishTask.from_dict(data)
        except Exception as exc:
            logger.warning("Arquivo de tarefa %s corrompido: %s", task_id, exc)
            return None

    def list_tasks(
        self,
        platform: Optional[Platform | str] = None,
        state: Optional[PublishState | str] = None,
        limit: int = 50,
    ) -> List[PublishTask]:
        tasks: List[PublishTask] = []
        p_filter = Platform(platform) if platform else None
        s_filter = PublishState(state) if state else None

        for file in sorted(self.tasks_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                t = PublishTask.from_dict(data)
                if p_filter and t.platform != p_filter:
                    continue
                if s_filter and t.state != s_filter:
                    continue
                tasks.append(t)
            except Exception:
                continue
        return tasks

    def create_task(
        self,
        platform: Platform | str,
        video_path: Path | str,
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
        niche: str = "geral",
        require_approval: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PublishTask:
        p = Platform(platform) if isinstance(platform, str) else platform
        if not self.registry.is_operation_allowed(p, "upload_video") and not self.registry.is_operation_allowed(p, "upload_reels_meta_graph_api"):
            raise PermissionError(f"Operacao de upload nao autorizada para plataforma {p.value}")

        task_id = f"omega_{p.value}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = PublishTask(
            task_id=task_id,
            platform=p,
            video_path=str(video_path),
            title=title,
            description=description,
            hashtags=hashtags or [],
            niche=niche,
            state=PublishState.CREATED,
            metadata=metadata or {},
        )
        task.state_history.append({"state": PublishState.CREATED.value, "timestamp": time.time(), "notes": "Tarefa criada"})

        # Validação de metadados pelo adaptador da plataforma
        adapter = self.adapters[p]
        task = adapter.prepare_task(task)

        # Portão de aprovação humana
        if require_approval:
            task = self.approval_gateway.submit_for_review(task, auto_review_notes="Criado via Omega Orchestrator")
        else:
            task.state = PublishState.QUEUED
            task.state_history.append({"state": PublishState.QUEUED.value, "timestamp": time.time(), "notes": "Fila direta sem aprovacao"})

        self.save_task(task)
        logger.info("Tarefa de publicacao Omega %s criada para %s (Estado: %s)", task.task_id, p.value, task.state.value)
        return task

    def approve_task(self, task_id: str, operator: str = "operator_admin", comment: str = "") -> PublishTask:
        task = self.load_task(task_id)
        if not task:
            raise ValueError(f"Tarefa nao encontrada: {task_id}")
        task = self.approval_gateway.approve(task, operator=operator, comment=comment)
        task.state = PublishState.QUEUED
        task.state_history.append({"state": PublishState.QUEUED.value, "timestamp": time.time(), "notes": "Enfileirado para envio"})
        self.save_task(task)
        return task

    def reject_task(self, task_id: str, operator: str = "operator_admin", reason: str = "") -> PublishTask:
        task = self.load_task(task_id)
        if not task:
            raise ValueError(f"Tarefa nao encontrada: {task_id}")
        task = self.approval_gateway.reject(task, operator=operator, reason=reason)
        self.save_task(task)
        return task

    def execute_task(self, task_id: str) -> PublishTask:
        """Executa a publicação de uma tarefa aprovada/enfileirada com prevenção de duplicidade."""
        task = self.load_task(task_id)
        if not task:
            raise ValueError(f"Tarefa nao encontrada: {task_id}")

        if task.state != PublishState.QUEUED:
            raise ValueError(f"Apenas tarefas no estado QUEUED podem ser executadas. Estado atual: {task.state.value}")

        adapter = self.adapters.get(task.platform)
        if not adapter:
            raise ValueError(f"Adaptador nao disponivel para {task.platform}")

        # Prevenção de duplicidade: checar se já possui ID de publicação remoto registrado
        if task.remote_publish_id:
            logger.warning("Tarefa %s ja possui remote_publish_id=%s. Ignorando reenvio.", task.task_id, task.remote_publish_id)
            task.state = PublishState.PUBLISHED
            self.save_task(task)
            return task

        task = adapter.execute_upload(task)
        self.save_task(task)

        # Se publicado com sucesso e possui URL remota, acionar verificação visual pós-publicação
        if task.state == PublishState.PUBLISHED and task.remote_url:
            try:
                self.verify_task(task.task_id)
            except Exception as exc:
                logger.warning("Falha na inspecao visual automatica pos-upload para %s: %s", task.task_id, exc)

        return task

    def verify_task(self, task_id: str) -> PublishTask:
        """Abre a página pública da publicação e audita título e renderização de vídeo."""
        task = self.load_task(task_id)
        if not task:
            raise ValueError(f"Tarefa nao encontrada: {task_id}")

        if not task.remote_url:
            raise ValueError(f"Tarefa {task_id} nao possui URL remota para inspecao.")

        prof_dir = self.session_manager.get_profile_dir(task.platform)
        with OmegaCDPEngine(profile_dir=prof_dir, headless=True, timeout=25.0) as engine:
            self.visual_qa.inspect_publication(task, engine)

        self.save_task(task)
        return task

    def get_dashboard_telemetry(self) -> Dict[str, Any]:
        """Agrega telemetria em tempo real para exibição no Web Studio (:8787)."""
        all_tasks = self.list_tasks(limit=100)
        counts = {
            "total": len(all_tasks),
            "ready_for_review": sum(1 for t in all_tasks if t.state == PublishState.READY_FOR_REVIEW),
            "approved": sum(1 for t in all_tasks if t.state == PublishState.APPROVED),
            "queued": sum(1 for t in all_tasks if t.state == PublishState.QUEUED),
            "uploading": sum(1 for t in all_tasks if t.state == PublishState.UPLOADING),
            "published": sum(1 for t in all_tasks if t.state == PublishState.PUBLISHED),
            "verified": sum(1 for t in all_tasks if t.state == PublishState.VERIFIED),
            "failed": sum(1 for t in all_tasks if t.state == PublishState.FAILED),
            "requires_human_action": sum(1 for t in all_tasks if t.state == PublishState.REQUIRES_HUMAN_ACTION),
        }

        sessions = {}
        for p in (Platform.YOUTUBE, Platform.TIKTOK, Platform.INSTAGRAM):
            sessions[p.value] = self.adapters[p].check_auth_status()

        return {
            "status": "OPERATIONAL",
            "timestamp": time.time(),
            "task_counts": counts,
            "sessions": sessions,
            "capabilities": self.registry.list_capabilities(),
            "recent_tasks": [t.to_dict() for t in all_tasks[:10]],
        }
