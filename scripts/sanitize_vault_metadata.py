#!/usr/bin/env python3
"""Batch Metadata Sanitizer for AutoShorts Vault.

Fixes:
1. Truncated titles ending in dangling prepositions/conjunctions (de, em, com, que, e, ou, :).
2. Captions polluted with external YouTube links, scraping disclaimers, and 'se inscreva' talk.
3. Injects native platform micro-CTAs that boost shares and saves.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


TRAILING_PREP_REGEX = re.compile(
    r"\s+\b(em|com|de|que|para|no|na|e|ou|da|do|dos|das|se|um|uma|os|as|por|ao|aos|sobre)\s*$",
    re.IGNORECASE,
)

TRAILING_PUNCT_REGEX = re.compile(r"[,:;\-\'\"]\s*$")

SPECIFIC_TITLE_FIXES = {
    "11 de": "11 de Setembro",
    "testemunha de": "Testemunha de Jeová",
    "mandou um": "mandou mensagem",
    "dia 17 de": "dia 17",
    "veja como eles": "veja como funcionam",
    "negociações e que": "negociações",
    "presidencial do Haiti em": "presidencial do Haiti",
    "eleição presidencial da França com": "eleição presidencial da França",
    "controle de uma área": "controle de área estratégica",
    "refém de Senado": "refém do Senado",
    "manifestar": "manifestar'",
    "Como Treinar o Seu": "Como Treinar o Seu Dragão",
    "Soluço e Banguela se tornam melhores amigos | Como": "Soluço e Banguela se tornam melhores amigos",
}

NICHE_CLEAN_CTA = {
    "entretenimento_animes": "Qual o seu personagem favorito nessa cena? Comenta aí e segue para mais cortes dublados!",
    "noticias_mundiais": "Qual a sua opinião sobre esse caso? Deixe nos comentários e segue para acompanhar os fatos.",
    "podcast": "Salva esse corte para não esquecer e manda para quem precisa ouvir isso hoje!",
    "financas": "Salva para consultar depois e compartilha com quem quer evoluir financeiramente!",
    "desenvolvimento_pessoal": "Salva esse vídeo para rever depois e segue para manter a disciplina diária!",
    "concursos": "Salva essa dica de estudo e manda para o seu parceiro de concurso!",
    "games_gta6": "Qual a sua expectativa para esse momento? Deixe nos comentários e segue para mais clipes!",
}


def sanitize_title(title: str) -> str:
    if not title:
        return ""

    t = title.strip()

    # Split pipe suffix if present (e.g. | Mundo Hoje)
    if " | " in t:
        parts = t.split(" | ", 1)
        main_part = parts[0].strip()
        channel_tag = parts[1].strip()
    elif "|" in t:
        parts = t.split("|", 1)
        main_part = parts[0].strip()
        channel_tag = parts[1].strip()
    else:
        main_part = t
        channel_tag = ""

    # Clean truncated channel tag (e.g. "Mund", "Mundo H", "")
    if channel_tag in {"Mund", "Mundo H", "Mundo", "Mun", "M"}:
        channel_tag = "Mundo Hoje"

    # Clean specific known truncation patterns
    for bad_fragment, fix in SPECIFIC_TITLE_FIXES.items():
        if main_part.endswith(bad_fragment):
            main_part = main_part[: -len(bad_fragment)] + fix
            break

    # Strip any dangling prepositions (up to 3 passes)
    for _ in range(3):
        main_part = TRAILING_PREP_REGEX.sub("", main_part).strip()
        main_part = TRAILING_PUNCT_REGEX.sub("", main_part).strip()

    # Clean clean up doubled dashes or weird pipes in channel tag
    channel_tag = re.sub(r"^[—\-\s]+", "", channel_tag).strip()
    channel_tag = TRAILING_PUNCT_REGEX.sub("", channel_tag).strip()

    # Clean unclosed quotes in main_part if it started with a quote
    if main_part.startswith("'") and not main_part.endswith("'"):
        main_part = main_part + "'"
    if main_part.startswith('"') and not main_part.endswith('"'):
        main_part = main_part + '"'

    if channel_tag and channel_tag not in {"—", "-"}:
        final_t = f"{main_part} | {channel_tag}"
    else:
        final_t = main_part

    # Ensure clean spacing
    return re.sub(r"\s+", " ", final_t).strip()


def sanitize_caption(caption: str, title: str, niche: str = "geral") -> str:
    if not caption:
        return title

    c = caption

    # 1. Strip external URLs
    c = re.sub(r"https?://\S+", "", c, flags=re.IGNORECASE)
    c = re.sub(r"Fonte\s*(?:original|/\s*Referencia).*?(?=\n\n|\Z)", "", c, flags=re.IGNORECASE | re.DOTALL)
    c = re.sub(r"Video original:.*?(?=\n\n|\Z)", "", c, flags=re.IGNORECASE | re.DOTALL)
    c = re.sub(r"Qual a sua teoria sobre essa cena\?.*?(?=\n\n|\Z)", "", c, flags=re.IGNORECASE | re.DOTALL)
    c = re.sub(r"Deixe nos comentarios e se inscreva!?", "", c, flags=re.IGNORECASE)
    c = re.sub(r"Comenta sua opiniao ai embaixo!?", "", c, flags=re.IGNORECASE)
    c = re.sub(r"Comenta sua opiniao e siga o canal.*?(?=\n\n|\Z)", "", c, flags=re.IGNORECASE)

    # Strip any previously injected CTAs to prevent repetition
    for cta_text in NICHE_CLEAN_CTA.values():
        c = c.replace(cta_text, "")

    # 3. Clean multiple blank lines
    c = re.sub(r"\n{3,}", "\n\n", c).strip()

    # 4. Extract existing hashtags
    hashtags = re.findall(r"#\w+", c)
    text_without_tags = re.sub(r"#\w+", "", c).strip()

    # 5. Native Micro-CTA
    native_cta = NICHE_CLEAN_CTA.get(niche, "Comenta sua opinião aí embaixo e segue para acompanhar os próximos cortes!")

    # Format final clean caption without duplicate lines
    clean_parts: List[str] = []
    seen_blocks = set()

    for p in [text_without_tags, native_cta]:
        norm = p.strip()
        if norm and norm.lower() not in seen_blocks:
            clean_parts.append(norm)
            seen_blocks.add(norm.lower())

    # Curate high-engagement hashtags (max 5)
    curated_tags: List[str] = []
    for h in hashtags:
        lh = h.lower()
        if lh not in {"#shorts", "#fyp", "#viral", "#atualidades"}:
            if h not in curated_tags:
                curated_tags.append(h)
    if "#cortes" not in curated_tags:
        curated_tags.append("#cortes")
    if "#viral" not in curated_tags:
        curated_tags.append("#viral")
    if "#fyp" not in curated_tags:
        curated_tags.append("#fyp")

    clean_parts.append(" ".join(curated_tags[:5]))

    # Dedupe final consecutive lines
    final_text = "\n\n".join(clean_parts)
    return re.sub(r"\n{3,}", "\n\n", final_text).strip()


def run_vault_sanitization(output_dir: str | Path) -> Dict[str, int]:
    out_path = Path(output_dir)
    files = list(out_path.glob("*.publish.json"))
    stats = {"total": len(files), "titles_fixed": 0, "captions_fixed": 0}

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            orig_title = data.get("title", "")
            orig_caption = data.get("caption", "")
            niche = data.get("niche", "geral")

            new_title = sanitize_title(orig_title)
            new_caption = sanitize_caption(orig_caption, new_title, niche=niche)

            changed = False
            if new_title != orig_title:
                data["title"] = new_title
                stats["titles_fixed"] += 1
                changed = True

            if new_caption != orig_caption:
                data["caption"] = new_caption
                stats["captions_fixed"] += 1
                changed = True

            if changed:
                with open(f, "w", encoding="utf-8") as fp:
                    json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error processing {f.name}: {e}", file=sys.stderr)

    return stats


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    print(f"Running vault sanitization on: {target_dir}")
    res = run_vault_sanitization(target_dir)
    print(f"Sanitization complete: {res}")
