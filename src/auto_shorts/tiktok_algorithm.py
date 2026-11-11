"""TikTok For You (FYP) Reverse-Engineered Cohort Scorer & Cognitive Mentalism Engine.

Models TikTok's documented signal weights (Rewatch/Loop, 2s Hold Rate, Completion Rate,
Share/Save velocity, Niche Coherence) alongside applied mentalism & visual-cortex framing
for every configured Brazilian niche in AutoShorts Studio.
"""

import re
from typing import Dict, List, Optional

from .config import NICHES, PLATFORMS


NICHE_MENTALISM_PLAYBOOKS: Dict[str, Dict] = {
    "financas": {
        "niche": "financas",
        "brain_trigger": "Aversao a Perda + Ilusao de Acesso Restrito",
        "mentalism_technique": "Pressuposicao Oculta ('Voce ja percebeu onde somem R$ 300 por mes sem notar?')",
        "visual_blueprint": "Cortes rapidos a cada 3.2s com contraste numerico, setas/graficos ou rotina urbana real + legenda amarela em safe-zone.",
        "eye_anchor": "Numero concreto + palavra de risco nos primeiros 1.8s.",
        "comment_trigger": "Pergunta binaria de opiniao financeira (ex: 'Voce deixaria no banco ou faria isso?').",
        "share_driver": "Salvar como checklist anti-prejuizo / enviar para parceiro(a).",
        "ideal_bpm_cuts_sec": 3.2,
        "recommended_layout": "blur_bg",
        "hashtags": ["#financas", "#dinheiro", "#educacaofinanceira", "#tiktokbrasil"],
    },
    "ia_tech": {
        "niche": "ia_tech",
        "brain_trigger": "Efeito Uau Imediato + Medo de Ficar para Tras (FOMO Cognitivo)",
        "mentalism_technique": "Contraste Futuro-Presente ('Enquanto voce faz isso em 2 horas, esse app faz em 4 segundos offline')",
        "visual_blueprint": "Tela em movimento ou cyberpunk/tech B-Roll a cada 2.8s com zoom de foco no resultado final antes de explicar como.",
        "eye_anchor": "Mostrar o resultado impossivel no frame 0-2s, depois revelar o passo.",
        "comment_trigger": "Desafio pratico ('Comenta TESTAR ou me diz se usaria no celular').",
        "share_driver": "Salvar tutorial / mandar no grupo de trabalho ou faculdade.",
        "ideal_bpm_cuts_sec": 2.8,
        "recommended_layout": "blur_bg",
        "hashtags": ["#inteligenciaartificial", "#tecnologia", "#ia", "#produtividade"],
    },
    "entretenimento_animes": {
        "niche": "entretenimento_animes",
        "brain_trigger": "Loop Aberto de Zeigarnik + Detalhe Oculto (Foreshadowing)",
        "mentalism_technique": "Desvio de Atencao Visual ('99% viu essa cena, mas quase ninguem olhou para o canto esquerdo nesse segundo')",
        "visual_blueprint": "Troca de cena a cada 2.6s com zoom abrupto em expressao facial ou pista visual + contraste alto.",
        "eye_anchor": "Contradicao direta logo no 1o frame ('Esse personagem nunca foi o vilao').",
        "comment_trigger": "Debate de lore ('Concorda com essa teoria ou acha que o autor mudou de ideia?').",
        "share_driver": "Mandar para amigo que assiste o mesmo anime.",
        "ideal_bpm_cuts_sec": 2.6,
        "recommended_layout": "center_crop",
        "hashtags": ["#anime", "#teoria", "#animesbrasil", "#manga"],
    },
    "desenvolvimento_pessoal": {
        "niche": "desenvolvimento_pessoal",
        "brain_trigger": "Efeito Barnum / Leitura Fria (Espelho Mental)",
        "mentalism_technique": "Cold Reading Empatico ('Se voce abre o celular ao acordar e sente cansaco antes das 9h, escuta essa regra')",
        "visual_blueprint": "Parkour / chuva urbana / horizonte em ritmo constante de 3.8s reduzindo ansiedade visual enquanto voz calma cria intimidade.",
        "eye_anchor": "Leitura comportamental especifica na 2a pessoa ('Voce faz isso quando...').",
        "comment_trigger": "Identificacao silenciosa ('Se voce ja passou por isso, comenta EU').",
        "share_driver": "Salvar para reler ou repostar nos Stories/Status.",
        "ideal_bpm_cuts_sec": 3.8,
        "recommended_layout": "blur_bg",
        "hashtags": ["#mentalidade", "#habitos", "#psicologia", "#foco"],
    },
    "saude_fitness": {
        "niche": "saude_fitness",
        "brain_trigger": "Contraste Somatico + Quebra de Mito Popular",
        "mentalism_technique": "Inversao Cognitiva ('O alimento que voce acha saudavel pode estar travando seu sono hoje')",
        "visual_blueprint": "B-Roll de movimento/treino limpo e bem iluminado a cada 3.2s; evita frames escuros abaixo de 35 luma.",
        "eye_anchor": "Mito comum riscado visualmente nos primeiros 2 segundos.",
        "comment_trigger": "Checagem de rotina ('Quantas horas voce dormiu ontem?').",
        "share_driver": "Salvar dica pratica / enviar para amigo de treino ou familia.",
        "ideal_bpm_cuts_sec": 3.2,
        "recommended_layout": "center_crop",
        "hashtags": ["#saude", "#neurociencia", "#treino", "#habitos"],
    },
    "podcast": {
        "niche": "podcast",
        "brain_trigger": "Escuta Social Privilegiada + Triangulacao de Debate",
        "mentalism_technique": "Interrupcao de Padrao Conversacional — comeca direto no meio da resposta polemica, sem 'ola' nem introducao",
        "visual_blueprint": "Topo/Base 2 Telas (`split_top_bottom`) com rosto expressivo em cima + gameplay satisfatorio embaixo segurando cortex motor.",
        "eye_anchor": "Frase de impacto incompleta no topo + expressao facial nos primeiros 1.5s.",
        "comment_trigger": "Polarizacao respeitosa ('Quem tem razao nesse trecho?').",
        "share_driver": "Enviar para amigo debatendo o mesmo assunto.",
        "ideal_bpm_cuts_sec": 3.4,
        "recommended_layout": "split_top_bottom",
        "hashtags": ["#podcast", "#cortespodcast", "#debate", "#brasil"],
    },
    "concursos": {
        "niche": "concursos",
        "brain_trigger": "Atalho Cognitivo + Micro-Dopamina de Acerto",
        "mentalism_technique": "Ancoragem de Segredo ('A regra de 10 segundos que elimina 80% das pegadinhas da banca')",
        "visual_blueprint": "Alternancia limpa de quadros a cada 3.5s com foco em memorizacao e karaoke 3 palavras por bloco.",
        "eye_anchor": "Pergunta-teste rapida nos primeiros 2s ('Qual voce marcaria aqui?').",
        "comment_trigger": "Gabarito nos comentarios ('A ou B? Comenta antes do final!').",
        "share_driver": "Salvar obrigatorio para revisar na vespera da prova.",
        "ideal_bpm_cuts_sec": 3.5,
        "recommended_layout": "blur_bg",
        "hashtags": ["#concursos", "#estudos", "#dicasdeestudo", "#carreira"],
    },
    "noticias_mundiais": {
        "niche": "noticias_mundiais",
        "brain_trigger": "Urgencia Contextual + Efeito Domino Local",
        "mentalism_technique": "Ponte Global -> Bolso ('O que aconteceu hoje fora do pais vai bater no seu dia a dia por este motivo')",
        "visual_blueprint": "Alternancia dinamica a cada 3.0s entre cenas de cidade, tecnologia, transporte e mundo com gancho jornalismo direto.",
        "eye_anchor": "Fato concreto + consequencia pratica nos primeiros 2s.",
        "comment_trigger": "Previsao de impacto ('Isso melhora ou piora para o Brasil?').",
        "share_driver": "Compartilhar novidade fresca em grupos antes da concorrencia.",
        "ideal_bpm_cuts_sec": 3.0,
        "recommended_layout": "blur_bg",
        "hashtags": ["#noticias", "#mundohoje", "#atualidades", "#brasil"],
    },
    "geral": {
        "niche": "geral",
        "brain_trigger": "Lacuna de Curiosidade + Quebra de Expectativa no Climax",
        "mentalism_technique": "Loop Circular Sintatico (ultima frase termina inacabada e encaixa direto no comeco sem pausa)",
        "visual_blueprint": "Cortes multi-cena a cada 3.3s com alta luminancia e legenda karaoke centralizada fora da zona dos icones.",
        "eye_anchor": "Promessa inesperada sem entregar a resposta antes dos 75% do video.",
        "comment_trigger": "Pergunta aberta de curiosidade ou votacao rapida.",
        "share_driver": "Salvar curiosidade ou marcar alguem que nao sabia.",
        "ideal_bpm_cuts_sec": 3.3,
        "recommended_layout": "blur_bg",
        "hashtags": ["#curiosidades", "#storytelling", "#brasil", "#fy"],
    },
}

