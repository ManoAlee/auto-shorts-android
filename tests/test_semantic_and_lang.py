"""Tests for Universal Semantic Visual Engine and multi-language anime title/subtitle hygiene."""

from auto_shorts.highlights import NICHES, _build_clip_title
from auto_shorts.semantic_visual_engine import extract_visual_queries


def test_extract_visual_queries_for_games_and_politics():
    q_games = extract_visual_queries(
        "GTA 6 precisa de nota 90 no Metacritic, diz analista",
        "Analista afirma que GTA 6 da Rockstar Games precisa atingir nota alta.",
        category="games_gta6",
    )
    assert len(q_games) >= 3
    assert any(q["type"] == "video" for q in q_games)
    assert any("GTA" in q["query"] or "Metacritic" in q["query"] for q in q_games)

    q_pol = extract_visual_queries(
        "Lula se reúne com líderes do Congresso em Brasília para votar pacote fiscal",
        "Presidente Luiz Inácio Lula da Silva discute medidas econômicas no Planalto.",
        category="noticias_mundiais",
    )
    assert len(q_pol) >= 3
    assert any(q["type"] == "photo" for q in q_pol)
    assert any("Lula" in q["query"] or "Congresso" in q["query"] for q in q_pol)


def test_anime_title_respects_audio_language():
    niche = NICHES["entretenimento_animes"]
    src = "Jin-woo vs. Kargalgan | Solo Leveling 2ª Temporada"
    ja_title = _build_clip_title(src, "PRESTA ATENCAO NISSO", 2, niche, audio_lang="ja")
    assert "Legendada" in ja_title
    assert "Dublada" not in ja_title

    pt_title = _build_clip_title(src, "PRESTA ATENCAO NISSO", 2, niche, audio_lang="pt")
    assert "Dublada" in pt_title
