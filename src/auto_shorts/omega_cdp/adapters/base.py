"""Base Platform Adapter Specification."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..engine import OmegaCDPEngine
from ..models import Platform, PublishState, PublishTask
from ..session_manager import SecureSessionManager


class BasePlatformAdapter(ABC):
    """Contrato base para adaptadores de publicação e inspeção de plataformas."""

    def __init__(self, session_manager: SecureSessionManager) -> None:
        self.session_manager = session_manager

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Plataforma atendida pelo adaptador."""
        ...

    @abstractmethod
    def check_auth_status(self) -> Dict[str, Any]:
        """Inspeciona credenciais e estado da sessão sem mutação."""
        ...

    @abstractmethod
    def prepare_task(self, task: PublishTask) -> PublishTask:
        """Valida e ajusta metadados (título, limites de caracteres, tags)."""
        ...

    @abstractmethod
    def execute_upload(self, task: PublishTask, engine: Optional[OmegaCDPEngine] = None) -> PublishTask:
        """Executa upload através do canal oficial ou CDP autorizado."""
        ...

    @abstractmethod
    def fetch_live_metrics(self, remote_publish_id: str) -> Dict[str, Any]:
        """Consulta métricas legítimas de engajamento (views, likes, comments)."""
        ...
