"""Generate viral shorts batch using ffmpeg-skill smart media engine and natural PT-BR narration."""

import os
import sys
import time
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_shorts.config import load_dotenv_file
from auto_shorts.narrator import build_narrated_short
from auto_shorts.validator import audit_short_end_to_end


def main():
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv_file(repo_root / ".env")
    out_dir = repo_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    videos_to_generate = [
        {
            "name": "short_gta6_30fps_segredo_leonida.mp4",
            "hook_title": "GTA 6 A 30 FPS NOS CONSOLES?",
            "custom_title": "Por que GTA 6 vai rodar a 30 FPS no PS5 e Xbox? O Segredo Técnico de Leonida",
            "style_key": "narrador_pro",
            "niche": "games_esports",
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_gta_ramp_a_QRwCGtf_Q.mp4",
                repo_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4",
                repo_root / "assets" / "gameplay" / "gp_minecraft_7yl7Wc1dtWc.mp4",
            ],
            "script": (
                "Você ainda acredita que o GTA 6 vai rodar a 60 quadros por segundo no seu PlayStation 5 "
                "ou Xbox Series X? A verdade técnica vai te surpreender. "
                "A Rockstar Games não está apenas criando um jogo bonito. Ela construiu uma simulação física "
                "completa para o estado de Leonida. Cada gota d'água no oceano de Vice City possui física de maré "
                "volumétrica em tempo real. Mais de setenta por cento dos prédios têm interiores modelados e acessíveis. "
                "E a inteligência artificial dos pedestres agora é neural, onde cada cidadão toma decisões individuais "
                "sobre clima, trânsito e crimes ao redor. O gargalo não é a placa de vídeo, é o processador dos consoles, "
                "que não aguenta calcular tantas rotinas de simulação e iluminação global a 60 FPS sem comprometer a estabilidade. "
                "Por isso, até mesmo no PS5 Pro, os trinta quadros cravados serão o padrão da Rockstar. "
                "Qual a sua opinião sobre isso? Deixa nos comentários e me segue para mais segredos do mundo gamer."
            ),
        },
        {
            "name": "short_rdr2_fantasma_agnes_dowd.mp4",
            "hook_title": "O FANTASMA DO RED DEAD 2",
            "custom_title": "O Segredo Macabro de Agnes Dowd nos Pântanos de Red Dead Redemption 2",
            "style_key": "thalita_hd",
            "niche": "podcast",
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_rdr2_agnes_dowd.mp4",
                repo_root / "assets" / "gameplay" / "gp_dbz_trunks_real.mp4",
                repo_root / "assets" / "gameplay" / "gp_subway_QPW3XwBoQlw.mp4",
            ],
            "script": (
                "Você sabia que a Rockstar escondeu uma das histórias mais assustadoras dos games nos pântanos de Lemoyne? "
                "Se você cavalgar por Bluewater Marsh entre duas e três da manhã com neblina alta, vai ouvir uma mulher "
                "chorando no meio das árvores. É o espírito de Agnes Dowd. Existem dezesseis encontros diferentes com ela. "
                "Em cada um, ela revela uma parte do seu passado trágico: um amor proibido, a desaprovação de sua família rigorosa "
                "e a traição que a levou a tirar a própria vida na forca. No último encontro, você encontra a árvore exata "
                "da corda, e se apontar a arma ou se aproximar demais, ela solta um grito aterrorizante e desaparece no ar, "
                "deixando apenas flores raras no local. Esse nível de detalhe vivo é o que faz a Rockstar ser incomparável. "
                "Você já encontrou a Agnes? Me conta nos comentários e segue o canal para não perder o próximo mistério."
            ),
        },
    ]

    results = []
    for item in videos_to_generate:
        out_mp4 = out_dir / item["name"]
        print(f"\n=======================================================")
        print(f"[PRODUCING] {item['hook_title']}")
        print(f"[DESTINATION] {out_mp4.name}")

        bg_path = None
        for cand in item["bg_candidates"]:
            if cand.is_file() and cand.stat().st_size > 100_000:
                bg_path = cand
                break
        if bg_path is None:
            bg_path = "gameplay"

        print(f"[BACKGROUND] {bg_path}")
        start_t = time.time()
        res = build_narrated_short(
            bg_video=bg_path,
            script_text=item["script"],
            out_mp4=out_mp4,
            hook_title=item["hook_title"],
            style_key=item["style_key"],
            quality="mobile",
            layout="center_crop",
            humanize=True,
            niche=item["niche"],
            burn_hook=True,
            custom_title=item["custom_title"],
        )
        elapsed = time.time() - start_t
        print(f"[RENDERED in {elapsed:.1f}s] Video: {out_mp4} ({out_mp4.stat().st_size / (1024*1024):.2f} MB)")

        # Validate with smart media engine audit
        audit = audit_short_end_to_end(out_mp4, min_duration=45.0, max_duration=90.0)
        print(f"[AUDIT] Passed: {audit['passed']} | Quality Score: {audit.get('quality_score')} | EBU R128: {audit.get('loudnorm_compliant')}")
        results.append({"video": str(out_mp4), "audit": audit, "elapsed_sec": round(elapsed, 1)})

    print("\n=======================================================")
    print(f"BATCH FINISHED! Total generated: {len(results)}")
    for r in results:
        print(f" - {Path(r['video']).name}: passed={r['audit']['passed']} in {r['elapsed_sec']}s")


if __name__ == "__main__":
    main()
