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
        "bg": "gp_rdr2_agnes_dowd.mp4",
        "script": (
            "Mano, olha o detalhe bizarro que a Rockstar escondeu em Red Dead 2. "
            "Se você cavalgar no pântano de Bluewater Marsh de madrugada com neblina, começa a ouvir o choro de uma mulher. "
            "Quando você chega perto, dá de cara com o fantasma da Agnes Dowd vagando entre as árvores. "
            "E o mais doido: são dezesseis aparições diferentes, e cada vez ela conta um pedaço da tragédia dela. "
            "O nível de loucura que a Rockstar colocou nesse jogo não existe em nenhum outro lugar. "
            "Já trombou com ela no jogo? Comenta aí e segue a AleplayTV!"
        ),
    },
    {
        "stem": "short_anime_teoria_saiyajin",
        "title": "A Teoria Mais Insana de Dragon Ball",
        "hook": "O Segredo do Trunks do Futuro",
        "style": "capcut_julia",
        "niche": "entretenimento_animes",
        "bg": "gp_dbz_trunks_real.mp4",
        "script": (
            "Cara, repara nessa loucura sobre o Trunks do futuro em Dragon Ball. "
            "Muita gente não entende como ele ficou tão forte sem nem pisar na Sala do Tempo. "
            "O Toriyama explicou que Saiyajin híbrido que nasce sem cauda já herda um potencial genético absurdo. "
            "Só que o Trunks cresceu vendo todo mundo que ele amava morrer. "
            "A dor da perda destravou o poder oculto dele muito antes do Gohan. "
            "Ele não tava treinando pra ficar forte, tava lutando pra não ser extinto. "
            "Quem é o guerreiro mais brabo de anime pra você? Deixa aí nos comentários e segue a AleplayTV!"
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
        val = validate_generated_short(out_mp4, max_duration=65.0)
        print(f"    Validação: Valid={val.get('valid')} Errors={val.get('errors')}")

    print("\n=== TODOS OS SHORTS FORAM GERADOS COM SUCESSO! ===")

if __name__ == "__main__":
    main()
