"""Unit tests for world news sanitization, SEO title formatting, word-boundary hooks, and humor/memes niche."""

import pytest
from auto_shorts.config import NICHES, NICHE_BADGES
from auto_shorts.horizon_radar import HORIZON_CATALOG
from auto_shorts.mahoraga import clean_word_boundary_hook, MahoragaEngine
from auto_shorts.tiktok_algorithm import NICHE_MENTALISM_PLAYBOOKS
from auto_shorts.world_news import (
    _clean_seo_title,
    clean_truncate_to_sentence,
    sanitize_news_lead_text,
    build_brazil_news_story_pack,
)


def test_clean_seo_title_preserves_internal_hyphens_and_strips_brands():
    # Internal hyphens/dashes in game news must NEVER strip the title
    raw1 = "GTA 6 - Caixa física revela vantagens no PS5"
    res1 = _clean_seo_title(raw1, suffix=" | Plantão Games")
    assert "Caixa física revela vantagens" in res1
    assert res1.endswith(" | Plantão Games")
    assert not res1.startswith("GTA 6 | Plantão Games")

    # Trailing publisher brands at the end should be stripped
    raw2 = "Musk defende volta de Jensen Huang para comando da Nvidia - G1"
    res2 = _clean_seo_title(raw2, suffix=" | Plantão Tech")
    assert "- G1" not in res2
    assert "Musk defende volta de Jensen" in res2
    assert res2.endswith(" | Plantão Tech")

    raw3 = "GTA 6 precisa de nota 90 no Metacritic, diz analista | Viciados.net"
    res3 = _clean_seo_title(raw3, suffix=" | Plantão Games")
    assert "Viciados" not in res3
    assert "Metacritic" in res3


def test_clean_word_boundary_hook_never_slices_words():
    # Must never produce "AO BR" instead of "AO BRASIL"
    h1 = clean_word_boundary_hook("UE DECIDE FIM DO EMBARGO AO BRASIL", max_chars=32)
    assert not h1.endswith(" BR")
    assert h1 in ("UE DECIDE FIM DO EMBARGO", "UE DECIDE FIM DO EMBARGO AO BRASIL")

    # Must never produce "REVELA VA" instead of "REVELA VANTAGENS"
    h2 = clean_word_boundary_hook("GTA 6 CAIXA FÍSICA REVELA VANTAGENS", max_chars=32)
    assert not h2.endswith(" VA")
    assert "REVELA" in h2

    # Contractions and prepositions must be stripped if dangling at the end
    h3 = clean_word_boundary_hook("DESTAQUE SOBRE O FUTURO DO", max_chars=28)
    assert not h3.endswith(" DO")


def test_sanitize_news_lead_text_removes_portal_junk_and_emojis():
    raw_junk = (
        "Movimento reúne empresários e investidores da fabricante. ➡️ O escândalo parece filme. "
        "Veja as notícias de GTA 6 primeiro no seu Discover. Toque aqui e siga. "
        "Você pode conferir mais notícias de GTA 6, no vídeo do nosso parceiro SanInPlay : "
        "A Rockstar confirmou novidades para a comunidade gamer."
    )
    clean = sanitize_news_lead_text(raw_junk)
    assert "Discover" not in clean
    assert "Toque aqui" not in clean
    assert "SanInPlay" not in clean
    assert "➡️" not in clean
    assert "Rockstar confirmou novidades" in clean


def test_clean_truncate_to_sentence_avoids_mid_sentence_cuts():
    text = (
        "O executivo renunciou ao cargo após denúncias de relacionamentos na empresa. "
        "A mobilização envolve empresários de renome global e funcionários da fábrica enquanto uma investigação prossegue no conselho."
    )
    # Truncate to 100 chars
    res = clean_truncate_to_sentence(text, max_chars=110)
    # Must end with full stop and not mid-sentence fragment
    assert res.endswith(".")
    assert "enquanto uma" not in res
    assert "O executivo renunciou ao cargo após denúncias de relacionamentos na empresa." == res


