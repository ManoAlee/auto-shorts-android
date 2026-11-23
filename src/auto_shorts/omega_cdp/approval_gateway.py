"""User Approval Gateway — Enforces explicit human-in-the-loop sign-off before content release."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import PublishState, PublishTask

logger = logging.getLogger("autoshorts.omega_cdp.approval")


class UserApprovalGateway:
    """Portão de auditoria e aprovação humana para publicações e mutações externas."""

    def __init__(self, audit_dir: Path | str = "output/reviews") -> None:
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = self.audit_dir / "approval_audit.jsonl"

    def _record_audit_event(self, event_type: str, task: PublishTask, operator: str, detail: str = "") -> None:
        entry = {
            "timestamp": time.time(),
            "event": event_type,
            "task_id": task.task_id,
            "platform": task.platform.value if hasattr(task.platform, "value") else str(task.platform),
            "video_path": task.video_path,
            "title": task.title,
            "operator": operator,
            "detail": detail,
        }
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def submit_for_review(self, task: PublishTask, auto_review_notes: str = "") -> PublishTask:
        """Transiciona uma tarefa validada para a fila de revisão humana."""
        task.state = PublishState.READY_FOR_REVIEW
        task.updated_at = time.time()
        task.state_history.append({
            "state": PublishState.READY_FOR_REVIEW.value,
            "timestamp": task.updated_at,
            "notes": auto_review_notes or "Submetido para aprovacao humana",
        })
        self._record_audit_event("SUBMITTED_FOR_REVIEW", task, operator="system", detail=auto_review_notes)
        return task

    def approve(self, task: PublishTask, operator: str = "operator_admin", comment: str = "") -> PublishTask:
        """Aprova a publicação da tarefa pelo operador humano."""
        if task.state != PublishState.READY_FOR_REVIEW:
            raise ValueError(f"Tarefa nao pode ser aprovada no estado atual: {task.state}")

        task.state = PublishState.APPROVED
        task.approved_by = operator
        task.approved_at = time.time()
        task.updated_at = time.time()
        task.state_history.append({
            "state": PublishState.APPROVED.value,
            "timestamp": task.approved_at,
            "operator": operator,
            "comment": comment,
        })
        self._record_audit_event("APPROVED", task, operator=operator, detail=comment)
        logger.info("Tarefa %s aprovada pelo operador %s", task.task_id, operator)
        return task

    def reject(self, task: PublishTask, operator: str = "operator_admin", reason: str = "") -> PublishTask:
        """Rejeita a tarefa de publicação."""
        task.state = PublishState.FAILED
        task.last_error = f"Rejeitado pelo operador: {reason or 'Sem motivo especificado'}"
        task.updated_at = time.time()
        task.state_history.append({
            "state": PublishState.FAILED.value,
            "timestamp": task.updated_at,
            "operator": operator,
            "reason": reason,
        })
        self._record_audit_event("REJECTED", task, operator=operator, detail=reason)
        logger.warning("Tarefa %s rejeitada pelo operador %s: %s", task.task_id, operator, reason)
        return task