_SENSORY_AND_LOOP_MARKERS = (
    "olha", "imagina", "percebe", "veja", "repare", "agora", "segredo",
    "porque", "entao", "nunca", "erro", "detalhe", "descubra", "mente",
    "ninguem", "verdade", "isso explica", "por isso",
)
_SPAM_GENERIC_TAGS = {"#fyp", "#fypage", "#viral", "#foryou", "#foryoupage", "#explore"}


def get_niche_mentalism_playbook(niche: str) -> Dict:
    """Return the TikTok reverse-engineered cohort + mentalism playbook for any niche."""
    key = str(niche or "geral").strip().lower()
    if key in NICHE_MENTALISM_PLAYBOOKS:
        return dict(NICHE_MENTALISM_PLAYBOOKS[key])
    return {**NICHE_MENTALISM_PLAYBOOKS["geral"], "niche": key}


def score_short_for_tiktok_algorithm(
    pack: Optional[Dict] = None,
    validation: Optional[Dict] = None,
    filename: str = "",
) -> Dict:
    """Reverse-engineered TikTok FYP cohort readiness scorecard (0-100)."""
    p = pack or {}
    v = validation or p.get("validation") or {}
    vis = (p.get("visual_audit") or {}).get("visual") or {}
    title = str(p.get("title") or filename or "").strip()
    hook = str(p.get("hook_title") or "").strip()
    cap = str(p.get("caption") or "").strip()
    tags = [str(t).strip() for t in (p.get("hashtags") or [])]
    niche = str(p.get("niche") or "geral").strip().lower()
    playbook = get_niche_mentalism_playbook(niche)

    dur = float(v.get("duration") or 0.0)
    cues = int(v.get("subtitle_cues") or 0)
    overlaps = int(v.get("subtitle_overlaps") or 0)
    bg_style = str(p.get("background_style") or "")
    combined = f"{hook} {title} {cap}".lower()

    tips: List[str] = []

    # 1. Rewatch / Loop & Duration Fit (35 pts)
    loop_pts = 0
    if 61.0 <= dur <= 88.0:
        loop_pts += 22  # TikTok Creator Rewards monetizable window (60s+)
    elif 14.0 <= dur <= 34.0:
        loop_pts += 20  # High completion / viral rewatch sprint
    elif 34.0 < dur < 61.0:
        loop_pts += 14
    else:
        loop_pts += 8
        tips.append("Mire 15-32s para alcance viral rapido ou 62-75s para monetizacao TikTok Creator Rewards.")

    if any(m in cap.lower() for m in ("e e exatamente", "por isso", "comenta", "salva", "voce")):
        loop_pts += 13
    else:
        loop_pts += 7
        tips.append("Feche a ultima frase conectando com o gancho inicial + CTA de comentario/salvamento.")

    # 2. 2s Neural Pattern Interrupt & Mentalism Hook (25 pts)
    hook_pts = 0
    hk_words = hook.split()
    if 2 <= len(hk_words) <= 6 and len(hook) <= 38:
        hook_pts += 13
    else:
        hook_pts += 6
        tips.append("Mantenha o gancho superior entre 2 e 6 palavras (<=38 chars) para leitura instantanea em 1.5s.")

    mental_hits = sum(1 for tok in _SENSORY_AND_LOOP_MARKERS if tok in combined)
    if mental_hits >= 2:
        hook_pts += 12
    elif mental_hits == 1:
        hook_pts += 8
    else:
        hook_pts += 4
        tips.append(f"Use gatilho mentalista ({playbook['mentalism_technique'].split('(')[0].strip()}) logo nos primeiros 2s.")

    # 3. High-Friction Engagement & Visual Orienting Reflex (25 pts)
    eng_pts = 0
    has_question = "?" in cap or "comenta" in cap.lower() or "qual" in cap.lower()
    if has_question:
        eng_pts += 10
    else:
        eng_pts += 4
        tips.append("Inclua pergunta polarizadora ou pedido de opiniao para disparar peso de Comentario/Share no FYP.")

    has_broll_var = ("+" in bg_style) or float(vis.get("motion_delta") or 0.0) >= 12.0
    if cues >= 6 and overlaps == 0 and has_broll_var:
        eng_pts += 15
    elif cues >= 2 and overlaps == 0:
        eng_pts += 10
    else:
        eng_pts += 5
        tips.append("Combine cortes visuais a cada ~3s com legenda karaoke sem sobreposicao (retençao no feed mudo).")

    # 4. Cohort Indexing, Safe-Zone & Audio Hygiene (15 pts)
    idx_pts = 0
    clean_tags = [t for t in tags if t.lower() not in _SPAM_GENERIC_TAGS]
    if 3 <= len(clean_tags) <= 5:
        idx_pts += 7
    else:
        idx_pts += 3
        tips.append("Use 3 a 5 hashtags especificas de nicho (evite #fyp/#viral genericos que confundem o cohort).")

    if v.get("valid"):
        idx_pts += 8
    else:
        idx_pts += 2
        tips.append("Valide integridade 9:16 + loudness (-14 LUFS) antes de publicar.")

    total = max(0, min(100, loop_pts + hook_pts + eng_pts + idx_pts))
    if total >= 82:
        cohort_stage = "For You Tier 3 (10k-100k+ FYP Cascade)"
    elif total >= 65:
        cohort_stage = "For You Tier 2 (1k-5k Test Batch)"
    else:
        cohort_stage = "Cold-Start Ajuste (Otimizar Gancho/Loop)"

    return {
        "tiktok_score": total,
        "cohort_forecast": cohort_stage,
        "monetization_eligible_60s": dur >= 60.0,
        "niche": niche,
        "playbook": playbook,
        "signals": {
            "rewatch_loop_35": loop_pts,
            "hold_2s_mentalism_25": hook_pts,
            "share_comment_visual_25": eng_pts,
            "cohort_indexing_15": idx_pts,
        },
        "tips": tips,
    }


