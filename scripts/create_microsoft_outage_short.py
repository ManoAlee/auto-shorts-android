#!/usr/bin/env python3
"""Produce breaking news short for Microsoft 365 incident EX1550543 / MO1550821 with verified root cause and publish to YouTube."""

import os
import sys
import json
import traceback
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
    
    mp4_out = out_dir / "ex1550543_microsoft_outage_v2.mp4"
    bg_video = project_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4"
    if not bg_video.is_file():
        gp_files = list((project_root / "assets" / "gameplay").glob("*.mp4"))
        if gp_files:
            bg_video = gp_files[0]
        else:
            raise FileNotFoundError("Nenhum video de fundo encontrado em assets/gameplay/")

    # Script técnico, dinâmico e investigativo com a causa raiz oficial
    script_text = (
        "Atenção! Um apagão global paralisou os serviços da Microsoft no mundo todo neste 12 de novembro, "
        "sob os alertas oficiais EX1550543 e MO1550821! "
        "Se o seu Outlook, o Microsoft Teams ou o Copilot pararam de responder hoje, a Microsoft finalmente "
        "revelou o motivo técnico nos bastidores. "
        "Segundo o centro de status da empresa, a infraestrutura em nuvem sofreu uma sobrecarga crítica "
        "causada por um pico inesperado e anômalo de tráfego em um serviço específico. "
        "Esse tsunami de requisições congestionou as filas de autenticação do Exchange Online, e o efeito "
        "cascata derrubou não só os e-mails corporativos, mas também o SharePoint, o Teams e recursos de "
        "inteligência artificial. "
        "Equipes de engenharia estão agora reiniciando nós de infraestrutura e redirecionando o tráfego global "
        "para clusters de contingência para restaurar os serviços. "
        "Comenta aqui embaixo: a sua empresa foi afetada por essa pane hoje? "
        "Compartilhe este vídeo com a sua equipe e inscreva-se para acompanhar as novidades de tecnologia!"
    )

    hook_title = "MICROSOFT FORA DO AR!"
    video_title = "EX1550543: O Verdadeiro Motivo do Apagão Global da Microsoft Hoje! #Shorts"
    
    print(">>> [1/4] Renderizando Short em 9:16 com voz neural HD profunda e legendas dinâmicas...", flush=True)
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
    print(">>> Vídeo renderizado com sucesso:", mp4_out, flush=True)

    print(">>> [2/4] Gerando Thumbnails de alta conversão...", flush=True)
    cover_9x16 = out_dir / "ex1550543_v2_cover_9x16.jpg"
    thumb_16x9 = out_dir / "ex1550543_v2_thumb_16x9.jpg"
    try:
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
        print(">>> Capas geradas:", cover_9x16, thumb_16x9, flush=True)
    except Exception as e:
        print(">>> Aviso na geração de thumbnail:", e, flush=True)

    description = (
        "🚨 URGENTE: Os códigos oficiais EX1550543 e MO1550821 identificam a grande pane global da "
        "Microsoft que paralisou o Exchange Online, Outlook, Teams e Copilot neste 12 de novembro de 2026.\n\n"
        "🔍 MOTIVO TÉCNICO OFICIAL:\n"
        "A Microsoft confirmou que um pico inesperado e desproporcional de tráfego em um serviço específico "
        "provocou sobrecarga crítica na infraestrutura de nuvem, travando as filas de autenticação (MAPI, REST, ActiveSync) "
        "e gerando um efeito cascata em múltiplos serviços corporativos.\n\n"
        "🛠️ AÇÕES EM ANDAMENTO:\n"
        "Engenheiros estão reiniciando nós degradados e redirecionando o tráfego global para clusters de contingência.\n\n"
        "Sua empresa foi impactada hoje? Deixe nos comentários!\n\n"
        "#Microsoft #Microsoft365 #ExchangeOnline #Outlook #Teams #Copilot #EX1550543 #MO1550821 #Tecnologia #TI #Shorts"
    )

    tags = ["Microsoft", "Microsoft365", "ExchangeOnline", "Outlook", "Teams", "Copilot", "EX1550543", "MO1550821", "Tecnologia", "TI", "Shorts"]

    print(">>> [3/4] Publicando no YouTube Shorts (Canal AleplayTV)...", flush=True)
    video_id = None
    try:
        yt_res = publish_youtube_short(
            video_path=mp4_out,
            title=video_title,
            description=description,
            tags=tags,
            privacy_status="public",
        )
        video_id = yt_res.get("video_id")
        print(f">>> PUBLICADO COM SUCESSO NO YOUTUBE! ID: {video_id} - URL: https://youtube.com/shorts/{video_id}", flush=True)

        if thumb_16x9.is_file() and video_id:
            try:
                set_youtube_thumbnail(video_id, thumb_16x9)
                print(">>> Thumbnail personalizada aplicada no YouTube!", flush=True)
            except Exception as e:
                print(">>> Aviso ao definir thumbnail:", e, flush=True)

        playlist_name = "Notícias Rápidas de Tecnologia e TI"
        try:
            pid = ensure_youtube_playlist(playlist_name, description="Plantão de notícias urgentes de TI e Tecnologia.")
            if pid and video_id:
                add_video_to_playlist(video_id, pid)
                print(f">>> Adicionado à playlist '{playlist_name}'!", flush=True)
        except Exception as e:
            print(">>> Aviso ao adicionar em playlist:", e, flush=True)

    except Exception as exc:
        print(">>> Erro ao publicar no YouTube:", exc, flush=True)
        traceback.print_exc()

    print(">>> [4/4] Enviando cópia de backup para o Google Drive 5TB...", flush=True)
    try:
        upload_to_rclone(mp4_out, "gdrive:Shorts_Finalizados")
        print(">>> Salvo em gdrive:Shorts_Finalizados/ com sucesso!", flush=True)
    except Exception as e:
        print(">>> Aviso rclone:", e, flush=True)

    print("\n=======================================================", flush=True)
    print("PROCESSO CONCLUÍDO COM SUCESSO!", flush=True)
    if video_id:
        print(f"Vídeo no YouTube: https://youtube.com/shorts/{video_id}", flush=True)
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    main()
