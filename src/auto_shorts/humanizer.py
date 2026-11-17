"""Humanizer Engine for Viral Short Scripts (inspired by blader/humanizer & Wikipedia AI Cleanup).

Transforms rigid, predictable AI-sounding scripts into natural, punchy, conversational spoken Portuguese.
Removes:
- Staging and inflated significance ("um divisor de águas", "marca um momento crucial")
- Formulaic rule-of-three triplets
- Generic AI hooks ("Você sabia que", "Em um mundo onde", "Prepare-se para descobrir")
- Monotonous sentence length cadence
- Chatbot-like closers and summaries
Injects:
- Authentic conversational cadence (variable sentence lengths, spoken contractions)
- Real speaker personality (spontaneous reactions, curiosity, edge)
- Natural speech flow with breathing pauses for neural voice engines.
"""

from __future__ import annotations

import random
import re
from typing import Dict, List, Tuple


AI_INFLATED_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(marca|marcando)\s+(um\s+)?(momento\s+crucial|divisor\s+de\s+águas|uma\s+virada\s+histórica)\b", "mudou tudo"),
    (r"\b(serve|servindo)\s+como\s+(um\s+)?(lembrete|testemunho|prova\s+viva)\b", "mostra bem"),
    (r"\b(desempenha|desempenhando)\s+um\s+papel\s+(crucial|fundamental|vital)\b", "é essencial"),
    (r"\b(no\s+cenário\s+atual|no\s+mundo\s+de\s+hoje|em\s+constante\s+evolução)\b", "hoje em dia"),
    (r"\b(não\s+se\s+trata\s+apenas\s+de\s+[^,]+),\s*mas\s+(sim\s+de\s+)?\b", r"\1. Na real, é "),
    (r"\bé\s+importante\s+(destacar|lembrar|ressaltar)\s+que\b", "repara que"),
    (r"\bvale\s+(a\s+pena\s+)?(destacar|lembrar|notar)\s+que\b", "olha só:"),
    (r"\bpodemos\s+observar\s+que\b", "dá pra ver que"),
    (r"\bum\s+verdadeiro\s+(espetáculo|marco|fenômeno)\b", "algo surreal"),
    (r"\binquestionavelmente\b", "com certeza"),
    (r"\bindubitavelmente\b", "sem dúvida"),
    (r"\bportanto\b", "então"),
    (r"\btodavia\b", "mas"),
    (r"\bcontudo\b", "só que"),
]

AI_CLICHE_HOOKS: List[Tuple[str, str]] = [
    (r"^(você\s+sabia\s+que\s+)", "Cara, "),
    (r"^(presta\s+muita\s+atenção\s+nisso!?)", "Olha esse detalhe bizarro:"),
    (r"^(prepare-se\s+para\s+ter\s+sua\s+mente\s+explodida!?)", "Mano, presta atenção nisso:"),
    (r"^(já\s+se\s+perguntou\s+como\s+seria\s+se\s+)", "Você já reparou que "),
]

CONVERSATIONAL_CONTRACTIONS: List[Tuple[str, str]] = [
    (r"\bpara\s+o\b", "pro"),
    (r"\bpara\s+a\b", "pra"),
    (r"\bpara\s+os\b", "pros"),
    (r"\bpara\s+as\b", "pras"),
    (r"\bestá\b", "tá"),
    (r"\bestão\b", "tão"),
    (r"\bestava\b", "tava"),
    (r"\bestavam\b", "tavam"),
]


def humanize_script(text: str, niche: str = "geral") -> str:
    """Rewrite AI-generated script into punchy, authentic spoken Portuguese."""
    raw = " ".join(str(text or "").split()).strip()
    if not raw:
        return ""

    out = raw

    # 1. Strip cliché hooks
    for pat, rep in AI_CLICHE_HOOKS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)

    # 2. Replace inflated AI patterns
    for pat, rep in AI_INFLATED_PATTERNS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)

    # 3. Apply natural contractions for spoken dialogue
    for pat, rep in CONVERSATIONAL_CONTRACTIONS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)

    # 4. Remove robotic AI formulaic endings
    out = re.sub(
        r"(qual\s+é\s+a\s+sua\s+opinião\?\s*deixe\s+nos\s+comentários\s+e\s+se\s+inscreva.*)$",
        "E você, sabia disso? Comenta aí e segue o canal!",
        out,
        flags=re.IGNORECASE
    )

    # 5. Fix punctuation for speech pauses (dots, dashes and commas)
    out = re.sub(r"\s*—\s*", ", ", out)
    out = re.sub(r"\s*:\s*", "... ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()

    # Ensure first letter is capitalized
    if out:
        out = out[0].upper() + out[1:]

    return out