def test_humor_memes_niche_registered_across_system():
    assert "humor_memes" in NICHES
    assert NICHES["humor_memes"].key == "humor_memes"
    assert "MEMES" in NICHE_BADGES["humor_memes"]

    assert "humor_memes" in HORIZON_CATALOG
    assert len(HORIZON_CATALOG["humor_memes"]["cards"]) >= 2
    assert "Casimiro" in HORIZON_CATALOG["humor_memes"]["cards"][0]["title_pt"] or "Defante" in HORIZON_CATALOG["humor_memes"]["cards"][0]["title_pt"]

    assert "humor_memes" in NICHE_MENTALISM_PLAYBOOKS
    assert NICHE_MENTALISM_PLAYBOOKS["humor_memes"]["ideal_bpm_cuts_sec"] <= 2.2


def test_build_brazil_news_story_pack_preserves_specific_summary():
    story = {
        "title": "GTA 6 terá tracklist com mais de 30 faixas musicais",
        "summary": "Vazamento revela seleção sonora diversificada para as estações de rádio de Leonida, incluindo rap, rock clássico e synthwave.",
        "source": "Viciados.net",
        "url": "https://viciados.net/gta-6-tracklist",
        "category": "games",
        "lang": "pt",
    }
    pack = build_brazil_news_story_pack(story, use_llm=False)
    # Must preserve the specific musical tracklist theme and not replace with Vice City boilerplate
    assert "tracklist" in pack["caption"].lower() or "faixas" in pack["caption"].lower() or "musical" in pack["caption"].lower()
    assert "A Rockstar Games confirmou o aguardado lançamento de Grand Theft Auto 6 para PlayStation 5" not in pack["caption"]
    assert len(pack["script"].split()) >= 60


def test_thumbnail_and_video_safe_zones():
    from auto_shorts.thumbnail import build_thumbnail_filter
    from auto_shorts.renderer import build_video_filter
    from auto_shorts.subtitles import generate_ass_subtitles
    import tempfile
    from pathlib import Path

    # 1. Thumbnail filter on 720x1280 must position badge in top safe zone (>= 140px, never 28px)
    thumb_vf = build_thumbnail_filter(720, 1280, "DESENVOLVEDOR PS5 DÁ A REAL", badge="GAMES", font_path="C:/Windows/Fonts/arialbd.ttf")
    # Badge Y must be >= 140
    import re
    m_badge = re.search(r"text='GAMES'.*?:y=(\d+)", thumb_vf)
    assert m_badge, "Badge drawtext filter not found"
    badge_y = int(m_badge.group(1))
    assert badge_y >= 140, f"Thumbnail badge Y ({badge_y}) is in unsafe top bar zone (< 140)"

    # 2. Video hook banner on 720x1280 must position hook pill in top safe zone (>= 150px)
    vid_vf = build_video_filter(layout="blur_bg", width=720, height=1280, hook_title="DESENVOLVEDOR PS5 DÁ A REAL", font_path="C:/Windows/Fonts/arialbd.ttf")
    m_hook = re.search(r"boxcolor=0x0B0F19@0.80.*?:y=(\d+)", vid_vf)
    assert m_hook, "Hook banner drawtext not found"
    hook_y = int(m_hook.group(1))
    assert hook_y >= 150, f"Hook banner Y ({hook_y}) is in unsafe top bar zone (< 150)"

    # 3. Subtitles default MarginV on 720x1280 must be >= 280px (clear of TikTok caption fold)
    with tempfile.TemporaryDirectory() as td:
        ass_out = Path(td) / "test.ass"
        generate_ass_subtitles([{"start": 0.0, "end": 2.0, "text": "TESTE DE LEGENDA"}], 0.0, 2.0, ass_out, width=720, height=1280)
        ass_content = ass_out.read_text(encoding="utf-8")
        # Check MarginV in Style lines (Format: ... MarginL, MarginR, MarginV, Encoding)
        m_margin = re.search(r"Style:\s*Default,.*?,\d+,\d+,(\d+),1\s*$", ass_content, re.M)
        assert m_margin, "MarginV not found in ASS style"
        margin_v = int(m_margin.group(1))
        assert margin_v >= 280, f"Subtitle MarginV ({margin_v}) is too low, will overlap TikTok caption (< 280)"


