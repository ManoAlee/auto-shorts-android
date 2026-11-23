"""AUTO SHORTS SENTINEL — Pre-Render Multimodal Validation & Creative Intelligence Harness.

Provides pre-render intelligence, storyboard-first validation, semantic scene alignment,
lightweight proxy rendering, and 10 mandatory Quality Gates before final video production.
"""

from .contracts import (
    ContentBrief,
    GateResult,
    GateStatus,
    SceneContract,
    SentinelReport,
    StoryboardManifest,
    TitleConsistencyMatrix,
)
from .orchestrator import SentinelPreRenderOrchestrator
from .preview_renderer import LowCostPreviewEngine, PreviewMode
from .quality_gates_sentinel import SentinelQualityGatesEngine
from .revision_engine import EvidenceGuidedRevisionEngine
from .script_intelligence import ScriptIntelligenceEngine
from .semantic_scene_aligner import SemanticSceneAligner
from .storyboard_engine import StoryboardEngine
from .title_consistency import TitleToContentConsistencyEngine

__all__ = [
    "ContentBrief",
    "SceneContract",
    "StoryboardManifest",
    "TitleConsistencyMatrix",
    "GateStatus",
    "GateResult",
    "SentinelReport",
    "PreviewMode",
    "TitleToContentConsistencyEngine",
    "ScriptIntelligenceEngine",
    "SemanticSceneAligner",
    "StoryboardEngine",
    "LowCostPreviewEngine",
    "SentinelQualityGatesEngine",
    "EvidenceGuidedRevisionEngine",
    "SentinelPreRenderOrchestrator",
]
