"""Instagram Reels Adapter — Meta Graph API Official Delivery & Visual QA."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..engine import OmegaCDPEngine
from ..models import Platform, PublishState, PublishTask
from .base import BasePlatformAdapter

logger = logging.getLogger("autoshorts.omega_cdp.instagram")


class InstagramOmegaAdapter(BasePlatformAdapter):
    """Adaptador oficial Meta Graph API v19+ para publicação de Reels com auditoria visual CDP."""

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    def check_auth_status(self) -> Dict[str, Any]:
        has_token = bool(os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip())
        has_page = bool(os.getenv("INSTAGRAM_PAGE_ID", "").strip())
        profile = self.session_manager.get_session_profile(self.platform)
        return {
            "platform": self.platform.value,
            "has_graph_api_token": has_token,
            "has_page_id": has_page,
            "has_cdp_cookies": profile.is_authenticated,
            "ready_to_publish": has_token and has_page,
        }

    def prepare_task(self, task: PublishTask) -> PublishTask:
        cap = task.description or task.title
        task.description = cap[:2100]
        task.state = PublishState.VALIDATED
        task.updated_at = time.time()
        return task

    def execute_upload(self, task: PublishTask, engine: Optional[OmegaCDPEngine] = None) -> PublishTask:
        mp4_path = Path(task.video_path)
        if not mp4_path.is_file():
            task.state = PublishState.FAILED
            task.last_error = f"Arquivo de video nao encontrado: {task.video_path}"
            return task

        task.state = PublishState.UPLOADING
        task.updated_at = time.time()

        from ...publisher import publish_to_instagram_reels
        try:
            res = publish_to_instagram_reels(
                video_path=mp4_path,
                caption=task.description or task.title,
                force=True,
            )
            if res.get("status") == "published_instagram":
                media_id = str(res.get("media_id") or "")
                task.remote_publish_id = media_id
                task.remote_url = f"https://www.instagram.com/reel/{media_id}" if media_id else ""
                task.state = PublishState.PUBLISHED
                task.updated_at = time.time()
            elif res.get("status") in ("skipped_unconfigured", "error"):
                task.state = PublishState.FAILED
                task.last_error = str(res.get("reason") or "Erro na publicacao do Reels via Graph API")
            else:
                task.state = PublishState.FAILED
                task.last_error = f"Resposta inesperada do Graph API: {res}"
        except Exception as exc:
            task.state = PublishState.FAILED
            task.last_error = f"Excecao na execucao do upload Instagram Reels: {exc}"

        return task

    def fetch_live_metrics(self, remote_publish_id: str) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "publish_id": remote_publish_id,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "queried_at": time.time(),
        }
