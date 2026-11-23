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
            "force_rerender": True,
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_gta6_trailer_official.mp4",
                repo_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4",
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
        {
            "name": "short_samsung_app_lock_biometria.mp4",
            "hook_title": "SAMSUNG BLOQUEIA APPS COM DIGITAL",
            "custom_title": "Samsung Libera Bloqueio Individual de Apps com Biometria na One UI | Plantão Tech",
            "style_key": "narrador_pro",
            "niche": "ia_tech",
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4",
                repo_root / "assets" / "gameplay" / "gp_gta_ramp_a_QRwCGtf_Q.mp4",
                repo_root / "assets" / "gameplay" / "gp_minecraft_7yl7Wc1dtWc.mp4",
            ],
            "script": (
                "A Samsung finalmente atendeu ao pedido mais antigo dos usuários da linha Galaxy. "
                "Na nova atualização da One UI, você agora pode bloquear qualquer aplicativo individualmente "
                "usando sua impressão digital, reconhecimento facial, padrão ou PIN de segurança. "
                "Antes dessa função nativa, quem queria privacidade extra no WhatsApp, galeria de fotos ou banco "
                "precisava recorrer a aplicativos de terceiros cheios de propagandas suspeitas ou usar a Pasta Segura. "
                "Agora, o bloqueio acontece direto no sistema operacional, com criptografia integrada ao processador Knox. "
                "Assim que você tenta abrir o app protegido, a tela de biometria surge instantaneamente sem atraso. "
                "O recurso estreou na versão beta e está sendo liberado gradualmente para os aparelhos compatíveis. "
                "Seu celular já recebeu a novidade? Deixa nos comentários e segue aqui para mais dicas de tecnologia."
            ),
        },
        {
            "name": "short_pulso_radio_misterio_espaco.mp4",
            "hook_title": "SINAL MISTERIOSO REPETE NO ESPAÇO",
            "custom_title": "Astrônomos Detectam Pulso de Rádio Cósmico Repetido a Cada 22 Minutos | Ciência Hoje",
            "style_key": "thalita_hd",
            "niche": "noticias_mundiais",
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4",
                repo_root / "assets" / "gameplay" / "gp_minecraft_7yl7Wc1dtWc.mp4",
                repo_root / "assets" / "gameplay" / "gp_gta_ramp_a_QRwCGtf_Q.mp4",
            ],
            "script": (
                "Astrônomos em todo o mundo estão perplexos com um sinal de rádio captado das profundezas do universo "
                "que desafia as leis conhecidas da física estelar. O objeto cósmico emite ondas de rádio extremamente brilhantes "
                "que duram até cinco minutos seguidos e se repetem com precisão milimétrica a cada vinte e dois minutos. "
                "Pela teoria astronômica tradicional, estrelas de nêutrons ou pulsares de rotação lenta não deveriam ter "
                "energia magnética suficiente para gerar emissões tão poderosas nessa frequência periódica. "
                "Cientistas da Universidade de Curtin já confirmaram que não se trata de interferência terrestre nem satélite. "
                "A principal hipótese atual é que seja um magnetar ultra-lento ou uma classe de corpo celeste nunca antes observada. "
                "Será que estamos descobrindo um novo fenômeno do cosmos? Deixa sua opinião e segue para mais exploração espacial."
            ),
        },
        {
            "name": "short_jujutsu_sukuna_dedos_segredo.mp4",
            "hook_title": "O SEGREDO DOS DEDOS DE SUKUNA",
            "custom_title": "Por que os Dedos de Sukuna São Indestrutíveis em Jujutsu Kaisen? Teoria Revelada",
            "style_key": "narrador_pro",
            "niche": "entretenimento_animes",
            "bg_candidates": [
                repo_root / "assets" / "gameplay" / "gp_dbz_trunks_real.mp4",
                repo_root / "assets" / "gameplay" / "gp_gta_ramp_a_QRwCGtf_Q.mp4",
                repo_root / "assets" / "gameplay" / "gp_drone_cinema_DesiBXmyCBQ.mp4",
            ],
            "script": (
                "Você já se perguntou por que nem mesmo Satoru Gojo ou o fogo do próprio Sukuna conseguem destruir "
                "um único dedo do Rei das Maldições? A resposta está escondida em um dos princípios mais profundos "
                "do sistema de energia amaldiçoada de Jujutsu Kaisen: os votos de restrição após a morte. "
                "Na Era de Ouro de Heian, quando Sukuna dividiu sua alma em vinte objetos amaldiçoados de grau especial, "
                "ele aceitou a restrição de ficar completamente inerte e dormente por mais de mil anos. "
                "Em troca dessa limitação absoluta, os seus fragmentos receberam a propriedade da indestrutibilidade permanente. "
                "Nenhum ataque de energia pura consegue sobrepor uma regra cósmica forjada por pacto de alma. "
                "A única maneira real de erradicá-los para sempre é através de um receptáculo humano como Yuji Itadori. "
                "Você já conhecia essa regra dos pactos? Comenta o que acha e segue para mais teorias de anime."
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
        if not item.get("force_rerender") and out_mp4.is_file() and out_mp4.stat().st_size > 5_000_000:
            print(f"[EXISTS] {out_mp4.name} already rendered ({out_mp4.stat().st_size / (1024*1024):.2f} MB), skipping re-render.")
            audit = audit_short_end_to_end(out_mp4, max_duration=180.0, vision_check=False)
            elapsed = 0.1
        else:
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
            audit = res.get("visual_audit") or audit_short_end_to_end(out_mp4, max_duration=180.0, vision_check=False)

        passed = bool(audit.get("passed") or audit.get("approved"))
        print(f"[AUDIT] Passed: {passed} | Quality Score: {audit.get('quality_score')} | EBU R128: {audit.get('loudnorm_compliant')}")
        results.append({"video": str(out_mp4), "audit": audit, "elapsed_sec": round(elapsed, 1), "passed": passed})

    print("\n=======================================================")
    print(f"BATCH FINISHED! Total generated: {len(results)}")
    for r in results:
        print(f" - {Path(r['video']).name}: passed={r['passed']} in {r['elapsed_sec']}s")


if __name__ == "__main__":
    main()
