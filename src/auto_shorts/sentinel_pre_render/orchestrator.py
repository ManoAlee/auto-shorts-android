"""Sentinel Pre-Render Orchestrator.

Master entrypoint for pre-render multimodal validation, creative intelligence,
and automated quality gate enforcement.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    ContentBrief,
    GateResult,
    GateStatus,
    PreviewMode,
    SceneContract,
    SentinelReport,
    StoryboardManifest,
    TitleConsistencyMatrix,
)
from .multimodal_personas import MultimodalReviewPersonas
from .preview_renderer import LowCostPreviewEngine
from .quality_gates_sentinel import SentinelQualityGatesEngine
from .revision_engine import EvidenceGuidedRevisionEngine
from .script_intelligence import ScriptIntelligenceEngine
from .semantic_scene_aligner import SemanticSceneAligner
from .storyboard_engine import StoryboardEngine
from .title_consistency import TitleToContentConsistencyEngine

logger = logging.getLogger("autoshorts.sentinel.orchestrator")


class SentinelPreRenderOrchestrator:
    """Coordinates pre-render inspection, storyboard generation, quality gates, and self-correction."""

    def __init__(
        self,
        out_dir: Path | str = "output/sentinel",
        media_catalog: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = self.out_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.title_engine = TitleToContentConsistencyEngine()
        self.script_engine = ScriptIntelligenceEngine()
        self.aligner = SemanticSceneAligner(media_catalog=media_catalog)
        self.storyboard_engine = StoryboardEngine(out_dir=self.out_dir / "previews")
        self.preview_engine = LowCostPreviewEngine(out_dir=self.out_dir / "previews")
        self.gates_engine = SentinelQualityGatesEngine()
        self.personas = MultimodalReviewPersonas()
        self.revision_engine = EvidenceGuidedRevisionEngine()

    def run_pre_render_validation(
        self,
        brief: ContentBrief,
        script_text: str = "",
        scenes: Optional[List[SceneContract]] = None,
        subtitle_text: str = "",
        preview_mode: PreviewMode = PreviewMode.FULL_PROXY_PREVIEW,
        auto_correct: bool = True,
        alternative_catalog: Optional[Dict[str, List[str]]] = None,
    ) -> SentinelReport:
        """Execute complete Sentinel pre-render audit pipeline with evidence-guided auto-correction."""
        project_id = f"sentinel_{int(time.time())}"
        scenes = scenes or []
        combined_script = script_text or " ".join(s.narration for s in scenes)
        combined_subs = subtitle_text or " ".join(s.subtitle_text or s.narration for s in scenes)
        
        revision_history: List[Dict[str, Any]] = []
        current_title = brief.title
        current_scenes = list(scenes)
        current_subs = combined_subs

        # Up to 3 self-correction iterations
        max_attempts = 3 if auto_correct else 1
        final_report: Optional[SentinelReport] = None

        for attempt in range(1, max_attempts + 1):
            logger.info("Starting Sentinel Pre-Render Run (Attempt %d/%d) for '%s'", attempt, max_attempts, current_title)

            # 1. Title-to-Content Consistency
            matrix = self.title_engine.analyze_consistency(
                title=current_title,
                script_text=combined_script,
                scenes=current_scenes,
            )

            # 2. Script Intelligence
            script_eval = self.script_engine.evaluate_script(
                script_text=combined_script,
                target_duration=brief.target_duration_sec,
                platform=brief.platform,
            )

            # 3. Semantic Scene Alignment
            aligned_scenes, alignment_summary = self.aligner.align_scenes(current_scenes)

            # 4. Storyboard Manifest Construction
            manifest = self.storyboard_engine.build_storyboard(
                project_id=project_id,
                title=current_title,
                scenes=aligned_scenes,
            )

            # 5. Caption Safe Zone Linting
            caption_eval = self.preview_engine.check_caption_safe_zones(
                subtitle_text=current_subs,
                platform=brief.platform,
            )

            # 6. Preview Generation (Proxy video or Stills)
            preview_path = None
            if preview_mode == PreviewMode.FULL_PROXY_PREVIEW:
                proxy = self.preview_engine.render_full_proxy(manifest)
                if proxy:
                    preview_path = str(proxy)
            elif preview_mode == PreviewMode.SCENE_PREVIEW and aligned_scenes:
                sc_proxy = self.preview_engine.render_scene_preview(aligned_scenes[0], platform=brief.platform)
                if sc_proxy:
                    preview_path = str(sc_proxy)

            # 7. Evaluate 10 Quality Gates
            gates = self.gates_engine.evaluate_all_gates(
                matrix=matrix,
                script_eval=script_eval,
                alignment_summary=alignment_summary,
                manifest=manifest,
                caption_eval=caption_eval,
                preview_path=preview_path,
                platform=brief.platform,
            )

            # Collect issues
            detected_issues = []
            for g_id, g_res in gates.items():
                if g_res.status in (GateStatus.FAIL, GateStatus.WARNING):
                    detected_issues.append({
                        "gate": g_id,
                        "status": g_res.status.value,
                        "errors": g_res.errors,
                        "warnings": g_res.warnings,
                    })

            # Check if all critical gates passed
            auth_gate = gates.get("GATE_10_FINAL_RENDER_AUTHORIZATION")
            is_approved = auth_gate.status == GateStatus.PASS if auth_gate else False
            overall_score = auth_gate.score if auth_gate else 0

            recommendations = []
            if not is_approved:
                for issue in detected_issues:
                    recommendations.extend(issue.get("errors", []))

            final_report = SentinelReport(
                project_id=project_id,
                title=current_title,
                is_approved=is_approved,
                overall_score=overall_score,
                gates=gates,
                consistency_matrix=matrix,
                storyboard=manifest,
                proxy_preview_path=preview_path,
                detected_issues=detected_issues,
                recommendations=recommendations,
                revision_history=revision_history,
            )

            # If approved or auto_correct disabled or last attempt, finish
            if is_approved or not auto_correct or attempt >= max_attempts:
                break

            # Perform Targeted Auto-Corrections
            changes_made = False

            # Heal Title Mismatch
            if gates["GATE_01_TITLE_VALIDATION"].status == GateStatus.FAIL or gates["GATE_03_FACT_VALIDATION"].status == GateStatus.FAIL:
                new_title = self.revision_engine.heal_mismatched_title(matrix, combined_script, niche=brief.niche)
                if new_title != current_title:
                    revision_history.append({
                        "attempt": attempt,
                        "type": "TITLE_AUTO_CORRECTION",
                        "old_title": current_title,
                        "new_title": new_title,
                    })
                    current_title = new_title
                    changes_made = True

            # Heal Caption Safe Zones
            if gates["GATE_07_CAPTION_VALIDATION"].status == GateStatus.FAIL:
                healed_subs = self.revision_engine.heal_captions_for_safe_zones(current_subs)
                if healed_subs != current_subs:
                    revision_history.append({
                        "attempt": attempt,
                        "type": "CAPTION_SAFE_ZONE_REFLOW",
                        "old_lines_count": len(current_subs.splitlines()),
                        "new_lines_count": len(healed_subs.splitlines()),
                    })
                    current_subs = healed_subs
                    changes_made = True

            # Heal Mismatched Scene Media
            if gates["GATE_04_VISUAL_ALIGNMENT"].status == GateStatus.FAIL and alternative_catalog:
                for sc in current_scenes:
                    if sc.validation_status == "FAIL":
                        old_asset = sc.media_asset
                        self.revision_engine.heal_mismatched_scene_media(sc, alternative_catalog=alternative_catalog)
                        if sc.media_asset != old_asset:
                            revision_history.append({
                                "attempt": attempt,
                                "type": "SCENE_MEDIA_REPLACEMENT",
                                "scene_id": sc.scene_id,
                                "old_asset": old_asset,
                                "new_asset": sc.media_asset,
                            })
                            changes_made = True

            if not changes_made:
                break

        # Persist report JSON
        report_file = self.reports_dir / f"{project_id}_report.json"
        report_file.write_text(json.dumps(final_report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Sentinel Audit Complete. Approved: %s, Score: %d/100, Report: %s", final_report.is_approved, final_report.overall_score, report_file)
        return final_report
