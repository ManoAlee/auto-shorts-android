"""Full virtual YouTube channel production team (7 specialized Personas + Weekly Editorial Planner)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional

from .anime_trends import get_releasing_anime_radar
from .config import NICHES
from .highlights import _parse_json_loose, call_gemini_or_openai
from .narrator import humanize_ptbr_script
from .tiktok_algorithm import build_mentalist_script_blueprint, get_niche_mentalism_playbook


@dataclass(frozen=True)
class ChannelPersona:
    id: str
    role: str
    name: str
    specialty: str
    pacing_rule: str
    deliverable: str
    recommended_voice: str


CHANNEL_PERSONAS: Dict[str, ChannelPersona] = {
    "trend_hunter": ChannelPersona(
        id="trend_hunter",
        role="Cacador de Tendencias",
        name="Rafael Radar",
        specialty="Monitora AniList ao vivo, podcasts em alta no Brasil e picos de busca antes da concorrencia.",
        pacing_rule="Prioriza temas lancados nas ultimas 24h-72h nos horarios nobres (11:45, 18:15, 21:00).",
        deliverable="Pauta quente validada com query de busca e playlist alvo.",
        recommended_voice="narrador_pro",
    ),
    "showrunner": ChannelPersona(
        id="showrunner",
        role="Diretor de Retencao e Pacing",
        name="Camila Corte-Fino",
        specialty="Controla ritmo, corte de silencios, zoom dinamico (punch_zoom) e duracao exata por plataforma.",
        pacing_rule="Gancho obrigatorio nos primeiros 2.5s; silêncio maximo 0.40s; YouTube Shorts 34s-52s; TikTok >= 62s.",
        deliverable="Parametros tecnicos de ritmo (duracao, silencio, pattern interrupt a cada 5s).",
        recommended_voice="authority",
    ),
    "screenwriter": ChannelPersona(
        id="screenwriter",
        role="Roteirista Conversacional PT-BR",
        name="Lucas Roteiro",
        specialty="Escreve roteiros em 3 atos com linguagem humana brasileira, curiosidade imediata e loop final.",
        pacing_rule="Frases curtas de 8-14 palavras para leitura natural e legendas de 3 palavras sem cansaco visual.",
        deliverable="Roteiro estruturado (Gancho 0-3s -> Desenvolvimento -> Climax + CTA).",
        recommended_voice="narrador_pro",
    ),
    "thumb_strategist": ChannelPersona(
        id="thumb_strategist",
        role="Designer de Hook e Thumbnail CTR",
        name="Marina CTR",
        specialty="Cria banners de topo curtos (<= 36 caracteres) e capas 16:9 / 9:16 com alto contraste.",
        pacing_rule="Texto limpo em no maximo 5 palavras com selo de nicho e contraste alto em tela pequena.",
        deliverable="Hook banner + thumbnail 16:9 + cover 9:16.",
        recommended_voice="podcast_female",
    ),
    "seo_growth": ChannelPersona(
        id="seo_growth",
        role="Estrategista de SEO e Playlists",
        name="Tiago Growth",
        specialty="Otimiza titulos reais curiosos, descricao completa com creditos e roteamento de playlists.",
        pacing_rule="Titulo ate 85 chars sem spam generico + #Shorts + 4 hashtags segmentadas + playlist do nicho.",
        deliverable="Pacote de publicacao completo (.publish.json) pronto para busca e Shorts feed.",
        recommended_voice="authority",
    ),
    "qa_auditor": ChannelPersona(
        id="qa_auditor",
        role="Auditor Tecnico de Midia",
        name="Helena QA",
        specialty="Impede envio de videos mudos, horizontais ou com sobreposicao de legendas.",
        pacing_rule="Bloqueia upload se 9:16 falhar, se audio < -55 dB ou se houver conflito de timestamp no .ass/.srt.",
        deliverable="Laudo tecnico combinado Python ffprobe/volumedetect + auditor ISO-BMFF em C.",
        recommended_voice="authority",
    ),
    "channel_manager": ChannelPersona(
        id="channel_manager",
        role="Showrunner do Canal e Planner",
        name="Bruno Grade",
        specialty="Organiza o calendario semanal multi-nicho mantendo constancia sem saturar um unico assunto.",
        pacing_rule="Alterna 3 faixas diarias (11:45 Shorts Rapido, 18:15 Podcast/Anime, 21:00 Curiosidade/Tech).",
        deliverable="Grade semanal de 7 dias com tema, roteiro base, playlist e meta de retencao.",
        recommended_voice="narrador_pro",
    ),
}

_PEAK_SLOTS = [
    ("11:45", "youtube_shorts", 42, "blur_bg"),
    ("18:15", "youtube_shorts", 48, "split_top_bottom"),
    ("21:00", "tiktok_rewards", 65, "center_crop"),
]

_DEFAULT_ROTATION = [
    "podcast",
    "entretenimento_animes",
    "ia_tech",
    "financas",
    "podcast",
    "entretenimento_animes",
    "desenvolvimento_pessoal",
]


def list_channel_personas() -> List[Dict]:
    """Return structured metadata of all 7 channel production personas."""
    return [
        {
            "id": p.id,
            "role": p.role,
            "name": p.name,
            "specialty": p.specialty,
            "pacing_rule": p.pacing_rule,
            "deliverable": p.deliverable,
            "recommended_voice": p.recommended_voice,
        }
        for p in CHANNEL_PERSONAS.values()
    ]


def is_llm_configured() -> bool:
    return bool(
        os.getenv("OPENROUTER_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("LOCAL_LLM_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )


def build_persona_script_brief(
    topic: str,
    niche: str = "podcast",
    platform: str = "youtube_shorts",
    use_llm: bool = True,
) -> Dict:
    """Assemble a 3-act PT-BR script + timing plan reviewed by Screenwriter, Showrunner & SEO."""
    clean_topic = humanize_ptbr_script(topic or "o detalhe escondido que quase ninguém percebeu")
    profile = NICHES.get(niche, NICHES["geral"])
    playbook = get_niche_mentalism_playbook(profile.key)
    bp = build_mentalist_script_blueprint(clean_topic, niche=profile.key, target_duration_sec=65 if platform == "tiktok_rewards" else 44)
    is_long_short = platform == "tiktok_rewards"
    target_sec = 65 if is_long_short else 44

    hook_line = humanize_ptbr_script(bp["beats"]["0_a_2s_pattern_interrupt"])
    body_line = humanize_ptbr_script(
        f"{bp['beats']['2_a_18s_zeigarnik_open_loop']} {bp['beats']['18_a_52s_mentalist_reframe']}"
    )
    climax_line = humanize_ptbr_script(bp["beats"]["52s_end_loop_bridge_cta"])
    hook_banner = clean_topic.upper()[:34]
    title = f"{clean_topic[:74]} — O Detalhe Que Ninguém Notou"[:90]
    engine_used = "heuristic_team"

    if use_llm and is_llm_configured():
        prompt = (
            f"Você é a equipe de criação do canal ({profile.label}) no formato {platform} ({target_sec}s).\n"
            f"Tema: {clean_topic}\n"
            f"Gatilho neuro-mentalista obrigatorio: {playbook['brain_trigger']} ({playbook['mentalism_technique']}).\n"
            f"Regra de retencao: prenda nos primeiros 2s sem saudacao robotica, use loop aberto (Zeigarnik) e termine conectando com o inicio para gerar rewatch.\n"
            "Escreva em português do Brasil falado e natural.\n"
            "Responda SOMENTE JSON válido:\n"
            '{"seo_title":"string max 80 chars","hook_banner":"MAX 5 PALAVRAS MAIUSCULAS",'
            '"gancho":"frase forte 0-3s","desenvolvimento":"2 frases diretas","climax_cta":"fechamento impactante com loop e CTA"}'
        )
        try:
            raw = call_gemini_or_openai(prompt)
            data = _parse_json_loose(raw)
            if isinstance(data, dict) and data.get("gancho") and data.get("desenvolvimento"):
                hook_line = humanize_ptbr_script(str(data["gancho"]))
                body_line = humanize_ptbr_script(str(data["desenvolvimento"]))
                climax_line = humanize_ptbr_script(str(data.get("climax_cta") or climax_line))
                if data.get("hook_banner"):
                    hook_banner = str(data["hook_banner"]).strip().upper()[:38]
                if data.get("seo_title"):
                    title = str(data["seo_title"]).strip()[:90]
                engine_used = "llm_team"
        except Exception:
            pass

    full_script = f"{hook_line} {body_line} {climax_line}"

    return {
        "niche": profile.key,
        "niche_label": profile.label,
        "platform": platform,
        "target_duration_sec": target_sec,
        "recommended_silence_sec": 0.40 if platform == "youtube_shorts" else 0.50,
        "pattern_interrupt_sec": 5,
        "hook_banner": hook_banner,
        "seo_title": title,
        "playlist": f"{profile.label.split(',')[0].strip()} - Shorts",
        "script": full_script,
        "engine_used": engine_used,
        "mentalism_playbook": playbook,
        "acts": {
            "0_a_3s_gancho": hook_line,
            "3_a_35s_desenvolvimento": body_line,
            "final_climax_cta": climax_line,
        },
        "signed_off_by": [
            CHANNEL_PERSONAS["screenwriter"].name,
            CHANNEL_PERSONAS["showrunner"].name,
            CHANNEL_PERSONAS["seo_growth"].name,
        ],
    }


def generate_channel_planner(days: int = 7, include_live_anime: bool = True) -> Dict:
    """Build a multi-day publishing schedule coordinated by the full 7-persona team."""
    live_animes: List[Dict] = []
    if include_live_anime:
        try:
            live_animes = get_releasing_anime_radar(limit=4)
        except Exception:
            live_animes = []

    today = datetime.now()
    schedule: List[Dict] = []
    anime_idx = 0

    for d in range(max(1, min(14, days))):
        day_dt = today + timedelta(days=d)
        niche = _DEFAULT_ROTATION[d % len(_DEFAULT_ROTATION)]
        hour_str, platform, target_sec, layout = _PEAK_SLOTS[d % len(_PEAK_SLOTS)]
        profile = NICHES.get(niche, NICHES["geral"])

        if niche == "entretenimento_animes" and anime_idx < len(live_animes):
            anime = live_animes[anime_idx]
            anime_idx += 1
            topic = f"{anime['title']} Episódio {max(1, (anime.get('next_episode') or 2) - 1)}"
            query = anime["youtube_query"]
        else:
            topic = profile.label
            query = f"{profile.key.replace('_', ' ')} podcast corte brasil"

        brief = build_persona_script_brief(topic, niche=niche, platform=platform)
        schedule.append({
            "day": day_dt.strftime("%Y-%m-%d"),
            "weekday": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"][day_dt.weekday()],
            "publish_time": hour_str,
            "niche": niche,
            "niche_label": profile.label,
            "platform": platform,
            "layout": layout,
            "target_duration_sec": target_sec,
            "topic": topic,
            "search_query": query,
            "seo_title": brief["seo_title"],
            "hook_banner": brief["hook_banner"],
            "playlist": brief["playlist"],
            "script_suggestion": brief["script"],
        })

    return {
        "team_size": len(CHANNEL_PERSONAS),
        "personas": list_channel_personas(),
        "planner_days": len(schedule),
        "schedule": schedule,
    }

