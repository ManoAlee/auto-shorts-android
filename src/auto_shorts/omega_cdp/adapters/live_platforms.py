"""Twitch and Kick Live Platforms Adapter — Authorized Stream & VOD Telemetry."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..engine import OmegaCDPEngine
from ..models import Platform, PublishState, PublishTask
from .base import BasePlatformAdapter

logger = logging.getLogger("autoshorts.omega_cdp.live")


class TwitchKickAdapter(BasePlatformAdapter):
    """Adaptador de observabilidade e monitoramento de transmissões ao vivo para Twitch e Kick."""

    def __init__(self, session_manager: Any, platform_type: Platform = Platform.TWITCH) -> None:
        super().__init__(session_manager)
        self._platform_type = platform_type

    @property
    def platform(self) -> Platform:
        return self._platform_type

    def check_auth_status(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "mode": "stream_monitor_public_authorized",
            "ready_to_monitor": True,
        }

    def prepare_task(self, task: PublishTask) -> PublishTask:
        task.state = PublishState.VALIDATED
        task.updated_at = time.time()
        return task

    def execute_upload(self, task: PublishTask, engine: Optional[OmegaCDPEngine] = None) -> PublishTask:
        # Plataformas de streaming ao vivo não operam uploads diretos de Shorts neste fluxo
        task.state = PublishState.FAILED
        task.last_error = f"Publicacao direta de shorts desabilitada para {self.platform.value}. Usar para monitoramento."
        return task

    def fetch_live_metrics(self, remote_publish_id: str) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "channel_or_vod": remote_publish_id,
            "is_live": False,
            "viewer_count": 0,
            "queried_at": time.time(),
        }
