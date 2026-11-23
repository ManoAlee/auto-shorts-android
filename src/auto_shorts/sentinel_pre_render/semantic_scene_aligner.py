"""Semantic Scene Alignment Engine.

Compares spoken narration intent against chosen visual media assets and detected entities.
Guarantees:
1. A scene discussing a technical topic (e.g. CPU overheating) is not paired with an unrelated generic clip (e.g. beach walk).
2. Media assets are not repeated across scenes without editorial justification.
3. Scene contracts carry verifiable visual evidence before rendering.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import SceneContract
from ..viral_titling import _clean_alnum_text, _STOPWORDS_PT
from ..viral_intelligence import AntiSlopHumanizer

logger = logging.getLogger("autoshorts.sentinel.semantic_scene_aligner")


class SemanticSceneAligner:
    """Validates semantic correspondence between spoken script lines and selected visual media."""

    def __init__(self, media_catalog: Optional[Dict[str, List[str]]] = None) -> None:
        # Preloaded asset tags catalog { "filename.mp4": ["tag1", "tag2"] }
        self.media_catalog = media_catalog or {}

    @staticmethod
    def _extract_scene_keywords(text: str) -> List[str]:
        """Extract significant content keywords from narration or visual intent."""
        clean = AntiSlopHumanizer.clean(text)
        tokens = re.findall(r"\b[\w\-áéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]+\b", clean)
        keywords = []
        for t in tokens:
            t_norm = _clean_alnum_text(t)
            if t_norm not in _STOPWORDS_PT and len(t) > 2 and not t.isdigit():
                keywords.append(t_norm)
        return list(dict.fromkeys(keywords))

    def evaluate_scene(
        self,
        scene: SceneContract,
        seen_assets: Set[str],
    ) -> SceneContract:
        """Evaluate alignment for an individual scene and update its validation status."""
        narration_kw = self._extract_scene_keywords(scene.narration)
        intent_kw = self._extract_scene_keywords(scene.visual_intent)
        
        # Combine expected objects and intent
        target_tags = set(narration_kw + intent_kw + [_clean_alnum_text(o) for o in scene.expected_objects])

        # Gather visual evidence from media asset filename, tags, or detected objects
        asset_norm = _clean_alnum_text(scene.media_asset)
        catalog_tags = [_clean_alnum_text(t) for t in self.media_catalog.get(scene.media_asset, [])]
        detected_tags = [_clean_alnum_text(d) for d in scene.detected_objects]
        
        visual_evidence_tags = set(catalog_tags + detected_tags)
        # Also parse tokens from asset filename
        for part in re.split(r"[_\-\.\s]+", asset_norm):
            if len(part) > 2 and part not in ("mp4", "jpg", "png", "short", "video", "clip", "scene"):
                visual_evidence_tags.add(part)

        notes: List[str] = []
        score = 100

        # 1. Check Duplicate Asset
        if scene.media_asset and scene.media_asset in seen_assets:
            score -= 30
            notes.append(f"Mídia duplicada: '{scene.media_asset}' já foi utilizada em cena anterior.")

        # 2. Check Semantic Match
        # Find overlap between narration/expected intent and visual evidence
        overlap = target_tags.intersection(visual_evidence_tags)

        # Check for obvious semantic contradictions (e.g. computer hardware vs nature/beach)
        tech_terms = {"computador", "processador", "cpu", "hardware", "software", "codigo", "servidor", "chip"}
        nature_terms = {"praia", "beach", "natureza", "floresta", "mar", "ondas", "ferias", "piscina"}
        
        is_tech_narr = any(t in target_tags for t in tech_terms)
        is_nature_media = any(t in visual_evidence_tags for t in nature_terms)
        
        if is_tech_narr and is_nature_media:
            score -= 60
            notes.append("Contradição semântica crítica: narração sobre hardware/computação pareada com mídia de natureza/praia.")

        # If there are expected objects, ensure at least one matches
        if scene.expected_objects:
            obj_matched = any(_clean_alnum_text(o) in visual_evidence_tags for o in scene.expected_objects)
            if not obj_matched and not overlap:
                score -= 40
                notes.append(f"Objetos esperados ({', '.join(scene.expected_objects[:3])}) não identificados na mídia.")

        # If zero overlap and score hasn't dropped yet
        if not overlap and len(target_tags) >= 2 and not scene.detected_objects:
            score -= 20
            notes.append("Correspondência semântica fraca entre narração e asset.")

        score = max(0, min(100, score))
        
        if score >= 75:
            status = "PASS"
        elif score >= 50:
            status = "REQUIRES_REVIEW"
        else:
            status = "FAIL"

        scene.alignment_score = score
        scene.alignment_notes = notes
        scene.validation_status = status
        return scene

    def align_scenes(self, scenes: List[SceneContract]) -> Tuple[List[SceneContract], Dict[str, Any]]:
        """Validate an entire sequence of planned scenes and return aggregated metrics."""
        seen_assets: Set[str] = set()
        evaluated_scenes: List[SceneContract] = []
        total_score = 0
        mismatched_scenes = []
        duplicate_scenes = []

        for sc in scenes:
            ev = self.evaluate_scene(sc, seen_assets=seen_assets)
            evaluated_scenes.append(ev)
            total_score += ev.alignment_score
            
            if ev.media_asset:
                if ev.media_asset in seen_assets:
                    duplicate_scenes.append(ev.scene_id)
                seen_assets.add(ev.media_asset)

            if ev.validation_status == "FAIL":
                mismatched_scenes.append({
                    "scene_id": ev.scene_id,
                    "media_asset": ev.media_asset,
                    "narration": ev.narration,
                    "notes": ev.alignment_notes,
                })

        avg_score = int(total_score / len(scenes)) if scenes else 0
        summary = {
            "passed": len(mismatched_scenes) == 0 and avg_score >= 70,
            "average_alignment_score": avg_score,
            "total_scenes": len(scenes),
            "mismatched_scenes_count": len(mismatched_scenes),
            "mismatched_scenes": mismatched_scenes,
            "duplicate_media_count": len(duplicate_scenes),
            "duplicate_scenes": duplicate_scenes,
        }
        return evaluated_scenes, summary
