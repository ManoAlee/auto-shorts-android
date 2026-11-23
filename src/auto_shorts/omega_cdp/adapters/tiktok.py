"""TikTok Studio Web Adapter — Native CDP Automation for TikTok Web Studio."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..engine import OmegaCDPEngine
from ..models import Platform, PublishState, PublishTask
from .base import BasePlatformAdapter

logger = logging.getLogger("autoshorts.omega_cdp.tiktok")


class TikTokOmegaAdapter(BasePlatformAdapter):
    """Adaptador CDP nativo para publicação autorizada no TikTok Studio Web."""

    @property
    def platform(self) -> Platform:
        return Platform.TIKTOK

    def check_auth_status(self) -> Dict[str, Any]:
        profile = self.session_manager.get_session_profile(self.platform)
        env_sid = bool(os.getenv("TIKTOK_SESSIONID", "").strip())
        return {
            "platform": self.platform.value,
            "has_sessionid_cookie": profile.is_authenticated or env_sid,
            "profile_dir": profile.profile_dir,
            "ready_to_publish": profile.is_authenticated or env_sid,
        }

    def prepare_task(self, task: PublishTask) -> PublishTask:
        # Higienizar legendas para o TikTok: remover tags de concorrentes (#shorts, #reels)
        caption = task.description or task.title
        cleaned = re.sub(r"(?i)#(shorts|youtubeshorts|reels|reelsbrasil)\b", "", caption)
        task.description = " ".join(cleaned.split())[:2100]
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

        from ...tiktok_cdp import publish_batch_to_tiktok_cdp
        try:
            res = publish_batch_to_tiktok_cdp(
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
                task.last_error = "Sessao do TikTok Studio Web expirada. E necessario login interativo humano."
            elif first_res.get("status") == "published_tiktok_cdp" or first_res.get("tiktok_publish_id"):
                pub_id = str(first_res.get("tiktok_publish_id") or first_res.get("publish_id") or "")
                task.remote_publish_id = pub_id
                task.remote_url = f"https://www.tiktok.com/@creator/video/{pub_id}" if pub_id else ""
                task.state = PublishState.PUBLISHED
                task.updated_at = time.time()
            else:
                task.state = PublishState.FAILED
                task.last_error = str(first_res.get("reason") or "Erro desconhecido durante upload TikTok CDP")
        except Exception as exc:
            task.state = PublishState.FAILED
            task.last_error = f"Excecao na execucao do upload TikTok: {exc}"

        return task

    def fetch_live_metrics(self, remote_publish_id: str) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "publish_id": remote_publish_id,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "queried_at": time.time(),
        }
