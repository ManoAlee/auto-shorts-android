from types import SimpleNamespace

import pytest


def test_news_without_source_summary_is_rejected_without_fabrication(monkeypatch):
    from auto_shorts.world_news import build_brazil_news_story_pack

    monkeypatch.setattr("auto_shorts.world_news._extract_article_lead_from_url", lambda _url: ("", ""))
    with pytest.raises(ValueError, match="resumo verificável"):
        build_brazil_news_story_pack(
            {"source": "Fonte", "title": "Manchete isolada", "summary": "", "url": "https://example.com/story", "lang": "pt"},
            use_llm=False,
            translator=lambda value: value,
        )


def test_news_narrative_uses_only_title_and_source_summary(tmp_path):
    from auto_shorts.mahoraga import MahoragaEngine

    engine = MahoragaEngine(db_path=tmp_path / "mahoraga.db")
    title = "Empresa anuncia nova regra para documentos"
    summary = "A empresa vai descontinuar duas opções antigas a partir de dezembro; alguns documentos podem mudar de formatação."
    script, _ = engine.compose_news_narrative(title, summary, "Fonte A", "tech")

    assert title in script
    assert summary.split(";")[0].lower() in script.lower()
    assert "mercado entrou em alerta" not in script.lower()
    assert "impacta diretamente" not in script.lower()


def test_rclone_paths_reject_options_and_traversal():
    from auto_shorts.downloader import is_rclone_target

    assert is_rclone_target("gdrive:Animes_Para_Cortar/episodio 01.mp4")
    assert not is_rclone_target("--config=secret:gdrive")
    assert not is_rclone_target("gdrive:Animes/../../token.txt")
    assert not is_rclone_target("gdrive:/absolute/path.mp4")


def test_drive_listing_reports_auth_or_remote_errors(monkeypatch):
    from auto_shorts import downloader

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "rclone")
    monkeypatch.setattr(
        downloader.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=7, stdout="", stderr="permission denied"),
    )

    with pytest.raises(RuntimeError, match="verifique conexão, autenticação e pasta remota"):
        downloader.list_gdrive_episodes()


def test_drive_listing_filters_video_files_and_keeps_nested_names(monkeypatch):
    from auto_shorts import downloader

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "rclone")
    monkeypatch.setattr(
        downloader.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="ep01.mkv\nnotes.txt\nsubfolder/ep02.mp4\n",
            stderr="",
        ),
    )

    assert downloader.list_gdrive_episodes("gdrive:Animes_Para_Cortar") == [
        "gdrive:Animes_Para_Cortar/ep01.mkv",
        "gdrive:Animes_Para_Cortar/subfolder/ep02.mp4",
    ]


def test_drive_output_folder_groups_by_niche_and_date():
    from auto_shorts.downloader import build_drive_niche_folder

    result = build_drive_niche_folder("noticias_mundiais")
    assert result.startswith("gdrive:Shorts_Finalizados/Noticias_Tech/")
    assert len(result.rsplit("/", 1)[-1]) == 10


def test_model_recommendation_respects_free_ram_and_prefers_installed_gguf():
    from auto_shorts.offline_llm import recommend_local_model_tier

    chosen = recommend_local_model_tier(
        7.25,
        3.0,
        [{"name": "qwen2.5-1.5b-instruct-q4_k_m.gguf"}],
    )

    assert chosen["id"] == "qwen2.5-1.5b-q4"


def test_news_feed_rejects_shopping_roundups_but_keeps_reporting():
    from auto_shorts.world_news import _is_commercial_roundup

    assert _is_commercial_roundup({"title": "Melhor TV 65 polegadas: 13 modelos para comprar", "summary": "Lista de TVs com desconto."})
    assert not _is_commercial_roundup({"title": "Microsoft encerra suporte ao Word", "summary": "A mudança começa em dezembro."})


def test_video_summary_extracts_spoken_text_without_metadata():
    from auto_shorts.webapp import _extract_summary_from_caption

    caption = (
        "Notícia | Mundo Hoje\nDestaque: UM FATO\n\n"
        "Resumo da notícia internacional:\nA empresa divulgou uma mudança para dezembro.\n\n"
        "Fonte original (Fonte A): https://example.com/story\nComente aqui!\n#Notícias"
    )
    assert _extract_summary_from_caption(caption) == "A empresa divulgou uma mudança para dezembro."


def test_anime_title_truncation_preserves_word_and_part_number():
    from auto_shorts.highlights import NICHES, _build_clip_title

    title = _build_clip_title(
        "Entrada Épica Netero e Zeno - Netero vs Pitou - Hunter x Hunter: Momento Épico Dublado (Parte 3)",
        "Netero Mostra Poder Máximo",
        3,
        NICHES["entretenimento_animes"],
    )

    assert len(title) <= 90
    assert title.endswith("(Parte 3)")
    assert not title.endswith("(")


def test_real_feedback_updates_learning_coverage(tmp_path):
    from auto_shorts.evolution import EvolutionStore

    store = EvolutionStore(tmp_path / "learning.db")
    clip_id = store.record_clip("source", "youtube_shorts", "tech", "blur_bg", 35, "GANCHO REAL", 80, "clip.mp4")
    store.record_feedback(clip_id, views=1200, avg_watch_pct=72.5, likes=90, shares=12, saves=18)
    status = store.learning_status()

    assert status["total_clips"] == 1
    assert status["measured_clips"] == 1
    assert status["pending_feedback"] == 0
    assert status["avg_latest_reward"] > 0


