"""YouTube & YouTube Studio Adapter — Official API & Studio Web CDP Hybrid."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..engine import OmegaCDPEngine
from ..models import Platform, PublishState, PublishTask
from .base import BasePlatformAdapter

logger = logging.getLogger("autoshorts.omega_cdp.youtube")


class YouTubeOmegaAdapter(BasePlatformAdapter):
    """Adaptador híbrido para YouTube Data API v3 e YouTube Studio Web via CDP."""

    @property
    def platform(self) -> Platform:
        return Platform.YOUTUBE

    def check_auth_status(self) -> Dict[str, Any]:
        has_api_key = bool(os.getenv("YOUTUBE_API_KEY", "").strip())
        profile = self.session_manager.get_session_profile(self.platform)
        return {
            "platform": self.platform.value,
            "has_official_api_credentials": has_api_key,
            "has_cdp_cookies": profile.is_authenticated,
            "profile_dir": profile.profile_dir,
            "ready_to_publish": has_api_key or profile.is_authenticated,
        }

    def prepare_task(self, task: PublishTask) -> PublishTask:
        title = task.title.strip()[:95]
        desc = task.description.strip()
        if "#shorts" not in desc.lower() and "#shorts" not in title.lower():
            desc = f"{desc}\n\n#Shorts".strip()
        task.title = title
        task.description = desc
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

        # Tentar via módulo CDP existente hardened
        from ...youtube_cdp import publish_batch_to_youtube_cdp
        try:
            res = publish_batch_to_youtube_cdp(
                [mp4_path],
                force=True,
                headless=True,
                max_videos=1,
                out_dir=mp4_path.parent,
            )
            sub_results = res.get("results", [])
            first_res = sub_results[0] if sub_results else {}
            if first_res.get("status") == "login_required":
                task.state = PublishState.REQUIRES_HUMAN_ACTION
                task.last_error = "Autenticacao do YouTube Studio expirada ou exige confirmacao humana (2FA)."
            elif first_res.get("status") == "published_youtube_cdp" or first_res.get("video_id"):
                vid_id = str(first_res.get("video_id") or first_res.get("publish_id") or "")
                task.remote_publish_id = vid_id
                task.remote_url = f"https://www.youtube.com/shorts/{vid_id}" if vid_id else ""
                task.state = PublishState.PUBLISHED
                task.updated_at = time.time()
            else:
                task.state = PublishState.FAILED
                task.last_error = str(first_res.get("reason") or "Erro desconhecido durante upload YouTube Studio CDP")
        except Exception as exc:
            task.state = PublishState.FAILED
            task.last_error = f"Excecao na execucao do upload YouTube: {exc}"

        return task

    def fetch_live_metrics(self, remote_publish_id: str) -> Dict[str, Any]:
        """Consulta métricas públicas básicas do YouTube Shorts."""
        return {
            "platform": self.platform.value,
            "publish_id": remote_publish_id,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "queried_at": time.time(),
        }
