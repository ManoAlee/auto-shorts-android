"""End-to-end SEO audit tests for Web Technical SEO, On-Page SEO, Structured Data, and Video SEO."""

import json
import re

from auto_shorts.analytics_ui import render_analytics_dashboard_html
from auto_shorts.cross_platform_adapter import (
    IG_MAX_TAGS,
    NICHE_TAG_POOLS,
    TIKTOK_MAX_TAGS,
    YT_SHORTS_MAX_TAGS,
    adapt_short_for_all_platforms,
)
from auto_shorts.webapp import render_dashboard_html, render_robots_txt, render_sitemap_xml
from auto_shorts.world_news import _clean_seo_title, _wrap_news_headline


def test_dashboard_onpage_seo_and_structured_data():
    html = render_dashboard_html(canonical_url="https://studio.aleplaytv.com/")
    m_title = re.search(r"<title>(.*?)</title>", html)
    assert m_title
    title_txt = m_title.group(1)
    assert 40 <= len(title_txt) <= 65, f"Title length out of optimal SEO range: {len(title_txt)}"

    m_desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    assert m_desc
    assert 115 <= len(m_desc.group(1)) <= 165, f"Meta description length: {len(m_desc.group(1))}"

    assert '<link rel="canonical" href="https://studio.aleplaytv.com/" />' in html
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'name="twitter:card"' in html

    m_ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m_ld
    ld = json.loads(m_ld.group(1))
    assert ld["@type"] == "WebApplication"
    assert ld["inLanguage"] == "pt-BR"
    assert ld["url"] == "https://studio.aleplaytv.com/"


def test_analytics_onpage_seo_and_breadcrumbs():
    html = render_analytics_dashboard_html(canonical_url="https://studio.aleplaytv.com/analytics")
    assert '<link rel="canonical" href="https://studio.aleplaytv.com/analytics" />' in html
    assert '<meta name="description"' in html
    assert 'property="og:title"' in html
    m_ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m_ld
    ld = json.loads(m_ld.group(1))
    assert ld["@type"] == "WebPage"
    assert ld["breadcrumb"]["@type"] == "BreadcrumbList"
    assert len(ld["breadcrumb"]["itemListElement"]) == 2


def test_robots_txt_and_sitemap_xml():
    robots = render_robots_txt("https://studio.aleplaytv.com")
    assert "Allow: /" in robots
    assert "Allow: /analytics" in robots
    assert "Disallow: /api/" in robots
    assert "Disallow: /mcp" in robots
    assert "Sitemap: https://studio.aleplaytv.com/sitemap.xml" in robots

    sitemap = render_sitemap_xml("https://studio.aleplaytv.com")
    assert "<urlset " in sitemap
    assert "<loc>https://studio.aleplaytv.com/</loc>" in sitemap
    assert "<loc>https://studio.aleplaytv.com/analytics</loc>" in sitemap


def test_video_seo_no_dangling_prepositions_and_platform_tag_limits():
    wrapped = _wrap_news_headline(
        "Música usada por Trump em eventos, YMCA é tocada durante visita à China",
        line_chars=30,
        max_lines=3,
    )
    assert "visita à China" in wrapped
    assert not wrapped.strip().lower().endswith("durante")

    seo_t = _clean_seo_title("Música usada por Trump em eventos, YMCA é tocada durante visita à China", max_chars=70)
    assert not seo_t.split("|")[0].strip().lower().endswith("durante")

    for niche in ("games_gta6", "desenvolvimento_pessoal", "podcast"):
        assert niche in NICHE_TAG_POOLS
        packs = adapt_short_for_all_platforms(
            title="Como a Saúde Mental Sustenta o Sucesso da Família",
            body_text="Estratégias práticas de mentalidade e foco para crescer sem esgotamento.",
            niche=niche,
        )
        assert len(packs["instagram"]["hashtags"]) <= IG_MAX_TAGS
        assert len(packs["tiktok"]["hashtags"]) <= TIKTOK_MAX_TAGS
        assert len(packs["youtube"]["hashtags"]) <= YT_SHORTS_MAX_TAGS


def test_submagic_filler_removal_multicolor_and_opusclip_virality_breakdown():
    from auto_shorts.subtitles import _format_karaoke_token, _strip_spoken_fillers
    from auto_shorts.yt_algorithm import score_short_for_youtube_algorithm

    # 1. Submagic filler cleaner strips 'EH', 'AH', 'HUM' without touching real words
    assert _strip_spoken_fillers(["EH", "REMETE", "AH,", "ISSO"]) == ["REMETE", "ISSO"]
    assert _strip_spoken_fillers(["VOCÊ", "AH", "O", "ALGORITMO"]) == ["VOCÊ", "O", "ALGORITMO"]

    # 2. Multi-color semantic power words (Green money, Red alert, Gold discovery)
    assert r"\c&H0069FF00&" in _format_karaoke_token("MILHÕES", 20)
    assert r"\c&H004D4DFF&" in _format_karaoke_token("URGENTE", 20)
    assert r"\c&H0000FFFF&" in _format_karaoke_token("ALGORITMO", 20)

    # 3. OpusClip-style explainable virality breakdown
    scored = score_short_for_youtube_algorithm(
        pack={
            "title": "GTA 6 Ao Vivo: Davy Jones | Gameplay #Shorts",
            "hook_title": "DAVY JONES NO GTA 6",
            "caption": "Reacao ao vivo no lancamento do GTA 6 com gameplay completa em 60fps #Shorts",
            "hashtags": ["#Shorts", "#GTA6", "#GamerBrasil"],
        },
        validation={"valid": True, "duration": 27.5, "subtitle_cues": 18, "subtitle_overlaps": 0, "mean_volume_db": -14.2},
    )
    assert scored["algo_score"] == 100
    vb = scored["virality_breakdown"]
    assert vb["hook_score"] == 30
    assert vb["retention_score"] == 30
    assert vb["seo_score"] == 20
    assert vb["tech_score"] == 20
    assert "Alto potencial" in vb["why_viral"]

