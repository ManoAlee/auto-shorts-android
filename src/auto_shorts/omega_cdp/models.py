"""Omega CDP Control Engine — Core Domain Models, Enums and Task Contracts."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class Platform(str, enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    TWITCH = "twitch"
    KICK = "kick"


class AdapterType(str, enum.Enum):
    OFFICIAL_API = "OFFICIAL_API"
    CDP_BROWSER = "CDP_BROWSER"
    HYBRID = "HYBRID"


class PublishState(str, enum.Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REQUIRES_HUMAN_ACTION = "REQUIRES_HUMAN_ACTION"


VALID_PUBLISH_TRANSITIONS: Dict[PublishState, set[PublishState]] = {
    PublishState.CREATED: {PublishState.VALIDATED, PublishState.FAILED},
    PublishState.VALIDATED: {PublishState.READY_FOR_REVIEW, PublishState.APPROVED, PublishState.FAILED},
    PublishState.READY_FOR_REVIEW: {PublishState.APPROVED, PublishState.FAILED, PublishState.REQUIRES_HUMAN_ACTION},
    PublishState.APPROVED: {PublishState.QUEUED, PublishState.FAILED},
    PublishState.QUEUED: {PublishState.UPLOADING, PublishState.FAILED, PublishState.REQUIRES_HUMAN_ACTION},
    PublishState.UPLOADING: {PublishState.PROCESSING, PublishState.PUBLISHED, PublishState.FAILED, PublishState.REQUIRES_HUMAN_ACTION},
    PublishState.PROCESSING: {PublishState.PUBLISHED, PublishState.FAILED, PublishState.REQUIRES_HUMAN_ACTION},
    PublishState.PUBLISHED: {PublishState.VERIFIED, PublishState.FAILED},
    PublishState.VERIFIED: set(),
    PublishState.FAILED: {PublishState.QUEUED, PublishState.READY_FOR_REVIEW, PublishState.REQUIRES_HUMAN_ACTION},
    PublishState.REQUIRES_HUMAN_ACTION: {PublishState.READY_FOR_REVIEW, PublishState.QUEUED, PublishState.FAILED},
}


@dataclass
class PlatformCapability:
    platform: Platform
    primary_adapter: AdapterType
    supports_official_api: bool
    supports_cdp_automation: bool
    allowed_operations: List[str]
    rate_limit_per_day: int
    requires_human_auth_setup: bool
    notes: str = ""


@dataclass
class SessionProfile:
    platform: Platform
    profile_dir: str
    cookies_path: str
    is_authenticated: bool = False
    last_validated: float = 0.0
    account_handle: str = ""
    lock_held: bool = False
    auth_mode: str = "cookies_and_profile"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualEvidence:
    evidence_id: str
    task_id: str
    platform: str
    url: str
    screenshot_path: str
    page_title: str
    verified_status: str
    title_matches: bool
    discrepancies: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PublishTask:
    task_id: str
    platform: Platform
    video_path: str
    title: str
    description: str
    hashtags: List[str] = field(default_factory=list)
    state: PublishState = PublishState.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    remote_publish_id: str = ""
    remote_url: str = ""
    niche: str = "geral"
    approved_by: str = ""
    approved_at: float = 0.0
    last_error: str = ""
    retry_count: int = 0
    max_retries: int = 2
    visual_evidence_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["platform"] = self.platform.value if isinstance(self.platform, Platform) else str(self.platform)
        d["state"] = self.state.value if isinstance(self.state, PublishState) else str(self.state)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PublishTask:
        clean = dict(data)
        if "platform" in clean:
            clean["platform"] = Platform(clean["platform"])
        if "state" in clean:
            clean["state"] = PublishState(clean["state"])
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in clean.items() if k in valid_keys}
        return cls(**filtered)