def build_mentalist_script_blueprint(
    topic: str,
    niche: str = "geral",
    target_duration_sec: int = 64,
) -> Dict:
    """Synthesize a 4-beat TikTok FYP & Mentalist retention script blueprint in PT-BR."""
    clean_topic = re.sub(r"\s+", " ", str(topic or "").strip()) or "um detalhe que quase ninguem nota"
    pb = get_niche_mentalism_playbook(niche)
    label = NICHES[niche].label if niche in NICHES else pb["niche"]
    words_target = max(90, min(220, int(round(target_duration_sec * 2.65))))

    hook_2s = f"Para de rolar agora: quase ninguem percebe o que {clean_topic} faz nos primeiros minutos."
    open_loop = (
        f"Voce provavelmente ja sentiu isso sem saber explicar — e o motivo nao e o que todo mundo repete por ai. "
        f"Presta atencao nesse detalhe visual enquanto eu te mostro a regra por tras de {clean_topic}."
    )
    reframe = (
        f"Quando voce aplica o principio de {pb['brain_trigger'].lower()}, a maioria cai no piloto automatico. "
        f"Quem inverte essa ordem ganha vantagem silenciosa logo na primeira tentativa."
    )
    loop_cta = (
        f"{pb['comment_trigger']} Salva esse video para testar hoje e e exatamente por isso que..."
    )

    return {
        "topic": clean_topic,
        "niche": niche,
        "niche_label": label,
        "target_duration_sec": target_duration_sec,
        "recommended_words": words_target,
        "brain_trigger": pb["brain_trigger"],
        "mentalism_technique": pb["mentalism_technique"],
        "visual_blueprint": pb["visual_blueprint"],
        "recommended_layout": pb["recommended_layout"],
        "beats": {
            "0_a_2s_pattern_interrupt": hook_2s,
            "2_a_18s_zeigarnik_open_loop": open_loop,
            "18_a_52s_mentalist_reframe": reframe,
            "52s_end_loop_bridge_cta": loop_cta,
        },
        "full_narration_script": f"{hook_2s} {open_loop} {reframe} {loop_cta}",
        "hashtags": pb["hashtags"],
    }


