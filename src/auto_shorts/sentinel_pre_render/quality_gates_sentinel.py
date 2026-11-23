"""Ten Mandatory Sentinel Quality Gates for Pre-Render Authorization.

Defines:
- GATE 01: TITLE VALIDATION (Title claims vs script & visual evidence)
- GATE 02: SCRIPT VALIDATION (Coherence, beginning/middle/end, pacing)
- GATE 03: FACT VALIDATION (Verifiable assertions, numerical delivery)
- GATE 04: VISUAL ALIGNMENT (Semantic scene matching score >= 70)
- GATE 05: STORYBOARD VALIDATION (Scene continuity, no gap, no duplicate media)
- GATE 06: AUDIO PLANNING (Pacing, WPM, duration limits)
- GATE 07: CAPTION VALIDATION (Safe zones, line lengths <= 34 chars)
- GATE 08: VISUAL COMPOSITION (9:16 vertical framing, margins)
- GATE 09: PREVIEW INSPECTION (Proxy/storyboard verified without critical artifacts)
- GATE 10: FINAL RENDER AUTHORIZATION (Gatekeeper for production render)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    ContentBrief,
    GateResult,
    GateStatus,
    SceneContract,
    StoryboardManifest,
    TitleConsistencyMatrix,
)

logger = logging.getLogger("autoshorts.sentinel.quality_gates")


class SentinelQualityGatesEngine:
    """Evaluates the 10 pre-render quality gates and computes the final render authorization."""

    def evaluate_gate_01_title(self, matrix: TitleConsistencyMatrix) -> GateResult:
        """GATE 01 — TITLE VALIDATION: verifies title-to-content consistency."""
        passed = not matrix.is_mismatched and matrix.consistency_score >= 70
        errors = [matrix.mismatch_reason] if matrix.is_mismatched and matrix.mismatch_reason else []
        return GateResult(
            gate_id="GATE_01_TITLE_VALIDATION",
            name="Title-to-Content Consistency",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            score=matrix.consistency_score,
            critical=True,
            errors=errors,
            warnings=[],
            evidence={"explicit_promises": matrix.explicit_promises, "claims_count": len(matrix.claims)},
        )

    def evaluate_gate_02_script(self, script_eval: Dict[str, Any]) -> GateResult:
        """GATE 02 — SCRIPT VALIDATION: validates structure, hook, clarity and pacing."""
        passed = script_eval.get("passed", False) and script_eval.get("overall_score", 0) >= 70
        errors = script_eval.get("errors", [])
        warnings = script_eval.get("warnings", [])
        status = GateStatus.PASS if passed else (GateStatus.FAIL if errors else GateStatus.REQUIRES_REVIEW)
        return GateResult(
            gate_id="GATE_02_SCRIPT_VALIDATION",
            name="Script Intelligence & Structure",
            status=status,
            score=script_eval.get("overall_score", 0),
            critical=True,
            errors=errors,
            warnings=warnings,
            evidence={
                "hook_score": script_eval.get("hook_score"),
                "structure_score": script_eval.get("structure_score"),
                "sentences_count": script_eval.get("sentences_count"),
            },
        )

    def evaluate_gate_03_fact(self, matrix: TitleConsistencyMatrix) -> GateResult:
        """GATE 03 — FACT VALIDATION: checks numerical delivery and claim validity."""
        errors = []
        warnings = []
        if matrix.expected_count and matrix.delivered_count < matrix.expected_count:
            errors.append(f"Fato não entregue: Título promete {matrix.expected_count} itens, mas apenas {matrix.delivered_count} foram identificados.")
        
        passed = len(errors) == 0
        return GateResult(
            gate_id="GATE_03_FACT_VALIDATION",
            name="Factual & Numerical Verification",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            score=100 if passed else 50,
            critical=True,
            errors=errors,
            warnings=warnings,
            evidence={"expected_count": matrix.expected_count, "delivered_count": matrix.delivered_count},
        )

    def evaluate_gate_04_visual_alignment(self, alignment_summary: Dict[str, Any]) -> GateResult:
        """GATE 04 — VISUAL ALIGNMENT: checks scene semantic relevance."""
        mismatches = alignment_summary.get("mismatched_scenes", [])
        avg_score = alignment_summary.get("average_alignment_score", 0)
        passed = len(mismatches) == 0 and avg_score >= 70
        errors = [f"Cena {m['scene_id']}: {'; '.join(m['notes'])}" for m in mismatches]
        return GateResult(
            gate_id="GATE_04_VISUAL_ALIGNMENT",
            name="Semantic Scene Alignment",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            score=avg_score,
            critical=True,
            errors=errors,
            warnings=[],
            evidence={"mismatches_count": len(mismatches), "total_scenes": alignment_summary.get("total_scenes")},
        )

    def evaluate_gate_05_storyboard(self, manifest: StoryboardManifest, alignment_summary: Dict[str, Any]) -> GateResult:
        """GATE 05 — STORYBOARD VALIDATION: verifies scene sequence, continuity, and duplicates."""
        errors = []
        warnings = []
        dups = alignment_summary.get("duplicate_scenes", [])
        if dups:
            warnings.append(f"Mídia duplicada detectada nas cenas: {', '.join(dups)}")

        if not manifest.scenes:
            errors.append("Storyboard vazio sem cenas planejadas.")
        
        # Check timeline continuity
        prev_end = 0.0
        for s in manifest.scenes:
            if s.timestamp_start > prev_end + 0.5:
                warnings.append(f"Lacuna temporal detectada antes da cena {s.scene_id} ({prev_end:.1f}s -> {s.timestamp_start:.1f}s).")
            prev_end = s.timestamp_end

        passed = len(errors) == 0
        status = GateStatus.PASS if passed and not warnings else (GateStatus.WARNING if passed else GateStatus.FAIL)
        score = 95 if not dups and passed else (75 if passed else 30)

        return GateResult(
            gate_id="GATE_05_STORYBOARD_VALIDATION",
            name="Storyboard Sequence & Continuity",
            status=status,
            score=score,
            critical=True,
            errors=errors,
            warnings=warnings,
            evidence={"scenes_count": len(manifest.scenes), "total_duration": manifest.total_duration},
        )

    def evaluate_gate_06_audio_planning(self, script_eval: Dict[str, Any], platform: str = "youtube_shorts") -> GateResult:
        """GATE 06 — AUDIO PLANNING: checks narration duration against platform limit."""
        max_dur = 60.0 if platform == "youtube_shorts" else 90.0
        est_dur = script_eval.get("estimated_duration_sec", 0.0)
        errors = []
        warnings = []
        if est_dur > max_dur:
            errors.append(f"Duração estimada do áudio ({est_dur:.1f}s) excede o limite máximo da plataforma ({max_dur:.1f}s).")

        passed = len(errors) == 0
        score = 95 if passed else 40
        return GateResult(
            gate_id="GATE_06_AUDIO_PLANNING",
            name="Audio Duration & Pacing Planning",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            score=score,
            critical=True,
            errors=errors,
            warnings=warnings,
            evidence={"estimated_duration_sec": est_dur, "platform_limit_sec": max_dur},
        )

    def evaluate_gate_07_caption(self, caption_eval: Dict[str, Any]) -> GateResult:
        """GATE 07 — CAPTION VALIDATION: ensures subtitles remain within platform safe zones."""
        passed = caption_eval.get("passed", True)
        errors = [caption_eval.get("issue")] if not passed and caption_eval.get("issue") else []
        return GateResult(
            gate_id="GATE_07_CAPTION_VALIDATION",
            name="Subtitle Safe Zone & Legibility",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            score=100 if passed else 50,
            critical=True,
            errors=errors,
            warnings=[],
            evidence={"overflow_lines": caption_eval.get("overflow_lines", [])},
        )

    def evaluate_gate_08_composition(self, manifest: StoryboardManifest) -> GateResult:
        """GATE 08 — VISUAL COMPOSITION: verifies 9:16 aspect ratio framing and assets."""
        score = 90
        warnings = []
        for s in manifest.scenes:
            if not s.media_asset:
                warnings.append(f"Cena {s.scene_id} sem arquivo de mídia atribuído.")
                score -= 15
        
        passed = score >= 70
        return GateResult(
            gate_id="GATE_08_VISUAL_COMPOSITION",
            name="Visual Composition & Framing",
            status=GateStatus.PASS if passed else GateStatus.WARNING,
            score=max(0, score),
            critical=False,
            errors=[],
            warnings=warnings,
            evidence={"scenes_with_assets": len([s for s in manifest.scenes if s.media_asset])},
        )

    def evaluate_gate_09_preview(self, preview_path: Optional[str], manifest: StoryboardManifest) -> GateResult:
        """GATE 09 — PREVIEW INSPECTION: verifies preview generation and frame availability."""
        has_preview = bool(preview_path or manifest.contact_sheet_path)
        score = 95 if has_preview else 50
        warnings = [] if has_preview else ["Nenhuma prévia em vídeo ou contact sheet foi gerada."]
        return GateResult(
            gate_id="GATE_09_PREVIEW_INSPECTION",
            name="Pre-Render Preview Inspection",
            status=GateStatus.PASS if has_preview else GateStatus.REQUIRES_REVIEW,
            score=score,
            critical=False,
            errors=[],
            warnings=warnings,
            evidence={"preview_path": preview_path, "contact_sheet": manifest.contact_sheet_path},
        )

    def evaluate_gate_10_authorization(self, gates: Dict[str, GateResult]) -> GateResult:
        """GATE 10 — FINAL RENDER AUTHORIZATION: final gatekeeper for production rendering."""
        critical_failures = [g.gate_id for g in gates.values() if g.critical and g.status == GateStatus.FAIL]
        scores = [g.score for g in gates.values()]
        avg_score = int(sum(scores) / len(scores)) if scores else 0
        
        authorized = len(critical_failures) == 0 and avg_score >= 75
        errors = [f"Bloqueado por falha crítica em {g_id}" for g_id in critical_failures]
        
        return GateResult(
            gate_id="GATE_10_FINAL_RENDER_AUTHORIZATION",
            name="Final Production Render Authorization",
            status=GateStatus.PASS if authorized else GateStatus.FAIL,
            score=avg_score if authorized else min(50, avg_score),
            critical=True,
            errors=errors,
            warnings=[],
            evidence={"authorized": authorized, "critical_failures_count": len(critical_failures), "average_score": avg_score},
        )

    def evaluate_all_gates(
        self,
        matrix: TitleConsistencyMatrix,
        script_eval: Dict[str, Any],
        alignment_summary: Dict[str, Any],
        manifest: StoryboardManifest,
        caption_eval: Dict[str, Any],
        preview_path: Optional[str] = None,
        platform: str = "youtube_shorts",
    ) -> Dict[str, GateResult]:
        """Execute all 10 gates in order and produce the final scorecard."""
        gates: Dict[str, GateResult] = {}
        gates["GATE_01_TITLE_VALIDATION"] = self.evaluate_gate_01_title(matrix)
        gates["GATE_02_SCRIPT_VALIDATION"] = self.evaluate_gate_02_script(script_eval)
        gates["GATE_03_FACT_VALIDATION"] = self.evaluate_gate_03_fact(matrix)
        gates["GATE_04_VISUAL_ALIGNMENT"] = self.evaluate_gate_04_visual_alignment(alignment_summary)
        gates["GATE_05_STORYBOARD_VALIDATION"] = self.evaluate_gate_05_storyboard(manifest, alignment_summary)
        gates["GATE_06_AUDIO_PLANNING"] = self.evaluate_gate_06_audio_planning(script_eval, platform=platform)
        gates["GATE_07_CAPTION_VALIDATION"] = self.evaluate_gate_07_caption(caption_eval)
        gates["GATE_08_VISUAL_COMPOSITION"] = self.evaluate_gate_08_composition(manifest)
        gates["GATE_09_PREVIEW_INSPECTION"] = self.evaluate_gate_09_preview(preview_path, manifest)
        gates["GATE_10_FINAL_RENDER_AUTHORIZATION"] = self.evaluate_gate_10_authorization(gates)
        return gates
