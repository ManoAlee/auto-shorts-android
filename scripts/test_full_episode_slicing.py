#!/usr/bin/env python3
"""Test downloading and slicing a full 20-minute anime episode with authentic Brazilian dubbing."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from auto_shorts.config import load_dotenv_file
load_dotenv_file(project_root / ".env")

from auto_shorts.pipeline import run_pipeline

def main():
    out_dir = project_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Full authentic 1080p Brazilian dubbed episode of Yu Yu Hakusho Ep 1 (A Morte)
    episode_url = "https://archive.org/download/yu-yu-hakusho-ep-1-dublado-hd-1080p/Yu%20Yu%20Hakusho%20EP%201%20Dublado%20HD%201080p.mp4"

    print(">>> [TESTE] Iniciando download e fatiamento do Episódio Completo:", episode_url, flush=True)
    res = run_pipeline(
        source=episode_url,
        out_dir=out_dir,
        platform="youtube_shorts",
        niche="entretenimento_animes",
        num_clips=3,
        layout="blur_bg",
        quality="mobile",
        use_llm=True,
        auto_layout=True,
        playlist_name="Animes Clássicos Dublados - Shorts",
        auto_publish=False, # Dry run before auto-publishing
    )

    clips = res.get("clips") or []
    print(f"\n=======================================================", flush=True)
    print(f"SUCESSO! Episódio fatiado em {len(clips)} cortes épicos!", flush=True)
    for idx, c in enumerate(clips, 1):
        mp4_file = c.get("output") or c.get("mp4")
        hook = c.get("hook_title") or c.get("title")
        print(f"Corte #{idx}: {hook} -> {mp4_file}", flush=True)
    print(f"=======================================================\n", flush=True)

if __name__ == "__main__":
    main()