def get_tiktok_algorithm_blueprint() -> Dict:
    """Return full reverse-engineered TikTok FYP weighting model and niche playbooks for UI/API."""
    return {
        "algorithm_model": "TikTok FYP Cohort Cascade + Creator Rewards 60s+ (RE Profile)",
        "signal_weights": [
            {"signal": "Taxa de Rewatch / Loop + Conclusao", "weight_pct": 35, "target": ">= 70% conclusao ou >= 1.15x loops"},
            {"signal": "Retencao 2s (Pattern Interrupt Neural)", "weight_pct": 25, "target": ">= 75% nao desliza nos 2s"},
            {"signal": "Shares + Saves + Comentarios Profundos", "weight_pct": 25, "target": "1 share vale ~5x mais que like"},
            {"signal": "Coerencia Semantica de Nicho + Audio/Safe-Zone", "weight_pct": 15, "target": "3-5 hashtags de nicho + -14 LUFS"},
        ],
        "cohort_stages": [
            {"stage": "1. Indexacao NLP/Visao (0-15 min)", "size": "0 views", "gate": "ASR audio + texto topo + ritmo visual (~3s) definem o nicho exato."},
            {"stage": "2. Coorte Fria Inicial", "size": "200-500 views", "gate": "Precisa superar 65% retencao aos 3s e zero frames congelados."},
            {"stage": "3. Coorte Ampliada + Feed Explorar", "size": "1k-15k views", "gate": "Disparado por Compartilhamentos (DM/WhatsApp), Salvamentos e Debates."},
            {"stage": "4. Viralizacao & Creator Rewards", "size": "50k-1M+ views", "gate": "Originalidade >= 60s (RPM elegivel) + forte loop final->inicio."},
        ],
        "playbooks": NICHE_MENTALISM_PLAYBOOKS,
        "platforms": {k: {"sweet_spot": v.sweet_spot, "min_s": v.min_duration, "max_s": v.max_duration} for k, v in PLATFORMS.items()},
    }

