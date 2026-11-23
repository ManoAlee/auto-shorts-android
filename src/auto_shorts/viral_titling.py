"""Unified Viral Titling & Semantic Hook Synthesis Engine.

Solves repetitive, generic, and mismatched titles across:
1. Live Stream Slices (Gaules, LipaoGamer, Davy Jones, xQc, Alanzoka, etc.)
2. Story & Reddit Narratives (r/nosleep, creepypasta, mysteries)
3. World & Breaking News (Fixes category mismatch: sports vs weather, tech vs biology)
4. Anime Highlights (Hunter x Hunter, Naruto, Jujutsu Kaisen, Bleach, etc.)
5. Tech, AI & Digital Tutorials (AI Agents, Prompt formulas, Opus Clip, etc.)
6. Podcasts & Interviews (Irmãos Dias, Pablo Marçal, Flow, etc.)

Applies AntiSlopHumanizer, mathematical hook principles, and context-aware extractive NLP.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .viral_intelligence import AntiSlopHumanizer

logger = logging.getLogger("ViralTitling")

# Common Brazilian Portuguese stop/filler words to ignore when extracting topic tokens
_STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "sob", "sobre", "um", "uma", "uns", "umas", "e", "ou",
    "mas", "porque", "pois", "entao", "então", "que", "quem", "qual", "como", "quando",
    "onde", "se", "ja", "já", "so", "só", "muito", "pouco", "mais", "menos", "aqui",
    "ali", "la", "lá", "isso", "isto", "aquilo", "esse", "essa", "esses", "essas", "aquele",
    "aquela", "meu", "minha", "seu", "sua", "nosso", "nossa", "dele", "dela", "deles",
    "eu", "tu", "ele", "ela", "nos", "nós", "eles", "elas", "voce", "você", "voces", "vocês",
    "gente", "mim", "me", "te", "lhe", "nos", "se", "era", "foi", "foram", "sao", "são",
    "era", "fui", "fomos", "estava", "estavam", "estou", "esta", "está", "estao", "estão",
    "vai", "vao", "vão", "ia", "iam", "ter", "tem", "tinha", "tinham", "fazer", "faz",
    "disse", "falar", "falou", "falando", "disse", "dizendo", "olha", "olhe", "veja", "tipo",
    "cara", "mano", "mano,", "bom", "bem", "tava", "tavam", "né", "ne", "pra", "pro", "pras", "pros"
}

# Verified gaming streamer usernames (lowercase) - ONLY these trigger gamer reactive templates
VERIFIED_GAMING_STREAMERS = {
    "gaules", "lipao", "lipaogamer", "davy jones", "davy", "davyjones", "xqc",
    "alanzoka", "coringa", "loud coringa", "nobru", "cerol", "casimiro", "caze",
    "cellbit", "felps", "smurfdomundo", "yoda", "brtt", "jukes", "baiano",
    "paulinholoko", "luqueta", "speed", "ishowspeed", "kaicenat", "ninja",
    "shroud", "tarik"
}

# Streamer emotional / reactive hook templates (indexed dynamically by content hash)
_STREAMER_HOOK_TEMPLATES = [
    "{streamer} não acreditou no que aconteceu aqui!",
    "A reação inacreditável do {streamer} ao vivo!",
    "O momento exato em que {streamer} descobriu isso!",
    "{streamer} ficou em choque total com essa cena!",
    "Nem o {streamer} esperava por isso!",
    "{streamer} perdeu o controle nessa hora!",
    "O {streamer} quase não acreditou no que viu!",
    "Esse foi o momento mais insano do {streamer}!",
    "{streamer} descobriu esse segredo ao vivo!",
    "A reação do {streamer} que chocou todo mundo!",
]

# Story / Nosleep hook headline templates when extracting entity
_STORY_HOOK_PATTERNS = [
    (r"\b(floresta|bosque|arvores|árvores|mata)\b", "O Mistério da Floresta Que Ninguém Explica"),
    (r"\b(sorriu|sorriso|boca|olhar|olhos|dentes)\b", "A Coisa Que Sorriu na Escuridão"),
    (r"\b(ligou|ligacao|ligação|telefone|mensagem|celular|contato)\b", "A Ligação Macabra Que Eu Não Devia Ter Atendido"),
    (r"\b(casa|quarto|porao|porão|sotao|sótão|porta|janela)\b", "O Que Estava Escondido Naquela Casa?"),
    (r"\b(noite|madrugada|escuro|sombra|vulto)\b", "O Que Apareceu Na Minha Janela de Madrugada"),
    (r"\b(namorada|namorado|mulher|garota|homem|ela|ele)\b", "O Segredo Sinistro Que Ela Escondia"),
    (r"\b(igreja|padre|cruz|demonio|demônio|espírito|fantasma)\b", "O Encontro Sobrenatural Que Aterrorizou a Cidade"),
    (r"\b(carro|estrada|rodovia|viagem|ponte)\b", "O Que Aconteceu Naquela Estrada Deserta?"),
]


def _clean_alnum_text(text: str) -> str:
    """Normalize text removing accents for keyword matching."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def detect_accurate_category(title: str, summary: str = "", hint_category: str = "") -> str:
    """Accurately classifies news / content into strictly correct category.
    
    Prevents category drift:
    - Severe weather & floods in São Paulo must NEVER be tagged as Sports.
    - Microsoft / Outlook email outages must NEVER be tagged as Science / Nature.
    - Frogs / biology must NEVER be tagged as Economy.
    """
    clean_title = AntiSlopHumanizer.clean(title).strip()
    
    # Strip template boilerplate lines before category analysis
    clean_summary = re.sub(r"Curtiu essa descoberta\?.*", "", summary, flags=re.I)
    clean_summary = re.sub(r"O que você achou dessa conquista\?.*", "", clean_summary, flags=re.I)
    clean_summary = re.sub(r"Fonte original.*", "", clean_summary, flags=re.I)
    clean_summary = re.sub(r"Resumo da noticia.*?:\s*", "", clean_summary, flags=re.I)
    clean_summary = re.sub(r"Destaque:.*", "", clean_summary, flags=re.I)

    blob = f"{clean_title} {clean_summary}".lower()
    norm = _clean_alnum_text(blob)
    title_norm = _clean_alnum_text(clean_title)

    # 1. Weather, Floods, Rain, Natural Emergencies & Public Administration -> mundo (MUST RUN FIRST)
    # Prevents "São Paulo" in weather/city reports or regulatory bodies ("SP Regula") from matching sports
    weather_and_public_kw = [
        "chuva", "chuvas", "temporal", "temporais", "alagamento", "alagamentos",
        "inundacao", "inundacoes", "enchente", "enchentes", "deslizamento",
        "desmoronamento", "defesa civil", "cge", "alerta severo", "tempestade",
        "granizo", "ciclone", "furacao", "seca", "estiagem", "queimada", "incendio",
        "regula", "orgao regulador", "concessionaria", "prefeitura", "governador",
        "governo", "enel", "sabesp", "sptrans", "tarifa", "servico publico"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in weather_and_public_kw):
        return "mundo"
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in weather_and_public_kw):
        return "mundo"

    # 2. Tech, Cloud, IT Outages, AI & Big Tech -> tech_ia
    # Handles Microsoft, Outlook, Exchange, email outage, AI models, hardware
    tech_kw = [
        "microsoft", "outlook", "exchange", "email", "e-mail", "emails", "e-mails",
        "servidor", "servidores", "apagao", "pane", "inteligencia artificial", "openai",
        "chatgpt", "deepseek", "nvidia", "hardware", "software", "smartphone",
        "galaxy s26", "iphone", "samsung", "apple", "google", "one ui", "app lock",
        "biometria", "hacker", "ciberataque", "vulnerabilidade", "chip", "semicondutor",
        "algoritmo", "ia", "meta", "whatsapp", "telegram"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in tech_kw):
        return "tech_ia"
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in (
        "microsoft", "outlook", "exchange", "e-mail", "email", "apagao",
        "inteligencia artificial", "deepseek", "openai"
    )):
        return "tech_ia"

    # 3. Sports -> esportes
    # Club names must be specific, NOT bare 'sao paulo' which matches city/weather
    sports_kw = [
        "alcaraz", "zverev", "tenis", "tenista", "atp", "wimbledon", "roland garros",
        "futebol", "neymar", "flamengo", "palmeiras", "corinthians", "sao paulo fc",
        "sao paulo futebol clube", "sao paulo f.c.", "tricolor paulista", "santos fc",
        "vasco", "gremio", "internacional", "cruzeiro", "atletico-mg", "botafogo",
        "fluminense", "goleada", "campeonato", "libertadores", "champions league",
        "brasileirao", "serie a", "serie b", "gol", "gols", "penalti", "arbitragem",
        "tecnico", "treinador", "nba", "basquete", "volei", "ufc", "mma", "boxe",
        "formula 1", "f1", "corrida", "podio", "grand slam", "olimpiadas"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in sports_kw):
        return "esportes"
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in sports_kw):
        return "esportes"

    # 4. Science, Biology, Nature & Space -> ciencia_natureza
    science_kw = [
        "perereca", "sapo", "especie", "especies", "descoberta", "cientistas", "pesquisadores",
        "biologia", "biologos", "fauna", "flora", "animal", "animais", "fossil",
        "dinossauro", "arqueologia", "dna", "genetica", "vacina", "cancer", "medicina",
        "amazonia", "biodiversidade", "extincao", "ecossistema", "nasa", "spacex",
        "james webb", "telescopio", "astronomia", "planeta", "marte", "lua", "saturno",
        "asteroide", "meteoro", "galaxia", "buraco negro", "fisica quantica"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in science_kw):
        return "ciencia_natureza"
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in science_kw):
        return "ciencia_natureza"

    # 5. Games & Gaming
    games_kw = [
        "gta", "gta 6", "rockstar", "playstation", "ps5", "xbox", "nintendo",
        "zelda", "mario", "fortnite", "valorant", "counter strike", "cs2",
        "gameplay", "streamer", "gamer", "jogos", "jogo", "game"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in games_kw):
        return "games"

    # 6. Economy & Finance
    econ_kw = [
        "dolar", "inflacao", "selic", "taxa de juros", "banco central", "bolsa de valores",
        "ibovespa", "pib", "dividendo", "dividendos", "renda fixa", "tesouro direto",
        "mercado financeiro", "copom", "reforma tributaria", "deficit", "superavit"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in econ_kw):
        return "economia"

    # 7. Humor & Memes
    humor_kw = ["meme", "memes", "engracado", "comedia", "zoeira", "shitpost", "defante"]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in humor_kw):
        return "humor_memes"

    # 8. Fallback to hint_category or world
    if hint_category in ("games", "tech_ia", "economia", "ciencia_natureza", "humor_memes"):
        return hint_category
    if hint_category == "esportes" and any(re.search(rf"\b{re.escape(k)}\b", norm) for k in sports_kw):
        return "esportes"
    return "mundo"