def test_kokoro_rate_uses_style_value_without_unsupported_slow_speed():
    from auto_shorts.narrator import VOICE_STYLES, _kokoro_base_speed

    assert _kokoro_base_speed(VOICE_STYLES["narrador_pro"]) == pytest.approx(1.03)
    assert _kokoro_base_speed(VOICE_STYLES["brian_hd"]) == 1.0


def test_background_selector_never_uses_unrelated_gameplay_for_tech(tmp_path, monkeypatch):
    from auto_shorts import gameplay
    from auto_shorts.evolution import EvolutionStore

    assets = gameplay.gameplay_cache_dir(tmp_path)
    subway = assets / "gp_subway_clip1.mp4"
    cosmos = assets / "gp_space_cosmos_clip2.mp4"
    subway.touch()
    cosmos.touch()
    monkeypatch.setattr(gameplay, "list_gameplay_clips", lambda _root: [subway, cosmos])
    monkeypatch.setattr(gameplay, "probe_video_duration", lambda _path: 120.0)
    monkeypatch.setattr(gameplay, "_is_segment_visually_bright", lambda *_args: True)
    seen = {}

    def select(_self, _niche, styles, last_style=""):
        seen["styles"] = styles
        return styles[0]

    monkeypatch.setattr(EvolutionStore, "select_evolving_background_style", select)
    result = gameplay.pick_evolving_background(tmp_path, niche="ia_tech", auto_download=False)

    assert result is not None
    assert result[2] == "space_cosmos"
    assert seen["styles"] == ["space_cosmos"]


def test_multiscene_broll_stays_within_the_niche(tmp_path, monkeypatch):
    from pathlib import Path
    from auto_shorts import gameplay, narrator

    clips = []
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for name in ("gp_space_cosmos_a.mp4", "gp_urban_rain_b.mp4", "gp_subway_c.mp4"):
        clip = tmp_path / name
        clip.write_bytes(b"\x00\x00\x00\x18ftyp" + b"x" * 60_000)
        clips.append(clip)
    monkeypatch.setattr(gameplay, "list_gameplay_clips", lambda _root: clips)
    monkeypatch.setattr(gameplay, "probe_video_duration", lambda _path: 60.0)
    monkeypatch.setattr(gameplay, "_is_segment_visually_bright", lambda *_args: True)

    def fake_ffmpeg(command, **_kwargs):
        Path(command[-1]).write_bytes(b"x" * 60_000)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(narrator.subprocess, "run", fake_ffmpeg)
    combined, styles = narrator._build_multiscene_broll(
        tmp_path, clips[0], "space_cosmos", 12.0, work_dir, niche="ia_tech"
    )

    assert combined.name == "_multiscene_broll.mp4"
    assert "subway" not in styles
    assert "space_cosmos" in styles and "urban_rain" in styles


def test_script_subtitle_coverage_detects_truncated_narration():
    from auto_shorts.narrator import _script_subtitle_coverage

    full = "A narração completa tem oito palavras para validar a legenda sem corte."
    partial = """1
00:00:00,000 --> 00:00:01,000
A narração completa tem oito
"""
    result = _script_subtitle_coverage(full, partial)

    assert result["script_words"] == 12
    assert result["coverage"] < 0.85


def test_voice_telemetry_reports_kokoro_voice_id():
    from auto_shorts.narrator import active_voice_label

    assert active_voice_label("thalita_hd", "Kokoro-82M PT-BR Offline (Natural)") == "pf_dora"


def test_each_platform_uses_its_own_publish_metadata():
    from auto_shorts.publisher import _build_instagram_caption
    from auto_shorts.tiktok_cdp import _build_tiktok_caption
    from auto_shorts.youtube_cdp import _build_youtube_cdp_metadata

    pack = {
        "title": "Título comum",
        "caption": "Descrição comum",
        "tiktok_caption": "Gancho nativo do TikTok #tec",
        "instagram_caption": "Pergunta nativa para Instagram #reels",
        "youtube_title": "Título SEO do YouTube",
        "youtube_description": "Descrição e fonte para YouTube",
        "niche": "ia_tech",
    }

    assert "Gancho nativo" in _build_tiktok_caption(pack, "fallback")
    assert "Pergunta nativa" in _build_instagram_caption(pack, "fallback")
    yt = _build_youtube_cdp_metadata(pack, "fallback")
    assert yt["title"] == "Título SEO do YouTube"
    assert "Descrição e fonte" in yt["description"]


def test_autopublish_blocks_narration_with_bad_integrity_or_off_niche_broll():
    from auto_shorts.smart_autopublish import _passes_narrated_preflight

    pack = {
        "source_type": "narrated_original",
        "script_integrity": {"coverage": 1.0},
        "niche": "ia_tech",
        "background_style": "space_cosmos+drone_cinema",
    }
    assert _passes_narrated_preflight(pack)
    assert not _passes_narrated_preflight({**pack, "script_integrity": {"coverage": 0.47}})
    assert not _passes_narrated_preflight({**pack, "background_style": "space_cosmos+subway"})
