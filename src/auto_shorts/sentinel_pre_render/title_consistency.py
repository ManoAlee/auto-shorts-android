"""Title-to-Content Consistency Engine.

Evaluates correspondence between the candidate title and the actual script / visual evidence.
Detects:
1. False numerical promises (e.g. title promises 5 errors, script delivers 3).
2. Topic mismatch (e.g. title claims GTA 6, script discusses digital marketing or video editing tools).
3. Clickbait exaggeration that has zero visual or spoken evidence.
4. Missing payoffs on explicit title promises.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .contracts import SceneContract, TitleConsistencyMatrix
from ..viral_titling import _clean_alnum_text, _STOPWORDS_PT
from ..viral_intelligence import AntiSlopHumanizer

logger = logging.getLogger("autoshorts.sentinel.title_consistency")


class TitleToContentConsistencyEngine:
    """Evaluates correspondence between title promises and script/visual delivery."""

    @staticmethod
    def _extract_numerical_promise(title: str) -> Optional[int]:
        """Detect if title makes an explicit list/number promise (e.g. '5 erros', '3 segredos', '4 ferramentas')."""
        norm = _clean_alnum_text(title)
        match = re.search(r"\b(\d+)\s*(?:erros?|dicas?|segredos?|ferramentas?|passos?|formas?|coisas?|motivos?|itens|fatores)\b", norm)
        if match:
            return int(match.group(1))
        
        # Word numbers in Portuguese
        words_num = {
            "um": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
            "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10
        }
        for word, val in words_num.items():
            if re.search(rf"\b{word}\s+(?:erros?|dicas?|segredos?|ferramentas?|passos?|formas?|coisas?|motivos?)\b", norm):
                return val
        return None

    @staticmethod
    def _count_delivered_items(script: str, scenes: List[SceneContract]) -> int:
        """Count how many numbered points or distinct item segments exist in the script/scenes."""
        full_text = f"{script} " + " ".join(s.narration for s in scenes)
        norm = _clean_alnum_text(full_text)

        # Look for explicit numbered patterns: '1.', 'erro 1', 'primeiro', 'segundo', etc.
        item_patterns = [
            r"\b(?:numero|item|erro|dica|segredo|passo)\s*(\d+)\b",
            r"\b(\d+)[\.\-\)]\s+[a-z]",
            r"\b(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|setim[oa]|oitav[oa]|non[oa]|decim[oa])\b",
        ]
        
        detected_indices = set()
        for pat in item_patterns:
            matches = re.findall(pat, norm)
            for m in matches:
                detected_indices.add(str(m))

        if detected_indices:
            return len(detected_indices)

        # Fallback: estimate based on scene count or distinct paragraphs
        paragraphs = [p for p in script.split("\n") if len(p.strip().split()) >= 4]
        return min(len(paragraphs), len(scenes)) if len(scenes) > 1 else len(paragraphs)

    @staticmethod
    def _extract_core_entities(text: str) -> List[str]:
        """Extract main topical entities and nouns from text."""
        clean = AntiSlopHumanizer.clean(text)
        tokens = re.findall(r"\b[\w\-áéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]+\b", clean)
        significant = []
        for t in tokens:
            t_norm = _clean_alnum_text(t)
            if t_norm not in _STOPWORDS_PT and len(t) > 2 and not t.isdigit():
                significant.append(t_norm)
        return list(dict.fromkeys(significant))

    def analyze_consistency(
        self,
        title: str,
        script_text: str = "",
        scenes: Optional[List[SceneContract]] = None,
    ) -> TitleConsistencyMatrix:
        """Analyze title against script and scene visual contracts.
        
        Builds matrix: TITLE_CLAIM -> SCRIPT_SEGMENT -> VISUAL_EVIDENCE -> TIMESTAMP
        """
        scenes = scenes or []
        combined_script = script_text or " ".join(s.narration for s in scenes)
        clean_title = AntiSlopHumanizer.clean(title).strip()
        
        norm_title = _clean_alnum_text(clean_title)
        norm_script = _clean_alnum_text(combined_script)

        explicit_promises = []
        expected_count = self._extract_numerical_promise(clean_title)
        delivered_count = 0

        if expected_count is not None:
            explicit_promises.append(f"Apresentar {expected_count} itens distintos prometidos no título.")
            delivered_count = self._count_delivered_items(combined_script, scenes)

        # Extract entities from title
        title_entities = self._extract_core_entities(clean_title)
        
        claims_matrix = []
        is_mismatched = False
        mismatch_reasons = []

        # 1. Check numerical promise match
        if expected_count is not None:
            delivered = delivered_count >= expected_count
            claims_matrix.append({
                "claim": f"{expected_count} itens prometidos",
                "script_segment": f"{delivered_count} itens identificados no roteiro",
                "visual_evidence": f"{len(scenes)} cenas planejadas",
                "timestamp": 0.0,
                "delivered": delivered,
            })
            if not delivered:
                is_mismatched = True
                mismatch_reasons.append(
                    f"Título promete {expected_count} itens, mas o roteiro entrega apenas {delivered_count}."
                )

        # 2. Check topic and entity alignment
        matched_entities = []
        missing_entities = []
        
        # Check specific known clickbait / hijacked topics
        if "gta 6" in norm_title and not any(k in norm_script for k in ("gta", "rockstar", "vice city", "leonida", "lucia", "jason")):
            is_mismatched = True
            mismatch_reasons.append("Título menciona 'GTA 6', mas o conteúdo não aborda o jogo.")

        if "ao vivo" in norm_title and any(w in norm_title for w in ("descobriu esse segredo", "perdeu o controle", "reação inacreditável")):
            if not any(k in norm_script for k in ("ao vivo", "live", "stream", "transmitido")):
                mismatch_reasons.append("Título afirma ocorrência 'ao vivo', mas o roteiro não é transmissão ao vivo.")

        for ent in title_entities:
            # Skip generic short terms like 'curiosidades', 'segredo'
            if ent in (
                "shorts", "plantao", "mundo", "hoje", "ciencia", "natureza", "veja", "sobre",
                "passos", "passo", "simples", "facil", "dicas", "dica", "erros", "erro",
                "formas", "forma", "segredos", "segredo", "coisas", "coisa", "aumentar",
                "melhorar", "evitar", "conheca", "descubra", "tudo", "como", "itens", "motivos"
            ):
                continue
            
            # Find evidence in script or scene visual contracts with root/stem flexibility
            ent_stem = ent[:5] if len(ent) >= 6 else ent
            found_in_script = ent in norm_script or (len(ent) >= 6 and ent_stem in norm_script)
            found_in_visuals = any(
                ent in _clean_alnum_text(s.visual_intent) or
                (len(ent) >= 6 and ent_stem in _clean_alnum_text(s.visual_intent)) or
                ent in _clean_alnum_text(" ".join(s.expected_objects)) or
                (len(ent) >= 6 and ent_stem in _clean_alnum_text(" ".join(s.expected_objects))) or
                ent in _clean_alnum_text(" ".join(s.detected_objects)) or
                ent in _clean_alnum_text(s.media_asset) or
                (len(ent) >= 6 and ent_stem in _clean_alnum_text(s.media_asset))
                for s in scenes
            )
            
            # Find closest timestamp
            matching_ts = 0.0
            matching_scene_id = "general"
            for s in scenes:
                if ent in _clean_alnum_text(s.narration) or ent in _clean_alnum_text(s.visual_intent):
                    matching_ts = s.timestamp_start
                    matching_scene_id = s.scene_id
                    break

            claims_matrix.append({
                "claim": ent,
                "script_segment": f"Presente no texto: {found_in_script}",
                "visual_evidence": f"Presente nos visuais: {found_in_visuals} ({matching_scene_id})",
                "timestamp": matching_ts,
                "delivered": found_in_script or found_in_visuals,
            })

            if found_in_script or found_in_visuals:
                matched_entities.append(ent)
            else:
                missing_entities.append(ent)

        # If more than 50% of significant title entities are missing from script and visuals
        significant_missing = [e for e in missing_entities if len(e) >= 4]
        if significant_missing and len(significant_missing) > len(matched_entities):
            is_mismatched = True
            mismatch_reasons.append(
                f"Principais elementos do título ausentes do conteúdo: {', '.join(significant_missing[:3])}"
            )

        # Calculate consistency score
        score = 100
        if is_mismatched:
            score -= 40
        if expected_count and delivered_count < expected_count:
            penalty = min(40, int(((expected_count - delivered_count) / expected_count) * 40))
            score -= penalty
        if missing_entities:
            score -= min(30, len(missing_entities) * 5)
        score = max(0, min(100, score))

        return TitleConsistencyMatrix(
            title=clean_title,
            explicit_promises=explicit_promises,
            expected_count=expected_count,
            delivered_count=delivered_count,
            claims=claims_matrix,
            is_mismatched=is_mismatched,
            mismatch_reason="; ".join(mismatch_reasons) if mismatch_reasons else None,
            consistency_score=score,
        )
