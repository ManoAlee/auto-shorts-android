"""Omega CDP Control Engine — Autonomous Multiplatform Browser & Publishing Control."""

from .models import (
    AdapterType,
    Platform,
    PlatformCapability,
    PublishState,
    PublishTask,
    SessionProfile,
    VisualEvidence,
    VALID_PUBLISH_TRANSITIONS,
)
from .registry import PlatformCapabilityRegistry
from .session_manager import SecureSessionManager
from .approval_gateway import UserApprovalGateway
from .engine import OmegaCDPEngine
from .visual_qa import VisualQAInspector
from .orchestrator import OmegaControlOrchestrator

__all__ = [
    "AdapterType",
    "Platform",
    "PlatformCapability",
    "PublishState",
    "PublishTask",
    "SessionProfile",
    "VisualEvidence",
    "VALID_PUBLISH_TRANSITIONS",
    "PlatformCapabilityRegistry",
    "SecureSessionManager",
    "UserApprovalGateway",
    "OmegaCDPEngine",
    "VisualQAInspector",
    "OmegaControlOrchestrator",
]
