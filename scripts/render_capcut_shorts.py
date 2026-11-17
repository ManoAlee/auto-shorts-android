#!/usr/bin/env python3
"""Generate multi-niche Shorts demonstrating CapCut voice styles, SAMI audio mastering, and Albert Sans typography."""

import os
import sys
from pathlib import Path

# Setup paths
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from auto_shorts.config import load_dotenv_file
load_dotenv_file(repo_root / ".env")

from auto_shorts.narrator import build_narrated_short, VOICE_STYLES
from auto_shorts.validator import validate_generated_short

VIDEOS = [
    {
        "stem": "short_games_red_dead_mistério",
        "title": "O Mistério Mais Bizarro de Red Dead 2",
        "hook": "O Segredo Oculto no Pântano",
        "style": "capcut_cleyton",
        "niche": "games",
        "bg": "gp_drone_cinema_DesiBXmyCBQ.mp4",
        "script": (
            "Você sabia que a Rockstar escondeu um dos mistérios mais perturbadores em Red Dead Redemption 2? "
            "Se você cavalgar até o pântano de Bluewater Marsh exatamente às duas da manhã com neblina, você escuta o choro de uma mulher. "
            "Ao se aproximar, você encontra o fantasma de Agnes Dowd vagando entre as árvores, repetindo as últimas palavras antes da sua tragédia. "
            "O mais bizarro é que existem dezesseis aparições diferentes, e cada vez ela revela uma parte sombria da sua história. "
            "A Rockstar levou o nível de realismo a um patamar que nenhum outro estúdio conseguiu alcançar. "
            "Qual mistério dos games mais te deu arrepios? Comenta aí e segue a AleplayTV!"
        ),
    },
    {
        "stem": "short_anime_teoria_saiyajin",
        "title": "A Teoria Mais Insana de Dragon Ball",
        "hook": "O Segredo do Trunks do Futuro",
        "style": "capcut_julia",
        "niche": "entretenimento_animes",
        "bg": "gp_space_cosmos_0i9wZ-xDC04.mp4",
        "script": (
            "Presta atenção nessa teoria que vai explodir a sua cabeça sobre Dragon Ball! "
            "Você já parou para pensar por que o Trunks do futuro tinha uma força tão absurda mesmo sem treinar na Sala do Tempo? "
            "Segundo Akira Toriyama, os Saiyajins híbridos nascem sem cauda quando herdam um potencial genético muito superior. "
            "Mas o detalhe que quase ninguém percebeu é que o Trunks cresceu em um mundo devastado pela perda e pelo trauma. "
            "A dor desbloqueou o poder oculto dele muito antes do Gohan. "
            "Ele não lutava para superar limites, ele lutava pela sobrevivência da humanidade. "
            "Qual seu guerreiro favorito de anime? Deixa nos comentários e segue a AleplayTV!"
        ),
    },
]

def main():
    out_dir = repo_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_gp = repo_root / "assets" / "gameplay"

    print("=== INICIANDO GERAÇÃO DE SHORTS COM VOZES CAPCUT ===")
    for item in VIDEOS:
        stem = item["stem"]
        out_mp4 = out_dir / f"{stem}.mp4"
        bg_file = assets_gp / item["bg"]
        if not bg_file.is_file():
            # Fallback to any mp4 in assets
            any_bg = list(assets_gp.glob("*.mp4"))
            bg_file = any_bg[0] if any_bg else assets_gp / "gp_minecraft_7yl7Wc1dtWc.mp4"

        print(f"\n[+] Produzindo: {item['title']}")
        print(f"    Voz: {item['style']} ({VOICE_STYLES[item['style']].label})")
        print(f"    Nicho: {item['niche']}")
        print(f"    Fundo: {bg_file.name}")

        res = build_narrated_short(
            bg_video=bg_file,
            script_text=item["script"],
            out_mp4=out_mp4,
            hook_title=item["hook"],
            style_key=item["style"],
            quality="mobile",
            bg_volume=0.06,
            niche=item["niche"],
            burn_hook=True,
            custom_title=item["title"],
        )

        print(f"    Renderizado: {out_mp4.name} ({out_mp4.stat().st_size / (1024*1024):.2f} MB)")
        print(f"    Duração: {res.get('duration')}s")

        # Validate with video validator
        val = validate_generated_short(out_mp4, min_duration=10.0, max_duration=65.0)
        print(f"    Validação: Valid={val.get('valid')} Errors={val.get('errors')}")

    print("\n=== TODOS OS SHORTS FORAM GERADOS COM SUCESSO! ===")

if __name__ == "__main__":
    main()
