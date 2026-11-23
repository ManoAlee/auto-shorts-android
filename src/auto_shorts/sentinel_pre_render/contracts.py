"""Data Contracts & Domain Entities for Auto Shorts Sentinel Pre-Render Subsystem."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    NOT_EVALUATED = "NOT_EVALUATED"


class PreviewMode(str, Enum):
    STORYBOARD_ONLY = "STORYBOARD_ONLY"
    SCENE_PREVIEW = "SCENE_PREVIEW"
    AUDIO_SYNC_PREVIEW = "AUDIO_SYNC_PREVIEW"
    FULL_PROXY_PREVIEW = "FULL_PROXY_PREVIEW"
    FINAL_RENDER = "FINAL_RENDER"


@dataclass
class ContentBrief:
    """Creative brief and high-level contract for the planned short."""
    title: str
    topic: str
    target_audience: str = "Público geral / Entusiastas"
    editorial_promise: str = ""
    key_claims: List[str] = field(default_factory=list)
    target_duration_sec: float = 60.0
    platform: str = "youtube_shorts"  # youtube_shorts, tiktok, instagram_reels
    niche: str = "geral"
    hook_hypothesis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SceneContract:
    """Structured contract representing an individual audiovisual scene."""
    scene_id: str
    timestamp_start: float
    timestamp_end: float
    duration_seconds: float
    narration: str
    visual_intent: str
    media_asset: str  # Path or filename
    media_type: str = "video"  # "video", "photo", "broll", "motion_graphic"
    expected_objects: List[str] = field(default_factory=list)
    detected_objects: List[str] = field(default_factory=list)
    representative_frame: Optional[str] = None
    subtitle_text: str = ""
    transition: str = "fade"
    validation_status: str = "PENDING"  # PENDING, PASS, FAIL, REQUIRES_REVIEW
    alignment_score: int = 100  # 0 to 100
    alignment_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneContract":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StoryboardManifest:
    """Pre-render storyboard manifest containing all planned scene contracts."""
    project_id: str
    title: str
    total_duration: float
    scenes: List[SceneContract] = field(default_factory=list)
    contact_sheet_path: Optional[str] = None
    html_preview_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scenes"] = [s.to_dict() if isinstance(s, SceneContract) else s for s in self.scenes]
        return d


@dataclass
class TitleConsistencyMatrix:
    """Matrix evaluating explicit/implicit claims in title vs delivered script and visuals."""
    title: str
    explicit_promises: List[str] = field(default_factory=list)
    expected_count: Optional[int] = None
    delivered_count: int = 0
    claims: List[Dict[str, Any]] = field(default_factory=list)
    is_mismatched: bool = False
    mismatch_reason: Optional[str] = None
    consistency_score: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    """Outcome of an individual Quality Gate check."""
    gate_id: str
    name: str
    status: GateStatus
    score: int  # 0 to 100
    critical: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, GateStatus) else str(self.status)
        return d


@dataclass
class SentinelReport:
    """Consolidated pre-render multimodal audit report and final render authorization."""
    project_id: str
    title: str
    is_approved: bool
    overall_score: int  # 0 to 100
    gates: Dict[str, GateResult] = field(default_factory=dict)
    consistency_matrix: Optional[TitleConsistencyMatrix] = None
    storyboard: Optional[StoryboardManifest] = None
    proxy_preview_path: Optional[str] = None
    detected_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    revision_history: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "is_approved": self.is_approved,
            "overall_score": self.overall_score,
            "gates": {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.gates.items()},
            "consistency_matrix": self.consistency_matrix.to_dict() if self.consistency_matrix else None,
            "storyboard": self.storyboard.to_dict() if self.storyboard else None,
            "proxy_preview_path": self.proxy_preview_path,
            "detected_issues": self.detected_issues,
            "recommendations": self.recommendations,
            "revision_history": self.revision_history,
            "timestamp": self.timestamp,
        }