def test_sanitize_news_lead_strips_bbc_nav_credits_notifications_and_dups():
    raw = (
        "No Reino Unido, a recomendação é sobreviver por três dias. "
        "Seções Notícias Brasil Internacional Economia Saúde Ciência Tecnologia "
        "Brasil Internacional Economia Saúde Ciência Tecnologia "
        "Por que a Europa pediu kits de emergência? Crédito, Reuters "
        "Nas últimas semanas, governos na Europa têm pedido que cidadãos se preparem. "
        "Menu Ative nossas notificações Você quer ficar por dentro das notícias mais importantes "
        "e receber notificações em tempo real? A decisão foi confirmada hoje. "
        "LG QNED70 promete cores vibrantes (imagem. Divulgação/LG) A nova linha chega em 2026. "
        "Economize 32% na oferta do Magalu no AliExpress Economize 32% na oferta do Magalu no AliExpress."
    )
    cleaned = sanitize_news_lead_text(raw)
    low = cleaned.lower()
    assert "seções notícias" not in low
    assert "crédito, reuters" not in low
    assert "ative nossas notificações" not in low
    assert "divulgação/lg" not in low
    assert "imagem." not in low
    assert cleaned.count("Economize 32% na oferta do Magalu no AliExpress") <= 1
    assert "No Reino Unido" in cleaned
    assert "Nas últimas semanas" in cleaned
    assert "A decisão foi confirmada hoje." in cleaned


def test_build_brazil_news_story_pack_rejects_1sentence_stubs_and_promos():
    stub_story = {
        "title": "Às vésperas de GTA VI, hacker responsável por vazamento do jogo se declara culpado - G1",
        "summary": "Às vésperas de GTA VI, hacker responsável por vazamento do jogo se declara culpado G1",
        "source": "Google News",
        "lang": "pt",
        "category": "games",
    }
    with pytest.raises(ValueError):
        build_brazil_news_story_pack(stub_story, use_llm=False)

    promo_story = {
        "title": "TV LG QNED 65 com Mini LED baixa 32% em até 12x no mês",
        "summary": "Economize 32% na oferta do Magalu no AliExpress usando cupom AEMEGA8 por R$ 3.399.",
        "source": "TechTudo",
        "lang": "pt",
        "category": "tech",
    }
    with pytest.raises(ValueError):
        build_brazil_news_story_pack(promo_story, use_llm=False)


def test_karaoke_subtitles_highlight_power_numbers_and_keywords():
    import tempfile
    from pathlib import Path
    from auto_shorts.subtitles import generate_ass_subtitles

    with tempfile.TemporaryDirectory() as td:
        ass_out = Path(td) / "power.ass"
        generate_ass_subtitles(
            [{"start": 0.0, "end": 2.4, "text": "URGENTE 32% EM IA"}],
            0.0,
            2.4,
            ass_out,
            width=720,
            height=1280,
        )
        content = ass_out.read_text(encoding="utf-8")
    assert r"\kf" in content
    assert r"\c&H0000FFFF&" in content
    assert "URGENTE" in content
    assert "32%" in content


def test_voice_clone_hf_chunker_and_style_registered():
    from auto_shorts.narrator import VOICE_STYLES
    from auto_shorts.voice_clone_hf import split_text_for_chatterbox

    assert "minha_voz" in VOICE_STYLES
    long_pt = (
        "Primeira notícia urgente do Brasil sobre inteligência artificial e economia. "
        "Segunda frase detalhando o impacto nos mercados financeiros e tecnologia móvel. "
        "Terceira frase explicando por que desenvolvedores estão adotando modelos offline no celular. "
        "Quarta frase concluindo com uma pergunta direta para os comentários."
    )
    chunks = split_text_for_chatterbox(long_pt, max_chars=140)
    assert len(chunks) >= 2
    assert all(len(c) <= 140 for c in chunks)


def test_hype_engine_boosts_gta6_launch_window_in_nov_2026():
    import datetime as dt
    from auto_shorts.hype_engine import build_weighted_rotation, pick_hype_aware_niche

    nov17 = dt.date(2026, 11, 17)
    rot = build_weighted_rotation(nov17)
    assert "games_gta6" in rot
    assert rot.count("games_gta6") >= 3

    niche0, topic0, summary = pick_hype_aware_niche(0, "all", today=nov17)
    assert niche0 == "games_gta6"
    assert topic0 is None  # even cycle -> video/gameplay/react clipping
    assert "faltam 2d" in summary

    niche1, topic1, _ = pick_hype_aware_niche(2, "all", today=nov17)
    niche_odd, topic_odd, _ = pick_hype_aware_niche(3, "all", today=nov17)
    assert "games_gta6" in {niche1, niche_odd} or topic_odd == "games" or topic1 == "games"



