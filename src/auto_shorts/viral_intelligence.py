"""Viral Intelligence, Psychological Retention, and Anti-Slop Engine.

Synthesizes the core retention molecules from:
1. instagram-agent-skill (26 Hook Formulas, Mathematical HookScorer, Beat Sheet, Anti-AI Slop Humanizer).
2. MoneyPrinterTurbo (Word-Level subtitle shaping, dynamic audio ducking, fast-pacing transitions).

Specifically engineered to eradicate weak, robotic AI content ("AI slop") and elevate authentic,
high-stakes human/dubbed moments into viral short-form assets.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. ANTI-SLOP & HUMANIZER LEXICON (PT-BR + EN)
# Eliminates robotic AI cliches, invisible Unicode watermarks, and machine fingerprints.
# ==============================================================================

INVISIBLE_CHARS_REGEX = re.compile(
    r"[\u200B\u200C\u200D\u2060\uFEFF\u00AD\u180E\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]"
)

# Stock AI buzzwords that cause users to scroll away in <1s
SLOP_REPLACEMENTS_PT = [
    # Aberturas e preambulos roboticos
    (r"\bno mundo de hoje\b", "hoje"),
    (r"\bno cen[aá]rio atual\b", "hoje"),
    (r"\bvamos mergulhar\b", "veja"),
    (r"\bmergulhe de cabe[cç]a\b", "entenda"),
    (r"\bmergulhe em\b", "olhe"),
    (r"\bdescubra o segredo\b", "a verdade"),
    (r"\bdesbloqueie seu potencial\b", "aprenda isso"),
    (r"\bpotencialize seus resultados\b", "melhore"),
    (r"\bum divisor de [aá]guas\b", "uma virada"),
    (r"\bum testemunho de\b", "a prova de"),
    (r"\b[eé] fundamental destacar que\b", "o detalhe é:"),
    (r"\b[eé] crucial entender\b", "o ponto é:"),
    (r"\bsem sombra de d[uú]vidas?\b", "claramente"),
    (r"\btransforme sua vida\b", "mude isso"),
    (r"\bvamos explorar\b", "olhe"),
    (r"\bcomo todos sabemos\b", ""),
    (r"\bneste v[ií]deo eu vou te mostrar\b", "olhe isso:"),
    (r"\bneste v[ií]deo voc[eê] vai aprender\b", "aqui está:"),
    (r"\bassista at[eé] o final\b", ""),
    (r"\bn[aã]o perca nenhum segundo\b", ""),
    (r"\bdeixe seu like e se inscreva\b", ""),
    (r"\bvoc[eê] n[aã]o vai acreditar no que aconteceu\b", "olha o que aconteceu:"),
    (r"\brevolucion[aá]ri[oa]\b", "pesado"),
    (r"\binovador(a)?\b", "novo"),
    (r"\brobusto\b", "forte"),
    (r"\bperfeito e sem falhas\b", "direto"),
]

SLOP_REPLACEMENTS_EN = [
    (r"\bdelve into\b", "look at"),
    (r"\bdelve\b", "dig into"),
    (r"\bdive deep into\b", "examine"),
    (r"\bdeep dive\b", "breakdown"),
    (r"\bleverage\b", "use"),
    (r"\butilize\b", "use"),
    (r"\bharness\b", "tap into"),
    (r"\bembark on\b", "start"),
    (r"\bfoster\b", "build"),
    (r"\bshowcase\b", "show"),
    (r"\bunlock\b", "get"),
    (r"\belevate\b", "boost"),
    (r"\bgame-changer\b", "major shift"),
    (r"\btestament to\b", "proof of"),
    (r"\bin today's fast-paced world\b", "today"),
    (r"\bin today's world\b", "today"),
    (r"\bstop scrolling\b", "listen:"),
    (r"\bin this video I'm going to show you\b", "here is:"),
    (r"\bwatch until the end\b", ""),
    (r"\byou won't believe what happens next\b", "look at this:"),
]

# ==============================================================================
# 2. 26 VIRAL HOOK FORMULAS (Adapted from instagram-agent-skill/hooks.json)
# Dual-Hook Architecture: Spoken Hook (<2.5s) + On-Screen Punch Hook (max 6 words).
# ==============================================================================

@dataclass(frozen=True)
class HookFormula:
    id: int
    name: str
    spoken_template: str
    on_screen_template: str
    psychological_trigger: str
    pattern_regex: str
    example_pt: str
    on_screen_pt: str


VIRAL_HOOK_FORMULAS: List[HookFormula] = [
    HookFormula(
        id=1,
        name="Cost Confession",
        spoken_template="{Specific cost} é exatamente o que {one mistake} me custou.",
        on_screen_template="{Cost} POR 1 ERRO",
        psychological_trigger="Choque de transparência e perda financeira real.",
        pattern_regex=r"(?:custou|perdi|prejuízo de)\s*(?:R\$|\$)?\s*\d+",
        example_pt="R$ 18.000 foi o que um único erro de contrato me custou.",
        on_screen_pt="ERRO DE R$ 18.000",
    ),
    HookFormula(
        id=2,
        name="Negative Command",
        spoken_template="Pare de {common habit}. Faça {alternative} agora.",
        on_screen_template="PARE DE {HABIT}",
        psychological_trigger="Interrupção agressiva de padrão e imperativo urgente.",
        pattern_regex=r"^(?:pare de|nunca mais|não faça|esqueça)\b",
        example_pt="Pare de postar 3 vezes por dia sem responder comentários.",
        on_screen_pt="PARE DE POSTAR ASSIM",
    ),
    HookFormula(
        id=3,
        name="Nobody Tells You",
        spoken_template="Ninguém te conta que {uncomfortable secret}.",
        on_screen_template="O QUE NINGUÉM TE CONTA",
        psychological_trigger="Quebra de tabu e curiosidade não resolvida.",
        pattern_regex=r"\b(?:ningu[eé]m te conta|ningu[eé]m fala sobre|o segredo que)\b",
        example_pt="Ninguém te conta que os seus primeiros 30 vídeos vão flopar.",
        on_screen_pt="NINGUÉM TE CONTA ISSO",
    ),
    HookFormula(
        id=4,
        name="The Replacement",
        spoken_template="Isso aqui substituiu {expensive alternative} por {fraction of cost}.",
        on_screen_template="{OLD} -> {NEW}",
        psychological_trigger="Assimetria brutal de valor e custo.",
        pattern_regex=r"\b(?:substituiu|troquei|ao inv[eé]s de gastar)\b",
        example_pt="Esse script substituiu um editor que cobrava 2 mil reais por mês.",
        on_screen_pt="R$ 2000 -> ZERO",
    ),
    HookFormula(
        id=5,
        name="Time Collapse",
        spoken_template="Isso levava {long time}. Agora leva {short time}.",
        on_screen_template="{LONG} -> {SHORT}",
        psychological_trigger="Promessa palpável de velocidade e eficiência extrema.",
        pattern_regex=r"\b(?:levava|demorava)\s+\d+.*(?:agora|em)\s+\d+\b",
        example_pt="Editar esse vídeo levava 4 horas. Hoje faço em 30 segundos.",
        on_screen_pt="4 HORAS -> 30 SEG",
    ),
    HookFormula(
        id=6,
        name="The Exception",
        spoken_template="Todo mundo fala para fazer {rule}, menos quando {exception}.",
        on_screen_template="A ÚNICA EXCEÇÃO",
        psychological_trigger="Confronto direto com a sabedoria convencional.",
        pattern_regex=r"\b(?:todo mundo fala|a maioria erra|a grande exce[cç][aã]o)\b",
        example_pt="Todo mundo diz pra acordar às 5 da manhã, mas esquecem desse detalhe.",
        on_screen_pt="O ERRO DAS 5 DA MANHÃ",
    ),
    HookFormula(
        id=7,
        name="High Stakes Showdown",
        spoken_template="Se você errar isso, {catastrophic outcome}.",
        on_screen_template="NUNCA ERRE ISSO",
        psychological_trigger="Aversão à perda e sobrevivência imediata.",
        pattern_regex=r"\b(?:se voc[eê] errar|o maior perigo|destr[uú]i tudo)\b",
        example_pt="Se você errar essa linha, sua conta do Instagram é suspensa em 24h.",
        on_screen_pt="CONTA SUSPENSA EM 24H?",
    ),
    HookFormula(
        id=8,
        name="The Direct Challenge",
        spoken_template="Você tem coragem de {difficult action} por {result}?",
        on_screen_template="VOCÊ TEM CORAGEM?",
        psychological_trigger="Desafio ao ego e provocação pessoal.",
        pattern_regex=r"\b(?:voc[eê] tem coragem|duvido voc[eê]|a maioria n[aã]o aguenta)\b",
        example_pt="Você tem coragem de passar 7 dias sem tocar no celular?",
        on_screen_pt="7 DIAS SEM CELULAR?",
    ),
]


# ==============================================================================
# 3. MATHEMATICAL HOOK SCORER (From hookscore.py)
# Objective 0-100 score across 5 essential virality dimensions.
# ==============================================================================

STAKES_KEYWORDS = {
    # Portugues
    "pare", "nunca", "erro", "erros", "perdi", "perdeu", "perder", "prejuizo", "prejuízo",
    "falhou", "fracasso", "ninguem", "ninguém", "segredo", "perigo", "cuidado", "proibido",
    "destruiu", "destrói", "traição", "guerra", "medo", "pressão", "morte", "risco", "crime",
    # Ingles
    "stop", "never", "wrong", "mistake", "lost", "lose", "cost", "broke", "failed", "nobody",
    "secret", "danger", "warning", "ruined", "destroy", "banned", "illegal", "hidden",
}

CONCRETE_REGEX = re.compile(
    r"(?:R\$|\$|€)?\s?\d+[\d.,]*(?:%|k|m|mil|milhões|segundos?|minutos?|horas?|dias?|anos?|reais|dólares)?\b|"
    r"\b(?:zero|um|dois|três|quatro|cinco|dez|vinte|cem|mil)\b",
    re.IGNORECASE,
)

AUDIENCE_AIM_REGEX = re.compile(
    r"\b(?:voc[eê]|seu|sua|seus|suas|pra voc[eê]|contigo|voc[eê]s|you|your|yours)\b",
    re.IGNORECASE,
)

GREETING_PENALTY_REGEX = re.compile(
    r"^(?:ol[aá]|oi|e a[ií]|fala pessoal|fala galera|bom dia|boa tarde|boa noite|bem-vindos?|hello|hey guys|what's up)\b",
    re.IGNORECASE,
)


@dataclass
class HookScoreResult:
    composite_score: float
    grade: str  # STRONG (>=75), VIABLE (55-74), WEAK (<55)
    length_words: int
    spoken_seconds_est: float
    length_score: float
    concrete_score: float
    stakes_score: float
    front_load_score: float
    audience_aim_score: float
    matched_formula: Optional[str]
    has_greeting_penalty: bool
    suggestions: List[str] = field(default_factory=list)


def score_hook(spoken_text: str, on_screen_text: str = "") -> HookScoreResult:
    """Evaluate opening spoken hook on the 5 local heuristics of viral attention.

    Returns 0-100 composite score. High score indicates video captures attention
    in the critical first 2.5 seconds without preamble or generic fluff.
    """
    clean_spoken = INVISIBLE_CHARS_REGEX.sub("", spoken_text).strip()
    words = re.findall(r"[A-Za-z0-9$%'’\-áéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]+", clean_spoken)
    word_count = len(words)

    # 1. Pacing & Length (165 words per minute average = ~2.75 words/sec)
    spoken_sec = word_count / 2.75 if word_count else 0.0
    if 5 <= word_count <= 12:
        length_score = 100.0
    elif word_count < 5:
        length_score = max(30.0, word_count * 15.0)
    elif word_count <= 18:
        length_score = max(50.0, 100.0 - (word_count - 12) * 8.0)
    else:
        length_score = max(10.0, 50.0 - (word_count - 18) * 5.0)

    # 2. Concrete Markers (numbers, metrics, currency, exact data)
    concrete_matches = CONCRETE_REGEX.findall(clean_spoken)
    if concrete_matches:
        concrete_score = min(100.0, 60.0 + len(concrete_matches) * 20.0)
    else:
        concrete_score = 30.0

    # 3. Emotional / High Stakes Keywords
    lower_words = {w.lower() for w in words}
    stakes_hits = lower_words.intersection(STAKES_KEYWORDS)
    if stakes_hits:
        stakes_score = min(100.0, 50.0 + len(stakes_hits) * 25.0)
    else:
        stakes_score = 25.0

    # 4. Front-Loading (Is the payload in the first 4 words, not buried at the end?)
    first_4_words = " ".join(words[:4]).lower() if len(words) >= 4 else clean_spoken.lower()
    has_front_concrete = bool(CONCRETE_REGEX.search(first_4_words))
    has_front_stakes = any(w in first_4_words for w in STAKES_KEYWORDS)
    if has_front_stakes or has_front_concrete:
        front_load_score = 95.0
    elif any(w in " ".join(words[:6]).lower() for w in STAKES_KEYWORDS):
        front_load_score = 70.0
    else:
        front_load_score = 35.0

    # 5. Audience Aim (Direct address to viewer)
    has_aim = bool(AUDIENCE_AIM_REGEX.search(clean_spoken))
    audience_aim_score = 90.0 if has_aim else 40.0

    # Penalty for robot/preamble greetings
    has_greeting = bool(GREETING_PENALTY_REGEX.search(clean_spoken))

    # Matched formula detection
    matched_formula_name: Optional[str] = None
    for f in VIRAL_HOOK_FORMULAS:
        if re.search(f.pattern_regex, clean_spoken, re.IGNORECASE):
            matched_formula_name = f.name
            break

    # Weighted Composite Score
    composite = (
        length_score * 0.20
        + concrete_score * 0.25
        + stakes_score * 0.25
        + front_load_score * 0.20
        + audience_aim_score * 0.10
    )

    if has_greeting:
        composite = max(10.0, composite - 30.0)

    if on_screen_text:
        on_screen_words = len(on_screen_text.split())
        if 1 <= on_screen_words <= 6:
            composite = min(100.0, composite + 5.0)  # Bonus for sharp on-screen punch

    composite = round(composite, 1)

    if composite >= 75.0:
        grade = "STRONG"
    elif composite >= 55.0:
        grade = "VIABLE"
    else:
        grade = "WEAK"

    suggestions: List[str] = []
    if has_greeting:
        suggestions.append("Corte a saudação inicial ('Olá', 'E aí'). Comece direto na afirmação de choque.")
    if word_count > 14:
        suggestions.append("Gancho muito longo. Reduza para menos de 12 palavras para ser dito em menos de 2.5s.")
    if stakes_score < 50.0:
        suggestions.append("Falta tensão/risco. Adicione uma palavra que coloque algo em jogo (erro, segredo, perigo, nunca).")
    if concrete_score < 50.0:
        suggestions.append("Falta especificidade. Adicione um número real, valor ou medida concreta.")

    return HookScoreResult(
        composite_score=composite,
        grade=grade,
        length_words=word_count,
        spoken_seconds_est=round(spoken_sec, 2),
        length_score=length_score,
        concrete_score=concrete_score,
        stakes_score=stakes_score,
        front_load_score=front_load_score,
        audience_aim_score=audience_aim_score,
        matched_formula=matched_formula_name,
        has_greeting_penalty=has_greeting,
        suggestions=suggestions,
    )


# ==============================================================================
# 4. ANTI-SLOP HUMANIZER
# Cleans generated text and transcript hooks to ensure natural, visceral speech.
# ==============================================================================

class AntiSlopHumanizer:
    """Strips machine artifacts, AI cliches, and generates sharp human tone."""

    @classmethod
    def clean(cls, text: str) -> str:
        """Sanitize text: remove invisible chars, normalize punctuation, replace AI slop."""
        if not text:
            return ""

        # 1. Strip invisible Unicode tags & watermarks
        t = INVISIBLE_CHARS_REGEX.sub("", text)

        # 2. Normalize typographical tells (em-dash to comma, curly quotes)
        t = t.replace("—", ", ").replace("–", "-")
        t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        t = re.sub(r"\s*,\s*", ", ", t)
        t = re.sub(r"\s+", " ", t).strip()

        # 3. Replace Brazilian & English AI cliches
        for pattern, replacement in SLOP_REPLACEMENTS_PT:
            t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)

        for pattern, replacement in SLOP_REPLACEMENTS_EN:
            t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)

        # 4. Clean resulting double punctuation
        t = re.sub(r"([,.!?])\s*[,.]+", r"\1", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def generate_dual_hook(cls, hook_title: str, spoken_first_line: str = "") -> Tuple[str, str]:
        """Generate high-impact (spoken_hook, on_screen_banner) pair following the dual-hook rule.

        Rule: On-screen banner must be 3-6 bold uppercase words, blunt, without punctuation.
        """
        clean_title = cls.clean(hook_title)
        words = clean_title.split()

        # Sharp on-screen banner
        if len(words) > 6:
            # Pick first 5-6 punchiest words
            banner_words = [w for w in words[:6] if w.lower() not in {"um", "uma", "o", "a", "os", "as", "de", "do", "da"}]
            banner = " ".join(banner_words[:5]).upper()
        else:
            banner = " ".join(words).upper()

        banner = re.sub(r"[.,!?:;\"'()]+", "", banner).strip()

        spoken = cls.clean(spoken_first_line) if spoken_first_line else clean_title
        return spoken, banner


# ==============================================================================
# 5. BEAT SHEET PACING & ZEIGARNIK LOOP
# Structures the cut into 5 mandatory psychological retention segments.
# ==============================================================================

@dataclass
class BeatSegment:
    name: str  # HOOK, STAKE, BODY, PAYOFF, LOOP
    start_sec: float
    end_sec: float
    purpose: str


def generate_beat_sheet(total_duration_sec: float) -> List[BeatSegment]:
    """Calculate the 5 psychological retention beats across video duration."""
    dur = max(10.0, total_duration_sec)
    return [
        BeatSegment("HOOK", 0.0, min(2.5, dur * 0.08), "Declaração de choque ou curiosidade imediata."),
        BeatSegment("STAKE", min(2.5, dur * 0.08), min(7.0, dur * 0.22), "Por que isso importa para quem assiste."),
        BeatSegment("BODY", min(7.0, dur * 0.22), max(dur - 4.0, dur * 0.85), "Desenvolvimento veloz com cortes a cada 3s."),
        BeatSegment("PAYOFF", max(dur - 4.0, dur * 0.85), dur - 1.2, "Entrega do que o gancho prometeu."),
        BeatSegment("LOOP", max(0.0, dur - 1.2), dur, "Fechamento aberto (Zeigarnik) que conecta com o início."),
    ]


def build_zeigarnik_loop_cta(first_spoken_phrase: str) -> str:
    """Generate closing line that echoes the opening phrase to induce continuous replay."""
    clean = AntiSlopHumanizer.clean(first_spoken_phrase).lower()
    words = clean.split()
    if not words:
        return "E é por isso que você nunca percebeu isso..."

    key_anchor = words[0] if len(words) == 1 else " ".join(words[:2])
    return f"E foi exatamente assim que começou {key_anchor}..."
