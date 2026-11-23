"""Multimodal Review Personas for Pre-Render Quality Assurance.

Executes sequential, memory-efficient reviews across 8 specialized domain personas:
1. CREATIVE DIRECTOR: Art direction, pacing, hook strength, overall appeal.
2. SCRIPT EDITOR: Clarity, narrative arc (beginning/middle/end), tone.
3. VISUAL SEMANTIC ANALYST: Alignment between spoken sentences and visual assets.
4. AUDIO DIRECTOR: Narration speed (WPM), pauses, duration balance.
5. MOTION DESIGN REVIEWER: Subtitle legibility, line wrapping, platform safe zones.
6. FACT-CHECK EDITOR: Verifiable numerical claims vs delivered content.
7. PLATFORM SPECIALIST: YouTube Shorts / TikTok / Reels constraints.
8. QA ORCHESTRATOR: Consolidates findings and issues approval verdict.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .contracts import (
    ContentBrief,
    GateResult,
    GateStatus,
    SceneContract,
    StoryboardManifest,
    TitleConsistencyMatrix,
)

logger = logging.getLogger("autoshorts.sentinel.multimodal_personas")


class MultimodalReviewPersonas:
    """Sequential executor for specialized pre-render review personas."""

    @staticmethod
    def review_creative_director(
        brief: ContentBrief,
        script_eval: Dict[str, Any],
        matrix: TitleConsistencyMatrix,
    ) -> Dict[str, Any]:
        """Creative Director: evaluates art direction, hook magnetism, and core promise."""
        score = 85
        notes = []
        
        if matrix.is_mismatched:
            score -= 30
            notes.append(f"A promessa do título não condiz com o conteúdo planejado: {matrix.mismatch_reason}")

        if script_eval.get("hook_score", 100) < 60:
            score -= 20
            notes.append("O gancho inicial carece de magnetismo e curiosidade.")

        passed = score >= 70
        return {
            "persona": "Creative Director",
            "score": max(0, min(100, score)),
            "passed": passed,
            "notes": notes,
            "verdict": "APROVADO" if passed else "REVISÃO_NECESSÁRIA",
        }

    @staticmethod
    def review_script_editor(script_eval: Dict[str, Any]) -> Dict[str, Any]:
        """Script Editor: validates structure, natural phrasing, and duration."""
        score = script_eval.get("overall_score", 80)
        errors = script_eval.get("errors", [])
        warnings = script_eval.get("warnings", [])
        passed = len(errors) == 0 and score >= 70
        return {
            "persona": "Script Editor",
            "score": score,
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "verdict": "APROVADO" if passed else "REJEITADO_PELO_ROTEIRO",
        }

    @staticmethod
    def review_visual_semantic_analyst(alignment_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Visual Semantic Analyst: validates scene-by-scene audio-visual correlation."""
        score = alignment_summary.get("average_alignment_score", 80)
        mismatches = alignment_summary.get("mismatched_scenes", [])
        passed = len(mismatches) == 0 and score >= 70
        return {
            "persona": "Visual Semantic Analyst",
            "score": score,
            "passed": passed,
            "mismatches": mismatches,
            "notes": [f"Detectadas {len(mismatches)} cena(s) com contradição semântica."] if mismatches else [],
            "verdict": "APROVADO" if passed else "CENAS_DESALINHADAS",
        }

    @staticmethod
    def review_audio_director(script_eval: Dict[str, Any]) -> Dict[str, Any]:
        """Audio Director: validates estimated narration pace and duration limits."""
        est_dur = script_eval.get("estimated_duration_sec", 45.0)
        pacing_score = script_eval.get("pacing_score", 90)
        passed = pacing_score >= 70 and est_dur <= 60.0
        return {
            "persona": "Audio Director",
            "score": pacing_score,
            "passed": passed,
            "estimated_duration_sec": est_dur,
            "notes": ["Duração do áudio dentro do limite planejado."] if passed else [f"Áudio excede o limite: {est_dur:.1f}s."],
            "verdict": "APROVADO" if passed else "DURAÇÃO_EXCESSIVA",
        }

    @staticmethod
    def review_motion_design(caption_eval: Dict[str, Any]) -> Dict[str, Any]:
        """Motion Design Reviewer: validates subtitles within safe zones."""
        passed = caption_eval.get("passed", True)
        score = 95 if passed else 50
        return {
            "persona": "Motion Design Reviewer",
            "score": score,
            "passed": passed,
            "overflow_lines": caption_eval.get("overflow_lines", []),
            "notes": [caption_eval.get("issue")] if not passed else ["Legendas 100% dentro da safe zone."],
            "verdict": "APROVADO" if passed else "LEGENDA_FORA_DA_SAFE_ZONE",
        }

    @staticmethod
    def review_fact_check(matrix: TitleConsistencyMatrix) -> Dict[str, Any]:
        """Fact-Check Editor: verifies numerical and claim integrity."""
        passed = not matrix.is_mismatched
        score = matrix.consistency_score
        return {
            "persona": "Fact-Check Editor",
            "score": score,
            "passed": passed,
            "expected_count": matrix.expected_count,
            "delivered_count": matrix.delivered_count,
            "notes": [matrix.mismatch_reason] if matrix.mismatch_reason else ["Afirmações verificadas com coerência."],
            "verdict": "APROVADO" if passed else "FATO_NÃO_ENTREGUE",
        }

    @staticmethod
    def review_platform_specialist(brief: ContentBrief, total_dur: float) -> Dict[str, Any]:
        """Platform Specialist: enforces strict platform constraints (YouTube Shorts, Reels, TikTok)."""
        max_dur = 60.0 if brief.platform == "youtube_shorts" else 90.0
        passed = total_dur <= max_dur and total_dur >= 10.0
        score = 95 if passed else 45
        return {
            "persona": "Platform Specialist",
            "score": score,
            "passed": passed,
            "platform": brief.platform,
            "total_duration": total_dur,
            "notes": [f"Duração ({total_dur:.1f}s) compatível com {brief.platform}."] if passed else [f"Duração ({total_dur:.1f}s) incompatível com {brief.platform} (máx {max_dur}s)."],
            "verdict": "APROVADO" if passed else "INCOMPATÍVEL_COM_PLATAFORMA",
        }
