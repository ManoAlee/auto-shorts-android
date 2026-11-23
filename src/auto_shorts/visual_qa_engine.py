"""Visual QA & Video Diagnostics Engine — Blackdetect, Freezedetect, Silencedetect & Contact Sheets.

Inspired by Netflix/vmaf and FFmpeg native diagnostic filter complexes.
Evaluates local video files before approval and generates contact sheet proof.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("autoshorts.visual_qa_engine")


class VisualQAEngine:
    """Inspeção profunda de arquivos de vídeo via filtros nativos do FFmpeg."""

    def __init__(self, out_dir: Path | str = "output") -> None:
        self.out_dir = Path(out_dir)
        self.evidence_dir = self.out_dir / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def run_deep_diagnostics(self, mp4_path: Path | str) -> Dict[str, Any]:
        """Executa varredura por frames pretos, congelamentos e silêncios."""
        path = Path(mp4_path)
        if not path.is_file():
            return {"error": f"Arquivo não encontrado: {path}", "passed": False}

        results: Dict[str, Any] = {
            "file_name": path.name,
            "size_kb": path.stat().st_size // 1024,
            "black_frames_detected": 0,
            "frozen_frames_detected": 0,
            "silence_intervals_detected": 0,
            "warnings": [],
            "passed": True,
        }

        # 1. FFprobe metadata check
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size,bit_rate:stream=width,height,codec_name",
                "-of", "json", str(path),
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10.0, check=False)
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                results["format"] = data.get("format", {})
                results["streams"] = data.get("streams", [])
        except Exception as exc:
            results["warnings"].append(f"ffprobe falhou: {exc}")

        # 2. Blackdetect & Freezedetect via FFmpeg
        try:
            vf = "blackdetect=d=0.5:pic_th=0.98,freezedetect=n=0.003:d=1.5"
            cmd = ["ffmpeg", "-i", str(path), "-vf", vf, "-af", "silencedetect=noise=-30dB:d=2.0", "-f", "null", "-"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25.0, check=False)
            stderr = proc.stderr or ""

            # Analisar outputs de filtro no stderr
            black_count = stderr.count("black_start:")
            frozen_count = stderr.count("freeze_start:")
            silence_count = stderr.count("silence_start:")

            results["black_frames_detected"] = black_count
            results["frozen_frames_detected"] = frozen_count
            results["silence_intervals_detected"] = silence_count

            if black_count > 0:
                results["warnings"].append(f"Detectados {black_count} trechos com tela preta (> 0.5s).")
            if frozen_count > 0:
                results["warnings"].append(f"Detectados {frozen_count} trechos com tela congelada (> 1.5s).")
            if silence_count > 0:
                results["warnings"].append(f"Detectados {silence_count} trechos com silêncio prolongado (> 2.0s).")

            # Falha se telas pretas excederem 2 trechos
            if black_count > 2:
                results["passed"] = False

        except Exception as exc:
            results["warnings"].append(f"Filtro FFmpeg não concluído: {exc}")

        return results

    def generate_contact_sheet(
        self,
        mp4_path: Path | str,
        grid: str = "3x3",
        thumb_width: int = 240,
    ) -> Optional[Path]:
        """Gera imagem mosaico de amostragem de frames (Contact Sheet)."""
        path = Path(mp4_path)
        if not path.is_file():
            return None

        out_img = self.evidence_dir / f"{path.stem}_contact_sheet.jpg"
        cols, rows = (int(x) for x in grid.split("x"))
        total_thumbs = cols * rows

        # select='not(mod(n\,step))',scale=240:-1,tile=3x3
        vf = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,2.0)',scale={thumb_width}:-1,tile={grid}"
        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-vf", vf,
            "-frames:v", "1",
            "-q:v", "3",
            str(out_img),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20.0, check=False)
            if res.returncode == 0 and out_img.is_file():
                return out_img
        except Exception as exc:
            logger.warning("Falha ao gerar contact sheet: %s", exc)

        return None
