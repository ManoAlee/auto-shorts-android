"""Cross-Platform Adaptation Engine for Instagram Reels, TikTok, and YouTube Shorts.

Distilled from research on:
- github.com/Jakeschincariol/instagram-agent-skill (125-char caption truncation, 5-tag cap, safe zones)
- github.com/harry0703/MoneyPrinterTurbo (word sync & audio ducking)
- github.com/gabuldev/auto-edit-video & agent-video-editor (pacing, retention loops)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .viral_intelligence import (
    AntiSlopHumanizer,
    build_zeigarnik_loop_cta,
    score_hook,
)

# Platform specs & limits
IG_TRUNCATE_CHARS = 125
IG_MAX_TAGS = 5
IG_MAX_CHARS = 2200

TIKTOK_MAX_TITLE = 90
TIKTOK_MAX_TAGS = 4

YT_SHORTS_MAX_TITLE = 70
YT_SHORTS_MAX_TAGS = 3

PLATFORM_SAFE_ZONES = {
    "instagram_reels": {
        "top_margin_px": 120,      # Profile & header icons
        "bottom_margin_px": 240,   # Audio handle, caption & CTA
        "right_margin_px": 90,     # Like, comment, share icons
        "aspect_ratio": "9:16",
    },
    "tiktok": {
        "top_margin_px": 100,      # Following / For You tabs
        "bottom_margin_px": 260,   # Username, description, sound
        "right_margin_px": 100,    # Like, bookmark, comment rail
        "aspect_ratio": "9:16",
    },
    "youtube_shorts": {
        "top_margin_px": 80,       # Channel logo, search
        "bottom_margin_px": 220,   # Sound title, channel handle
        "right_margin_px": 90,     # Dislike, like, comments
        "aspect_ratio": "9:16",
    },
}

NICHE_TAG_POOLS: Dict[str, Dict[str, List[str]]] = {
    "animes": {
        "instagram": ["#AnimeBrasil", "#OtakuBR", "#CenasDeAnime", "#AnimeDublado", "#Shonen"],
        "tiktok": ["#AnimeBrasil", "#OtakuBR", "#AnimeDublado", "#FYPAnime"],
        "youtube": ["#Shorts", "#AnimeBrasil", "#AnimeDublado"],
    },
    "noticias_mundiais": {
        "instagram": ["#Noticias", "#MundoHoje", "#Geopolitica", "#Jornalismo", "#Atualidades"],
        "tiktok": ["#Noticias", "#MundoHoje", "#TikTokNoticias", "#Atualidades"],
        "youtube": ["#Shorts", "#Noticias", "#MundoHoje"],
    },
    "tech_ia": {
        "instagram": ["#InteligenciaArtificial", "#Tecnologia", "#Inovacao", "#DevBR", "#Futuro"],
        "tiktok": ["#Tecnologia", "#InteligenciaArtificial", "#TechBR", "#DicasTech"],
        "youtube": ["#Shorts", "#Tecnologia", "#InteligenciaArtificial"],
    },
    "games": {
        "instagram": ["#GamerBrasil", "#GTA6", "#GamesBR", "#GameplayBR", "#ClipsGamer"],
        "tiktok": ["#GamerBrasil", "#GTA6", "#Gaming", "#Clipada"],
        "youtube": ["#Shorts", "#Gaming", "#GTA6"],
    },
    "geral": {
        "instagram": ["#Curiosidades", "#Brasil", "#Fatos", "#Conhecimento", "#ViralBR"],
        "tiktok": ["#Curiosidades", "#Fatos", "#ViralBR", "#AprendaNoTikTok"],
        "youtube": ["#Shorts", "#Curiosidades", "#Fatos"],
    },
}


def _clean_visible_hook(first_line: str, max_chars: int = IG_TRUNCATE_CHARS) -> str:
    """Ensure the very first sentence before the Instagram '... mais' fold is complete and engaging."""
    clean = re.sub(r"\s+", " ", first_line or "").strip()
    if len(clean) <= max_chars:
        return clean
    # Break at last sentence boundary or space before max_chars
    punct_cut = max(clean[:max_chars].rfind("."), clean[:max_chars].rfind("!"), clean[:max_chars].rfind("?"))
    if punct_cut > 40:
        return clean[:punct_cut + 1]
    space_cut = clean[:max_chars].rfind(" ")
    if space_cut > 35:
        return clean[:space_cut] + "..."
    return clean[:max_chars]


def build_instagram_caption(
    title: str,
    body_text: str,
    niche: str = "geral",
    source_attribution: str = "",
    custom_cta: str = "",
) -> Dict[str, Any]:
    """Generate an Instagram-native caption compliant with algorithm best practices.
    
    - First line is punchy & complete before the 125-char fold.
    - Exactly 4-5 targeted hashtags (Instagram creators rule: max 5).
    - Clear engagement CTA.
    """
    humanizer = AntiSlopHumanizer()
    clean_title = humanizer.clean(title).strip()
    clean_body = humanizer.clean(body_text).strip()

    # Lead hook
    visible_lead = _clean_visible_hook(clean_title, max_chars=120)
    
    # Body with spacing
    body_lines: List[str] = [visible_lead, ""]
    if clean_body and clean_body.lower() != clean_title.lower():
        body_lines.append(clean_body)
        body_lines.append("")

    if source_attribution:
        body_lines.append(f"📌 Fonte / Referência: {source_attribution}")
        body_lines.append("")

    # CTA
    cta = custom_cta or build_zeigarnik_loop_cta(niche)
    body_lines.append(f"💬 {cta}")
    body_lines.append("")

    # Hashtags (capped at 5 targeted tags)
    tags_pool = NICHE_TAG_POOLS.get(niche, NICHE_TAG_POOLS["geral"])["instagram"]
    selected_tags = tags_pool[:IG_MAX_TAGS]
    body_lines.append(" ".join(selected_tags))

    full_caption = "\n".join(body_lines).strip()
    return {
        "caption": full_caption[:IG_MAX_CHARS],
        "visible_lead": visible_lead,
        "hashtags": selected_tags,
        "tags_count": len(selected_tags),
        "is_within_limit": len(full_caption) <= IG_MAX_CHARS,
    }


def build_tiktok_metadata(
    title: str,
    niche: str = "geral",
    hook_banner: str = "",
    source_attribution: str = "",
) -> Dict[str, Any]:
    """Generate high-velocity TikTok metadata.
    
    - Punchy title banner in caps.
    - Compact caption under 150 chars with 3-4 trending tags.
    """
    humanizer = AntiSlopHumanizer()
    clean_title = humanizer.clean(title).strip()
    
    # Banner
    banner = hook_banner.strip().upper() if hook_banner else clean_title[:32].upper()
    
    # TikTok caption (short, high readability)
    tags_pool = NICHE_TAG_POOLS.get(niche, NICHE_TAG_POOLS["geral"])["tiktok"][:TIKTOK_MAX_TAGS]
    tags_str = " ".join(tags_pool)
    
    snippet = clean_title[:75].rsplit(" ", 1)[0] if len(clean_title) > 75 else clean_title
    caption = f"{snippet} {tags_str}".strip()
    
    return {
        "title": clean_title[:TIKTOK_MAX_TITLE],
        "hook_banner": banner[:32],
        "caption": caption[:180],
        "hashtags": tags_pool,
    }


def build_youtube_shorts_metadata(
    title: str,
    niche: str = "geral",
    channel_name: str = "AleplayTV",
    source_url: str = "",
) -> Dict[str, Any]:
    """Generate YouTube Shorts metadata optimized for search and CTR.
    
    - Title < 70 chars with #Shorts.
    - Description with source link and subscribe call.
    """
    humanizer = AntiSlopHumanizer()
    clean_title = humanizer.clean(title).strip()
    
    # Ensure title stays under 70 characters including suffix
    base_title = clean_title[:52].rsplit(" ", 1)[0] if len(clean_title) > 52 else clean_title
    yt_title = f"{base_title} | {channel_name} #Shorts"[:YT_SHORTS_MAX_TITLE]

    tags_pool = NICHE_TAG_POOLS.get(niche, NICHE_TAG_POOLS["geral"])["youtube"][:YT_SHORTS_MAX_TAGS]

    desc_lines = [
        clean_title,
        "",
        f"Inscreva-se no canal {channel_name} para mais conteúdos diários!",
    ]
    if source_url:
        desc_lines.append(f"Vídeo de referência: {source_url}")
    desc_lines.append("")
    desc_lines.append(" ".join(tags_pool))

    return {
        "title": yt_title,
        "description": "\n".join(desc_lines).strip(),
        "hashtags": tags_pool,
    }


def adapt_short_for_all_platforms(
    title: str,
    body_text: str,
    niche: str = "geral",
    hook_banner: str = "",
    source_attribution: str = "",
    source_url: str = "",
    channel_name: str = "AleplayTV",
) -> Dict[str, Any]:
    """Omni-channel packaging engine: produces 100% compliant bundles for IG, TikTok and YouTube."""
    ig = build_instagram_caption(
        title=title,
        body_text=body_text,
        niche=niche,
        source_attribution=source_attribution,
    )
    tiktok = build_tiktok_metadata(
        title=title,
        niche=niche,
        hook_banner=hook_banner,
        source_attribution=source_attribution,
    )
    yt = build_youtube_shorts_metadata(
        title=title,
        niche=niche,
        channel_name=channel_name,
        source_url=source_url,
    )
    
    return {
        "niche": niche,
        "safe_zones": PLATFORM_SAFE_ZONES,
        "instagram": ig,
        "tiktok": tiktok,
        "youtube": yt,
    }
