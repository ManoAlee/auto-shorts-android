"""Script Intelligence Engine.

Evaluates narrative coherence, clarity, hook power, pacing, anti-slop, and factual structure.
Ensures:
1. Clear Beginning (Hook), Middle (Development), and End (Payoff / CTA).
2. No abrupt in media res starts missing essential background context.
3. Audio duration matches platform limits (e.g. <= 60s for YouTube Shorts).
4. Elimination of filler cliches and AI slop.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..viral_intelligence import AntiSlopHumanizer
from ..viral_titling import _clean_alnum_text

logger = logging.getLogger("autoshorts.sentinel.script_intelligence")

_BORING_HOOK_STARTERS = [
    "ola pessoal", "olá pessoal", "fala galera", "sejam bem vindos", "no video de hoje",
    "hoje eu vou te mostrar", "voce sabia que hoje", "sem mais delongas", "vamos comecar"
]

_ABRUPT_STARTERS = [
    "alem disso", "além disso", "entao ele disse", "então ele disse", "por isso que",
    "mas depois disso", "e como eu estava dizendo", "segundo a mesma fonte"
]


class ScriptIntelligenceEngine:
    """Evaluates script quality, narrative structure, pacing, and factual integrity."""

    def __init__(self, target_wpm: float = 150.0) -> None:
        self.target_wpm = target_wpm  # ~2.5 words per second

    def estimate_duration_sec(self, text: str) -> float:
        """Estimate spoken audio duration based on word count."""
        words = [w for w in text.split() if w.strip()]
        if not words:
            return 0.0
        # Average reading pace: 2.5 words/sec (150 WPM)
        return len(words) / (self.target_wpm / 60.0)

    def evaluate_script(
        self,
        script_text: str,
        target_duration: float = 60.0,
        platform: str = "youtube_shorts",
    ) -> Dict[str, Any]:
        """Comprehensive pre-render script evaluation."""
        clean_text = AntiSlopHumanizer.clean(script_text).strip()
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", clean_text) if len(s.strip().split()) >= 2]
        words = [w for w in clean_text.split() if w.strip()]
        total_words = len(words)
        
        estimated_duration = self.estimate_duration_sec(clean_text)

        issues: List[Dict[str, Any]] = []
        warnings: List[str] = []
        errors: List[str] = []

        # 1. Beginning / Hook Evaluation
        hook_score = 80
        first_sentence = sentences[0] if sentences else ""
        norm_first = _clean_alnum_text(first_sentence)

        # Check boring starter
        if any(norm_first.startswith(starter) for starter in _BORING_HOOK_STARTERS):
            hook_score -= 35
            warnings.append("Início fraco ou clichê ('Olá pessoal', 'No vídeo de hoje').")
            issues.append({
                "type": "WEAK_HOOK",
                "severity": "WARNING",
                "message": "O gancho inicial contém saudações vazias que derrubam a retenção nos primeiros 3 segundos.",
            })

        # Check abrupt starter missing context
        if any(norm_first.startswith(starter) for starter in _ABRUPT_STARTERS):
            hook_score -= 40
            warnings.append("Vídeo inicia no meio de um raciocínio sem contexto prévio.")
            issues.append({
                "type": "ABRUPT_START_MISSING_CONTEXT",
                "severity": "WARNING",
                "message": "O vídeo começa de forma abrupta ('Além disso...', 'Então ele disse...'), faltando introdução.",
            })

        # High curiosity hook bonus
        if any(k in norm_first for k in ("por que", "como", "o segredo", "o erro", "o momento", "nunca", "descobriu", "o que acontece")):
            hook_score = min(100, hook_score + 15)

        # 2. Narrative Structure (Beginning, Middle, End)
        structure_score = 90
        if len(sentences) < 3:
            structure_score = 40
            errors.append("Roteiro curto demais (menos de 3 frases completas).")
            issues.append({
                "type": "INSUFFICIENT_NARRATIVE",
                "severity": "ERROR",
                "message": "O roteiro não possui desenvolvimento narrativo suficiente.",
            })

        # Check for Ending / Payoff / CTA
        last_sentence = sentences[-1] if sentences else ""
        norm_last = _clean_alnum_text(last_sentence)
        has_payoff = any(k in norm_last for k in ("comenta", "inscreva", "curta", "deixe", "compartilhe", "e voce", "e você", "afinal", "conclusao", "resultado", "final"))
        if not has_payoff:
            structure_score -= 15
            warnings.append("Roteiro termina sem encerramento claro, call-to-action ou desfecho.")

        # 3. Duration & Pacing
        max_duration = 60.0 if platform == "youtube_shorts" else 90.0
        pacing_score = 95
        if estimated_duration > max_duration:
            pacing_score -= 40
            errors.append(f"Duração estimada ({estimated_duration:.1f}s) excede o limite máximo ({max_duration:.1f}s).")
            issues.append({
                "type": "OVERLONG_NARRATION",
                "severity": "ERROR",
                "message": f"O áudio previsto ({estimated_duration:.1f}s) ultrapassa {max_duration:.1f}s da plataforma.",
            })
        elif estimated_duration < 15.0:
            pacing_score -= 25
            warnings.append(f"Roteiro muito curto ({estimated_duration:.1f}s).")

        # 4. Anti-Slop & Repetition
        slop_score = 95
        slop_words = ["realmente", "literalmente", "basicamente", "incrivelmente", "absurdamente"]
        slop_count = sum(norm_first.count(sw) for sw in slop_words)
        if slop_count > 3:
            slop_score -= 20
            warnings.append("Uso excessivo de advérbios de preenchimento (slop).")

        # Check for repetitive identical phrases
        words_norm = [_clean_alnum_text(w) for w in words if len(w) > 3]
        if len(words_norm) >= 12:
            trigrams = [" ".join(words_norm[i:i+3]) for i in range(len(words_norm) - 2)]
            for tri in trigrams:
                if trigrams.count(tri) >= 3:
                    warnings.append(f"Frase ou expressão repetida 3+ vezes: '{tri}'.")
                    issues.append({
                        "type": "REPETITIVE_SCRIPT_SEGMENT",
                        "severity": "WARNING",
                        "message": f"Expressão repetida desnecessariamente: '{tri}'",
                    })
                    break

        overall_script_score = int((hook_score * 0.35) + (structure_score * 0.35) + (pacing_score * 0.20) + (slop_score * 0.10))

        return {
            "passed": len(errors) == 0,
            "overall_score": max(0, min(100, overall_script_score)),
            "hook_score": hook_score,
            "structure_score": structure_score,
            "pacing_score": pacing_score,
            "estimated_duration_sec": round(estimated_duration, 1),
            "total_words": total_words,
            "sentences_count": len(sentences),
            "errors": errors,
            "warnings": warnings,
            "issues": issues,
        }
