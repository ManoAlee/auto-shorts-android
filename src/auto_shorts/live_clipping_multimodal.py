"""Multimodal Live Clipping Engine — Audio, Visual, Speech & Context Boundary Snapping.

Inspired by algorithms from:
- sidgaikwad/stream-clipper (rolling buffer & temporal windows)
- Cbhhhh211/livestream-highlight-clipper (reaction & chat density scoring)
- Breakthrough/PySceneDetect (scene change boundaries)
- WyattBlue/auto-editor (silence boundary snapping)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("autoshorts.live_clipping_multimodal")


@dataclass
class HighlightCandidate:
    start_sec: float
    end_sec: float
    duration_sec: float
    overall_score: float             # 0.0 a 100.0
    audio_energy_score: float        # 0.0 a 100.0
    visual_pace_score: float         # 0.0 a 100.0
    speech_density_score: float      # 0.0 a 100.0
    trigger_type: str                # "SCREAM_REACTION", "FAST_ACTION", "VIRAL_SPEECH", "MULTIMODAL_SPIKE"
    snapped_to_sentence: bool
    context_preserved: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultimodalHighlightScorer:
    """Combina múltiplos sinais (áudio, visual, fala) para isolar momentos virais de lives."""

    def __init__(
        self,
        min_clip_sec: float = 20.0,
        max_clip_sec: float = 58.0,
        cooldown_sec: float = 40.0,
    ) -> None:
        self.min_clip_sec = min_clip_sec
        self.max_clip_sec = max_clip_sec
        self.cooldown_sec = cooldown_sec

    def evaluate_live_window(
        self,
        audio_rms_samples: List[float],
        scene_changes: List[float],
        speech_intervals: List[Tuple[float, float]],
        sample_rate_hz: float = 10.0,  # 10 samples de áudio por segundo
        window_duration_sec: float = 120.0,
    ) -> List[HighlightCandidate]:
        """Varre a janela da live e isola os melhores candidatos a corte 9:16."""
        if not audio_rms_samples:
            return []

        avg_rms = sum(audio_rms_samples) / max(1, len(audio_rms_samples))
        candidates: List[HighlightCandidate] = []
        last_highlight_end = -self.cooldown_sec

        # Passo de 2 segundos para busca de picos
        step_samples = int(sample_rate_hz * 2.0)
        total_samples = len(audio_rms_samples)

        for i in range(0, total_samples - int(self.min_clip_sec * sample_rate_hz), step_samples):
            curr_sec = i / sample_rate_hz
            if curr_sec < (last_highlight_end + self.cooldown_sec):
                continue

            # Avaliar janela de 30s a partir deste ponto
            sub_len = min(int(self.min_clip_sec * sample_rate_hz), total_samples - i)
            sub_window = audio_rms_samples[i : i + sub_len]
            if not sub_window:
                continue

            max_sub_rms = max(sub_window)
            spike_ratio = max_sub_rms / max(0.0001, avg_rms)

            # S1: Audio Energy Score (0 a 100)
            audio_score = min(100.0, max(0.0, (spike_ratio - 1.2) * 35.0))

            # S2: Visual Scene Score (número de trocas de cena na janela)
            win_end_sec = curr_sec + self.min_clip_sec
            scenes_in_win = sum(1 for s in scene_changes if curr_sec <= s <= win_end_sec)
            visual_score = min(100.0, scenes_in_win * 25.0)

            # S3: Speech Density Score (tempo com fala ativa)
            speech_overlap = 0.0
            for sp_start, sp_end in speech_intervals:
                overlap_start = max(curr_sec, sp_start)
                overlap_end = min(win_end_sec, sp_end)
                if overlap_end > overlap_start:
                    speech_overlap += (overlap_end - overlap_start)
            speech_score = min(100.0, (speech_overlap / max(1.0, self.min_clip_sec)) * 100.0)

            # Pontuação Ponderada Multimodal
            # Audio 45%, Fala 35%, Visual 20%
            weighted_score = (audio_score * 0.45) + (speech_score * 0.35) + (visual_score * 0.20)

            if weighted_score >= 45.0:
                # Ajustar bordas para limites de fala (sentence boundary snapping)
                snapped_start = curr_sec
                snapped_end = win_end_sec
                snapped = False

                for sp_start, sp_end in speech_intervals:
                    # Se início cai dentro de uma frase, recuar para o começo da frase
                    if sp_start <= curr_sec <= sp_end:
                        snapped_start = max(0.0, sp_start - 0.5)
                        snapped = True
                    # Se término corta frase, estender até o final da frase
                    if sp_start <= win_end_sec <= sp_end:
                        snapped_end = min(window_duration_sec, sp_end + 0.5)
                        snapped = True

                clip_dur = snapped_end - snapped_start
                if clip_dur > self.max_clip_sec:
                    snapped_end = snapped_start + self.max_clip_sec

                trigger = "MULTIMODAL_SPIKE"
                if audio_score >= 80.0:
                    trigger = "SCREAM_REACTION"
                elif speech_score >= 80.0:
                    trigger = "VIRAL_SPEECH"
                elif visual_score >= 70.0:
                    trigger = "FAST_ACTION"

                candidate = HighlightCandidate(
                    start_sec=round(snapped_start, 2),
                    end_sec=round(snapped_end, 2),
                    duration_sec=round(snapped_end - snapped_start, 2),
                    overall_score=round(weighted_score, 1),
                    audio_energy_score=round(audio_score, 1),
                    visual_pace_score=round(visual_score, 1),
                    speech_density_score=round(speech_score, 1),
                    trigger_type=trigger,
                    snapped_to_sentence=snapped,
                    context_preserved=True,
                )
                candidates.append(candidate)
                last_highlight_end = candidate.end_sec

        # Ordenar por pontuação decrescente
        candidates.sort(key=lambda c: c.overall_score, reverse=True)
        return candidates