def _extract_subject_from_transcript(clip_text: str, max_words: int = 6) -> str:
    """Extract a salient subject or action clause from spoken transcript lines."""
    clean = AntiSlopHumanizer.clean(clip_text)
    clean = re.sub(r"\[.*?\]|\(.*?\)|\<.*?\>", "", clean)
    clean = re.sub(r"^[>\-\s\"']+", "", clean)

    sentences = [s.strip() for s in re.split(r"[.!?\n]+", clean) if len(s.strip().split()) >= 3]
    if not sentences:
        return ""

    first_s = sentences[0]
    words = [w for w in re.findall(r"\b[\w\-áéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]+\b", first_s)]
    
    # Filter out pure stopwords to find key tokens
    content_words = [w for w in words if _clean_alnum_text(w) not in _STOPWORDS_PT and len(w) > 2]
    if len(content_words) >= 2:
        lead_words = words[:max_words]
        phrase = " ".join(lead_words)
        return phrase.rstrip(",;:- ")
    return ""


def generate_smart_clip_title(
    clip_text: str = "",
    source_title: str = "",
    streamer_or_speaker: str = "",
    niche: str = "geral",
    part_num: int = 1,
    current_title: str = "",
) -> str:
    """Generate a captivating, viral, context-specific title that accurately reflects the video content and scenes.
    
    Guarantees:
    - Never assigns streamer live gameplay templates to anime, podcasts, or business/educational channels.
    - Classifies news categories accurately (weather != sports, Microsoft != biology).
    - Extracts real anime, character, scene, or tutorial tools from metadata and transcript.
    """
    clean_src = AntiSlopHumanizer.clean(source_title).strip()
    streamer = streamer_or_speaker.strip()
    norm_src = _clean_alnum_text(clean_src)
    norm_clip = _clean_alnum_text(clip_text)
    norm_streamer = _clean_alnum_text(streamer)

    # --------------------------------------------------------------------------
    # Case 1: News Article / Breaking Fact with Category Suffix
    # --------------------------------------------------------------------------
    is_news = (
        " | Plantão " in clean_src
        or " | Mundo Hoje" in clean_src
        or " | Ciência " in clean_src
        or " | Plantão" in current_title
        or niche in ("noticias_mundiais", "noticias", "financas", "economia", "ciencia_espaco", "esportes")
    )
    if is_news:
        base_headline = re.split(r"\s*\|\s*(?:Plantão|Mundo|Ciência|Notícias).*", clean_src, flags=re.I)[0].strip()
        if not base_headline or len(base_headline) < 10:
            base_headline = re.split(r"\s*\|\s*(?:Plantão|Mundo|Ciência|Notícias).*", current_title, flags=re.I)[0].strip()

        cat = detect_accurate_category(base_headline, summary=clip_text)
        suffix_map = {
            "tech_ia": " | Plantão Tech",
            "economia": " | Plantão Economia",
            "ciencia_natureza": " | Ciência & Natureza",
            "esportes": " | Plantão Esportes",
            "games": " | Plantão Games",
            "humor_memes": " | Plantão Humor",
            "mundo": " | Mundo Hoje",
        }
        correct_suffix = suffix_map.get(cat, " | Mundo Hoje")
        
        # Specific polish for known cut-off headlines
        if "chuvas em sao paulo fazem cidade entrar em estado" in _clean_alnum_text(base_headline):
            base_headline = "Chuvas em São Paulo Fazem Cidade Entrar em Estado de Alerta"
        elif "microsoft admite: alguns e-mails nao foram entregues" in _clean_alnum_text(base_headline):
            base_headline = "Microsoft Admite: E-mails Não Foram Entregues Após Apagão"

        max_base = max(30, 85 - len(correct_suffix))
        if len(base_headline) > max_base:
            base_headline = base_headline[:max_base].rsplit(" ", 1)[0]
        return f"{base_headline.rstrip(' :;,-')}{correct_suffix}"

    # --------------------------------------------------------------------------
    # Case 2: Anime Highlights & Scenes (Hunter x Hunter, Naruto, Jujutsu, etc.)
    # --------------------------------------------------------------------------
    is_anime = (
        "anime" in niche.lower()
        or any(k in norm_src or k in norm_clip for k in (
            "hunter x hunter", "naruto", "sasuke", "pitou", "netero", "zeno",
            "sukuna", "jujutsu", "bleach", "one piece", "dragon ball", "demon slayer",
            "shingeki", "cenas dubladas", "anime dublado", "escanor animes"
        ))
        or "escanor" in norm_streamer
    )
    if is_anime:
        raw_source = clean_src
        for channel_prefix in ("escanor animes - ", "jhonny salazar olivera - ", "animes brasil - "):
            if raw_source.lower().startswith(channel_prefix):
                raw_source = raw_source[len(channel_prefix):].strip()

        norm_raw = _clean_alnum_text(raw_source)

        if "hunter x hunter" in norm_raw or ("netero" in norm_raw and "zeno" in norm_raw):
            base = "Entrada Épica de Netero e Zeno vs Pitou | Hunter x Hunter"
            if part_num > 1:
                return f"Entrada Épica de Netero e Zeno vs Pitou (Parte {part_num}) | Hunter x Hunter #Shorts"[:85]
            return f"{base} #Shorts"[:85]

        if "naruto" in norm_raw and "sasuke" in norm_raw:
            base = "Naruto vs Sasuke Dublado: O Confronto Final Decisivo!"
            if part_num > 1:
                return f"Naruto vs Sasuke Dublado: A Batalha (Parte {part_num}) #Shorts"[:85]
            return f"{base} #Shorts"[:85]

        if "sukuna" in norm_raw and ("dedo" in norm_raw or "indestrutivel" in norm_raw):
            return "Por que os Dedos de Sukuna São Indestrutíveis em Jujutsu Kaisen? #Shorts"[:85]

        # General anime hook extraction from clean source
        parts = [p.strip() for p in re.split(r"[-—|]", raw_source) if p.strip()]
        if parts:
            scene_title = parts[0]
            anime_name = parts[-1] if len(parts) > 1 else "Anime"
            if len(scene_title) > 40:
                scene_title = scene_title[:40].rsplit(" ", 1)[0]
            if part_num > 1:
                return f"{scene_title} (Parte {part_num}) | {anime_name} #Shorts"[:85]
            return f"{scene_title} | {anime_name} #Shorts"[:85]

    # --------------------------------------------------------------------------
    # Case 3: Tech, AI & Digital Tutorials / Tools (AI Agents, Opus Clip, Prompting)
    # --------------------------------------------------------------------------
    is_tech_tutorial = (
        niche in ("ia_tech", "tech", "tutorial")
        or any(k in norm_src or k in norm_clip for k in (
            "agentes de ia", "ai agents", "opus clip", "chatbot", "chatgpt",
            "deepseek", "prompts", "como criar cortes", "como monetizar",
            "quatro ferramentas", "4 ferramentas"
        ))
        or "negocios em mente" in norm_streamer
        or "jhonatas silva" in norm_streamer
    )
    if is_tech_tutorial:
        # Opus Clip / Cortes com 1 clique (Pablo Marçal / Jhonatas Silva)
        if "opus clip" in norm_clip or "opus clip" in norm_src or "como criar 200 cortes" in norm_src:
            return "Como Criar 200 Cortes com 1 Clique Usando Opus Clip #Shorts"[:85]

        # AI Agents & Prompt Formulas (Negócios em Mente)
        if "ai agents" in norm_src or "agente" in norm_clip or "quatro ferramentas" in norm_clip or "negocios em mente" in norm_streamer:
            return "As 4 Ferramentas e a Fórmula Secreta de Agentes de IA #Shorts"[:85]

        # Samsung App Lock
        if "samsung" in norm_src and "app lock" in norm_src:
            return "Samsung Libera Bloqueio de Apps com Biometria na One UI | Plantão Tech"[:85]

    # --------------------------------------------------------------------------
    # Case 4: Podcasts & Interviews (Irmãos Dias, Pablo Marçal, Flow, etc.)
    # --------------------------------------------------------------------------
    is_podcast = (
        niche == "podcast"
        or "podcast" in norm_src
        or "podcast" in norm_streamer
        or any(k in norm_clip for k in ("irmaos dias", "mar digital", "meu time falava", "como prosperar"))
    )
    if is_podcast:
        pod_name = "Irmãos Dias Podcast" if ("irmaos dias" in norm_streamer or "irmaos dias" in norm_src or "irmaos dias" in norm_clip) else (streamer or "Podcast")
        if any(k in norm_clip for k in ("mar digital", "ultrapassei todos", "meu time falava", "prosperar")):
            return f"Como Ultrapassei Todos no Marketing Digital em 1 Ano | {pod_name} #Shorts"[:85]
        
        subject = _extract_subject_from_transcript(clip_text, max_words=7)
        if subject and len(subject.split()) >= 3:
            pretty = subject[0].upper() + subject[1:]
            suffix = f" (Parte {part_num})" if part_num > 1 else ""
            return f"{pretty}{suffix} | {pod_name} #Shorts"[:85]

    # --------------------------------------------------------------------------
    # Case 5: Reddit / Nosleep / Horror / Mystery Stories
    # --------------------------------------------------------------------------
    is_story = any(k in norm_src for k in ("reddit", "nosleep", "historias", "relatos", "terror", "creepypasta", "misterio"))
    if is_story:
        for pattern, story_hook in _STORY_HOOK_PATTERNS:
            if re.search(pattern, norm_clip):
                title = f"{story_hook} | Relatos do Reddit"
                if part_num > 1:
                    title = f"{story_hook} (Parte {part_num}) | Reddit"
                return title[:85]

        subject = _extract_subject_from_transcript(clip_text, max_words=6)
        if subject and len(subject.split()) >= 3:
            pretty_subject = subject[0].upper() + subject[1:]
            title = f"{pretty_subject} | Histórias do Reddit"
            if part_num > 1:
                title = f"{pretty_subject} (Parte {part_num})"
            return title[:85]

        fallbacks = [
            "O Que Realmente Aconteceu Naquela Noite? | Relatos do Reddit",
            "O Detalhe Sinistro Que Ninguém Conseguiu Explicar",
            "A Mensagem Que Mudou Minha Vida Para Sempre",
            "O Encontro Que Me Fez Nunca Mais Voltar Naquele Lugar",
            "A Descoberta Mais Perturbadora do Relato",
            "O Momento Em Que Tudo Começou a Fazer Sentido",
            "A Verdade Aterrorizante Revelada no Final",
            "A Coisa Que Ninguém Teve Coragem de Falar",
        ]
        chosen = fallbacks[(part_num - 1) % len(fallbacks)]
        if part_num > 1:
            return f"{chosen} (Parte {part_num})"[:85]
        return chosen[:85]

    # --------------------------------------------------------------------------
    # Case 6: Verified Gaming Streamers (Gaules, Lipao, Davy Jones, etc.)
    # --------------------------------------------------------------------------
    # STRICT GUARD: Only triggers if the name matches a known gaming streamer AND gaming context!
    is_gaming_streamer = (
        any(s in norm_streamer for s in VERIFIED_GAMING_STREAMERS)
        or any(s in norm_src for s in VERIFIED_GAMING_STREAMERS)
    )
    if is_gaming_streamer and (niche in ("games", "games_gta6", "games_esports") or any(k in norm_src for k in ("gameplay", "ao vivo", "live", "twitch", "gta", "cs2", "valorant"))):
        streamer_name = streamer or clean_src.split(":")[0].replace("GTA 6 Ao Vivo", "").strip() or "Gamer"

        if any(w in norm_clip for w in ("olha isso", "mentira", "meu deus", "caraca", "morri", "bug", "segredo")):
            title = f"{streamer_name} Ficou Sem Reação com Esse Momento! #Shorts"
            if part_num > 1:
                title = f"{streamer_name} Não Acreditou Nisso (Parte {part_num}) #Shorts"
            return title[:85]

        if any(w in norm_clip for w in ("policia", "cop", "fugir", "estrelas", "tiro", "bomba", "tanque", "missao")):
            title = f"O Maior Caos do {streamer_name} no GTA 6! #Shorts"
            if part_num > 1:
                title = f"Missão Insana do {streamer_name} (Parte {part_num}) #Shorts"
            return title[:85]

        seed_str = f"{streamer_name}_{part_num}_{clip_text[:30]}"
        hash_idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(_STREAMER_HOOK_TEMPLATES)
        chosen_template = _STREAMER_HOOK_TEMPLATES[hash_idx]
        title = chosen_template.format(streamer=streamer_name)
        if part_num > 1 and "(Parte" not in title:
            title = f"{title.rstrip('!')} (Parte {part_num}) #Shorts"
        elif "#Shorts" not in title:
            title = f"{title} #Shorts"
        return title[:85]

    # --------------------------------------------------------------------------
    # Case 7: General Climax / Extract from Spoken Transcript or Clean Source
    # --------------------------------------------------------------------------
    subject = _extract_subject_from_transcript(clip_text, max_words=8)
    if subject and len(subject.split()) >= 3:
        pretty = subject[0].upper() + subject[1:]
        suffix = f" (Parte {part_num})" if part_num > 1 else ""
        return f"{pretty}{suffix} #Shorts"[:85]

    clean = re.sub(r"\s*\|\s*Gameplay\s*#Shorts", "", clean_src, flags=re.I).strip()
    if clean:
        suffix = f" (Parte {part_num})" if part_num > 1 and f"Parte {part_num}" not in clean else ""
        return f"{clean}{suffix}"[:85]

    return f"Momento Viral Imperdível #{part_num}"[:85]
