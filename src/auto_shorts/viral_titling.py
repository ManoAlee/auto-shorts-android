"""Unified Viral Titling & Semantic Hook Synthesis Engine.

Solves repetitive, generic, and mismatched titles across:
1. Live Stream Slices (Gaules, LipaoGamer, Davy Jones, xQc, etc.)
2. Story & Reddit Narratives (r/nosleep, creepypasta, mysteries)
3. World & Breaking News (Fixes category mismatch: biology vs economy, sports vs tech)
4. Anime Highlights (Epic battles, character reveals)
5. General Educational / Tech Shorts

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
    
    Prevents category drift (e.g., frogs/biology classified as economy, sports as tech).
    """
    blob = f"{title} {summary} {hint_category}".lower()
    norm = _clean_alnum_text(blob)
    title_norm = _clean_alnum_text(title)

    # 1. Sports (Carlos Alcaraz, tennis, football, clubs, championships)
    sports_kw = [
        "alcaraz", "zverev", "tenis", "tenista", "atp", "wimbledon", "roland garros",
        "futebol", "neymar", "flamengo", "palmeiras", "corinthians", "sao paulo",
        "goleada", "campeonato", "libertadores", "champions league", "brasileirao",
        "gol", "tecnico", "treinador", "nba", "basquete", "volei", "ufc", "boxe",
        "formula 1", "f1", "corrida", "podio", "grand slam"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in sports_kw):
        return "esportes"

    # 2. Science, Biology, Nature & Space (frogs, new species, NASA, biology, health)
    science_kw = [
        "perereca", "sapo", "especie", "descoberta", "cientistas", "pesquisadores",
        "biologia", "biologos", "fauna", "flora", "animal", "animais", "fossil",
        "dinossauro", "arqueologia", "dna", "genetica", "vacina", "cancer", "medicina",
        "amazonia", "biodiversidade", "extincao", "ecossistema", "nasa", "spacex",
        "james webb", "telescopio", "astronomia", "planeta", "marte", "lua", "saturno",
        "asteroide", "meteoro", "galaxia", "buraco negro", "fisica quantica"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in science_kw):
        return "ciencia_natureza"

    # 3. Games & GTA 6
    games_kw = [
        "gta", "gta 6", "rockstar", "playstation", "ps5", "xbox", "nintendo",
        "zelda", "mario", "fortnite", "valorant", "counter strike", "cs2",
        "gameplay", "streamer", "gamer", "jogos", "jogo", "game"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in games_kw):
        return "games"

    # 4. Tech & Artificial Intelligence (Apple, Google, Nvidia, smartphones, apps)
    tech_kw = [
        "inteligencia artificial", "openai", "chatgpt", "deepseek", "nvidia",
        "hardware", "software", "smartphone", "galaxy s26", "iphone", "samsung",
        "apple", "google", "microsoft", "one ui", "app lock", "biometria", "hacker",
        "ciberataque", "vulnerabilidade", "chip", "semicondutor", "algoritmo", "ia"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in tech_kw):
        return "tech_ia"

    # 5. Economy & Finance (Only true financial/economic indicators, not biology/sports!)
    econ_kw = [
        "dolar", "inflacao", "selic", "taxa de juros", "banco central", "bolsa de valores",
        "ibovespa", "pib", "dividendo", "renda fixa", "tesouro direto", "mercado financeiro",
        "copom", "reforma tributaria", "deficit", "superavit"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", title_norm) for k in econ_kw):
        return "economia"

    # 6. Humor & Memes
    humor_kw = ["meme", "memes", "engracado", "comedia", "zoeira", "shitpost", "casimiro", "defante"]
    if any(re.search(rf"\b{re.escape(k)}\b", norm) for k in humor_kw):
        return "humor_memes"

    # 7. Fallback to hint_category or world
    if hint_category in ("games", "tech_ia", "economia", "ciencia_natureza", "esportes", "humor_memes"):
        return hint_category
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
        # Take first 4-6 words of the sentence around the key content
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
    """Generate a captivating, viral, context-specific title that accurately reflects the video.
    
    Eliminates repetitive formulas like '{Source} (Parte N) | Gameplay #Shorts'.
    """
    clean_src = AntiSlopHumanizer.clean(source_title).strip()
    streamer = streamer_or_speaker.strip()
    norm_src = _clean_alnum_text(clean_src)
    norm_clip = _clean_alnum_text(clip_text)
    
    # --------------------------------------------------------------------------
    # Case 1: News Article / Breaking Fact with Category Suffix
    # --------------------------------------------------------------------------
    if " | Plantão " in clean_src or " | Mundo Hoje" in clean_src or niche in ("noticias_mundiais", "tech_ia", "financas", "economia"):
        cat = detect_accurate_category(clean_src, summary=clip_text)
        suffix_map = {
            "tech_ia": " | Plantão Tech",
            "economia": " | Plantão Economia",
            "ciencia_natureza": " | Ciência & Natureza",
            "esportes": " | Plantão Esportes",
            "games": " | Plantão Games",
            "humor_memes": " | Plantão Humor",
            "mundo": " | Mundo Hoje",
        }
        # Strip old incorrect suffix
        base_headline = re.split(r"\s*\|\s*(?:Plantão|Mundo|Ciência|Notícias).*", clean_src, flags=re.I)[0].strip()
        correct_suffix = suffix_map.get(cat, " | Mundo Hoje")
        max_base = max(30, 85 - len(correct_suffix))
        if len(base_headline) > max_base:
            base_headline = base_headline[:max_base].rsplit(" ", 1)[0]
        return f"{base_headline}{correct_suffix}"

    # --------------------------------------------------------------------------
    # Case 2: Reddit / Nosleep / Horror / Mystery Stories
    # --------------------------------------------------------------------------
    is_story = any(k in norm_src for k in ("reddit", "nosleep", "historias", "relatos", "terror", "creepypasta", "misterio"))
    if is_story:
        # Check if transcript matches any specific story mystery trope
        for pattern, story_hook in _STORY_HOOK_PATTERNS:
            if re.search(pattern, norm_clip):
                title = f"{story_hook} | Relatos do Reddit"
                if part_num > 1:
                    title = f"{story_hook} (Parte {part_num}) | Reddit"
                return title[:85]

        # Extract salient phrase from transcript
        subject = _extract_subject_from_transcript(clip_text, max_words=6)
        if subject and len(subject.split()) >= 3:
            pretty_subject = subject[0].upper() + subject[1:]
            title = f"{pretty_subject} | Histórias do Reddit"
            if part_num > 1:
                title = f"{pretty_subject} (Parte {part_num})"
            return title[:85]

        # Diverse non-repetitive fallback based on part number
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
    # Case 3: Streamer Live Gameplay (Gaules, LipaoGamer, Davy Jones, xQc, etc.)
    # --------------------------------------------------------------------------
    if streamer or any(k in norm_src for k in ("gaules", "lipao", "davy", "xqc", "alanzoka", "coringa", "nobru")):
        streamer_name = streamer or clean_src.split(":")[0].replace("GTA 6 Ao Vivo", "").strip() or "Gamer"
        
        # Check transcript for strong streamer cues
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

        # Use deterministic hash of clip_text or part_num to guarantee non-repetitive viral title
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
    # Case 4: Anime Scenes (Cenas Dubladas / Batalhas Épicas)
    # --------------------------------------------------------------------------
    if "anime" in niche.lower() or any(k in norm_src for k in ("anime", "dublado", "cena epica", "naruto", "bleach", "jujutsu")):
        # Extract anime title
        anime_title = clean_src.split("—")[0].split("-")[0].strip()
        if anime_title and len(anime_title) > 3:
            anime_clean = anime_title[:30].strip()
            anime_hooks = [
                f"{anime_clean} — A Cena Mais Épica de Todas!",
                f"{anime_clean} — O Poder Que Chocou Todo Mundo!",
                f"{anime_clean} — O Momento Mais Tenso da Batalha!",
                f"{anime_clean} — Ninguém Esperava Por Esse Golpe!",
            ]
            chosen = anime_hooks[(part_num - 1) % len(anime_hooks)]
            if part_num > 1:
                chosen = f"{chosen.rstrip('!')} (Parte {part_num})!"
            return chosen[:85]

    # --------------------------------------------------------------------------
    # Case 5: General Climax / Extract from Transcript
    # --------------------------------------------------------------------------
    subject = _extract_subject_from_transcript(clip_text, max_words=8)
    if subject and len(subject.split()) >= 3:
        pretty = subject[0].upper() + subject[1:]
        suffix = f" (Parte {part_num})" if part_num > 1 else ""
        return f"{pretty}{suffix}"[:85]

    # Fallback: clean current title or source title without redundant part repetition
    clean = re.sub(r"\s*\|\s*Gameplay\s*#Shorts", "", clean_src, flags=re.I).strip()
    if clean:
        suffix = f" (Parte {part_num})" if part_num > 1 and f"Parte {part_num}" not in clean else ""
        return f"{clean}{suffix}"[:85]

    return f"Momento Viral Imperdível #{part_num}"[:85]
