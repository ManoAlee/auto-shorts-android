#!/usr/bin/env python3
"""Produce breaking news short for Microsoft 365 incident EX1550543 and publish to YouTube."""

import os
import sys
from pathlib import Path

# Add src to python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from auto_shorts.config import load_dotenv_file
load_dotenv_file(project_root / ".env")

from auto_shorts.narrator import build_narrated_short
from auto_shorts.thumbnail import generate_advanced_thumbnail
from auto_shorts.publisher import publish_youtube_short, ensure_youtube_playlist, add_video_to_playlist, set_youtube_thumbnail
from auto_shorts.downloader import upload_to_rclone

def main():
    out_dir = project_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    mp4_out = out_dir / "ex1550543_microsoft_outage.mp4"
    bg_video = project_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4"
    if not bg_video.is_file():
        # Fallback to any available gameplay video
        gp_files = list((project_root / "assets" / "gameplay").glob("*.mp4"))
        if gp_files:
            bg_video = gp_files[0]
        else:
            raise FileNotFoundError("Nenhum video de fundo encontrado em assets/gameplay/")

    script_text = (
        "Atenção! Um apagão global paralisou os serviços da Microsoft no mundo todo neste dia 12 de novembro! "
        "O código de emergência é EX1550543. Se você tentou abrir seu e-mail corporativo no Outlook, enviar mensagens "
        "no Microsoft Teams ou usar o Copilot hoje e enfrentou erros graves, saiba que você não está sozinho. "
        "Milhares de empresas e milhões de usuários em diversos países relataram que o Exchange Online parou de responder, "
        "bloqueando totalmente o acesso às caixas de correio e ferramentas de trabalho. "
        "A própria conta oficial da Microsoft confirmou o incidente crítico e mobilizou equipes de engenharia em regime "
        "de urgência máxima para restaurar a conectividade. "
        "Comenta aqui embaixo: o sistema caiu na sua empresa hoje? "
        "Compartilhe este alerta com quem precisa saber e inscreva-se para acompanhar os próximos desdobramentos!"
    )

    hook_title = "APAGÃO NA MICROSOFT!"
    video_title = "EX1550543: Apagão Global da Microsoft Derruba Outlook e Copilot! #Shorts"
    
    print(">>> [1/4] Renderizando Short em 9:16 com voz neural HD e legendas dinâmicas...")
    res = build_narrated_short(
        bg_video=str(bg_video),
        script_text=script_text,
        out_mp4=mp4_out,
        hook_title=hook_title,
        style_key="doc_deep",
        layout="blur_bg",
        quality="mobile",
        humanize=True,
        niche="noticias_mundiais",
        burn_hook=True,
    )
    print(">>> Video renderizado com sucesso:", mp4_out)

    print(">>> [2/4] Gerando Thumbnails de alta conversão...")
    cover_9x16 = out_dir / "ex1550543_cover_9x16.jpg"
    thumb_16x9 = out_dir / "ex1550543_thumb_16x9.jpg"
    generate_advanced_thumbnail(
        mp4_out,
        cover_9x16,
        hook_title=hook_title,
        badge="ALERTA URGENTE",
        timestamp_sec=2.5,
        vertical_cover=True,
    )
    generate_advanced_thumbnail(
        mp4_out,
        thumb_16x9,
        hook_title=hook_title,
        badge="EX1550543 PANE",
        timestamp_sec=2.5,
        vertical_cover=False,
    )
    print(">>> Capas geradas:", cover_9x16, thumb_16x9)

    description = (
        "🚨 URGENTE: O código EX1550543 confirmou uma das maiores interrupções globais da história "
        "recente dos serviços da Microsoft neste 12 de novembro de 2026.\n\n"
        "Milhares de empresas e usuários no mundo todo relataram perda de acesso ao Outlook, Exchange Online, "
        "Microsoft Teams e Copilot.\n\n"
        "A conta oficial @MSFT365Status confirmou o incidente de alta prioridade e equipes estão atuando "
        "para reverter a pane no roteamento de infraestrutura.\n\n"
        "Seu e-mail ou Teams parou de funcionar hoje? Comente aqui embaixo!\n\n"
        "#Microsoft #Microsoft365 #ExchangeOnline #Outlook #EX1550543 #Tecnologia #Noticias #SegurancaDaInformacao #TI #Shorts"
    )

    tags = ["Microsoft", "Microsoft365", "ExchangeOnline", "Outlook", "EX1550543", "Tecnologia", "TI", "Shorts", "Noticias"]

    print(">>> [3/4] Publicando no YouTube Shorts (Canal AleplayTV)...")
    yt_res = publish_youtube_short(
        video_path=mp4_out,
        title=video_title,
        description=description,
        tags=tags,
        privacy_status="public",
    )
    video_id = yt_res.get("video_id")
    print(f">>> PUBLICADO COM SUCESSO NO YOUTUBE! ID: {video_id} - URL: https://youtube.com/shorts/{video_id}")

    try:
        if thumb_16x9.is_file() and video_id:
            set_youtube_thumbnail(video_id, thumb_16x9)
            print(">>> Thumbnail personalizada aplicada no YouTube!")
    except Exception as e:
        print(">>> Aviso ao definir thumbnail:", e)

    try:
        playlist_name = "Notícias Rápidas de Tecnologia e TI"
        pid = ensure_youtube_playlist(playlist_name, description="Plantão de notícias urgentes de TI e Tecnologia.")
        if pid and video_id:
            add_video_to_playlist(video_id, pid)
            print(f">>> Adicionado à playlist '{playlist_name}'!")
    except Exception as e:
        print(">>> Aviso ao adicionar em playlist:", e)

    print(">>> [4/4] Enviando cópia de backup para o Google Drive 5TB...")
    try:
        upload_to_rclone(mp4_out, "gdrive:Shorts_Finalizados")
        print(">>> Salvo em gdrive:Shorts_Finalizados/ com sucesso!")
    except Exception as e:
        print(">>> Aviso rclone:", e)

    print("\n=======================================================")
    print("PROCESSO CONCLUÍDO COM SUCESSO ABSOLUTO!")
    print(f"Vídeo no YouTube: https://youtube.com/shorts/{video_id}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
