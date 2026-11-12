"""Unit tests for auto-shorts-android pipeline components."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_shorts.anime_trends import fetch_anilist_trending, get_releasing_anime_radar
from auto_shorts.cli import build_parser
from auto_shorts.config import LOUDNORM_FILTER, METADATA_SCRUB, load_dotenv_file
from auto_shorts.discovery import parse_discovery_lines
from auto_shorts.downloader import download_video_and_subs
from auto_shorts.evolution import EvolutionStore
from auto_shorts.highlights import chunk_segments, dedupe_highlights, detect_highlights
from auto_shorts.narrator import (
    DEFAULT_STYLE_KEY,
    VOICE_STYLES,
    _build_weighted_srt,
    _word_events_to_srt,
    resolve_background_video,
    synthesize_narration,
)
from auto_shorts.narrator import (
    DEFAULT_STYLE_KEY,
    VOICE_STYLES,
    _build_weighted_srt,
    _word_events_to_srt,
    humanize_ptbr_script,
    resolve_background_video,
    synthesize_narration,
)
from auto_shorts.publisher import build_publish_pack, publish_instagram_reel, publish_pack_to_youtube, publish_youtube_short
from auto_shorts.renderer import build_ffmpeg_command, build_video_filter
from auto_shorts.retention import build_pattern_interrupt_filter, get_retention_profile
from auto_shorts.silence import parse_silencedetect_log, remap_transcript_segments
from auto_shorts.subtitles import escape_ffmpeg_filter_path, generate_ass_subtitles
from auto_shorts.team import CHANNEL_PERSONAS, build_persona_script_brief, generate_channel_planner, list_channel_personas
from auto_shorts.thumbnail import build_thumbnail_filter
from auto_shorts.transcript import parse_srt, parse_vtt, parse_whisper_cpp_json
from auto_shorts.validator import validate_generated_short, validate_subtitle_file
from auto_shorts.webapp import render_dashboard_html


def test_parse_vtt_deduplicates_rolling_youtube_captions():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
ola pessoal

00:00:02.000 --> 00:00:04.500
ola pessoal hoje vamos falar de juros

00:00:04.500 --> 00:00:07.000
<c>segredo dos bancos</c>
"""
    parsed = parse_vtt(vtt)
    assert len(parsed["segments"]) == 2
    assert parsed["segments"][0]["text"] == "ola pessoal hoje vamos falar de juros"
    assert parsed["segments"][0]["end"] == 4.5
    assert parsed["segments"][1]["text"] == "segredo dos bancos"


def test_parse_srt_and_whisper_json():
    srt = "1\n00:00:00,500 --> 00:00:03,000\nPrimeiro corte\n\n2\n00:00:03,100 --> 00:00:06,000\nSegundo corte\n"
    res_srt = parse_srt(srt)
    assert res_srt["duration"] == 6.0
    assert len(res_srt["segments"]) == 2

    whisper_payload = json.dumps({
        "transcription": [
            {
                "offsets": {"from": 1000, "to": 4000},
                "text": " Teste ARM64 ",
                "tokens": [{"text": " Teste", "offsets": {"from": 1000, "to": 2000}}],
            }
        ]
    })
    res_w = parse_whisper_cpp_json(whisper_payload)
    assert res_w["duration"] == 4.0
    assert res_w["segments"][0]["words"][0]["word"] == "Teste"


def test_chunk_and_dedupe_highlights():
    segs = [{"start": float(i * 100), "end": float(i * 100 + 50), "text": f"bloco {i}"} for i in range(25)]
    chunks = chunk_segments(segs, duration=2500.0)
    assert len(chunks) >= 2

    kept = dedupe_highlights([
        {"start_time": 10.0, "end_time": 75.0, "score": 92},
        {"start_time": 20.0, "end_time": 80.0, "score": 70},  # overlaps heavily
        {"start_time": 120.0, "end_time": 185.0, "score": 85},
    ])
    assert len(kept) == 2
    assert kept[0]["score"] == 92
    assert kept[1]["score"] == 85


def test_offline_highlight_scoring_respects_tiktok_duration():
    segs = [
        {"start": float(i * 10), "end": float((i + 1) * 10), "text": "O segredo para investir dinheiro e pagar divida hoje!"}
        for i in range(15)
    ]
    transcript = {"duration": 150.0, "segments": segs}
    clips = detect_highlights(
        transcript,
        platform_key="tiktok_rewards",
        niche_key="financas",
        num_clips=2,
        use_llm=False,
    )
    assert len(clips) >= 1
    assert clips[0]["end_time"] - clips[0]["start_time"] >= 62.0


def test_offline_highlight_snaps_end_to_complete_sentence():
    segs = [
        {"start": 0.0, "end": 18.0, "text": "O segredo do dinheiro que ninguem te conta na escola."},
        {"start": 18.0, "end": 36.0, "text": "Quando voce investe todo mes em juros compostos,"},
        {"start": 36.0, "end": 45.0, "text": "o retorno cresce em bola de neve e muda sua vida,"},
        {"start": 45.0, "end": 53.0, "text": "principalmente se voce nao resgatar antes da hora."},
        {"start": 53.0, "end": 62.0, "text": "E agora começa outro assunto totalmente diferente"},
    ]
    transcript = {"duration": 62.0, "segments": segs}
    clips = detect_highlights(
        transcript,
        platform_key="youtube_shorts",
        niche_key="financas",
        num_clips=1,
        use_llm=False,
    )
    assert len(clips) == 1
    # Must extend past 45.0s comma clause to finish cleanly at 53.0s period (and stay <= 57.0s)
    assert clips[0]["end_time"] == 53.0
    assert clips[0]["clip_summary"].endswith(".")


def test_silence_parse_and_remap():
    stderr = """
[silencedetect @ 0x1] silence_start: 2.000
[silencedetect @ 0x1] silence_end: 4.000 | silence_duration: 2.000
"""
    intervals = parse_silencedetect_log(stderr, total_duration=10.0)
    assert intervals == [(0.0, 2.12), (3.88, 10.0)]

    remapped = remap_transcript_segments(
        [{"start": 0.5, "end": 1.5, "text": "Hook"}, {"start": 5.0, "end": 7.0, "text": "Corpo"}],
        intervals,
    )
    assert remapped[0]["start"] == 0.5
    assert remapped[1]["start"] == round(2.12 + (5.0 - 3.88), 3)


def test_ass_generation_and_ffmpeg_command_safety(tmp_path):
    ass_path = tmp_path / "subs_01.ass"
    generate_ass_subtitles(
        [{"start": 10.0, "end": 14.0, "text": "Texto com {chaves} e oito palavras para quebrar linha"}],
        clip_start=10.0,
        clip_end=15.0,
        out_path=ass_path,
    )
    content = ass_path.read_text(encoding="utf-8")
    assert "Dialogue: 0,0:00:00.00," in content
    assert "(CHAVES)" in content

    escaped = escape_ffmpeg_filter_path(r"C:\tmp\subs_01.ass")
    assert "\\" not in escaped.replace("\\:", "")
    assert "C\\:/tmp/subs_01.ass" == escaped

    vf = build_video_filter("blur_bg", 720, 1280, ass_path=ass_path, hook_title="SEGREDO: 3 PASSOS", font_path="/tmp/font.ttf")
    assert "boxblur=22:3" in vf
    assert "fontfile=" in vf
    assert "font=" not in vf.replace("fontfile=", "")

    cmd = build_ffmpeg_command("in.mp4", "out.mp4", 10.0, 75.0, layout="blur_bg", encoder="h264_mediacodec")
    assert "-af" in cmd and LOUDNORM_FILTER in cmd
    for flag in METADATA_SCRUB:
        assert flag in cmd
    assert "h264_mediacodec" in cmd


def test_cli_parser_defaults():
    args = build_parser().parse_args(["https://youtu.be/abc", "--niche", "ia_tech", "--offline"])
    assert args.platform == "tiktok_rewards"
    assert args.niche == "ia_tech"
    assert args.offline is True


def test_evolution_bandit_and_publish_pack(tmp_path):
    store = EvolutionStore(tmp_path / "evo.db")
    c1 = store.record_clip("vid1", "tiktok_rewards", "financas", "blur_bg", 68.0, "JUROS COMPOSTOS", 88, "s1.mp4")
    c2 = store.record_clip("vid2", "tiktok_rewards", "financas", "center_crop", 65.0, "ERRO DO CARTAO", 82, "s2.mp4")
    c3 = store.record_clip("vid3", "tiktok_rewards", "financas", "split_top_bottom", 70.0, "DEBATE PIX", 84, "s3.mp4")
    store.record_feedback(c1, views=25000, avg_watch_pct=78.0, shares=180, saves=220)
    store.record_feedback(c2, views=1200, avg_watch_pct=32.0, shares=2, saves=4)
    store.record_feedback(c3, views=900, avg_watch_pct=28.0, shares=1, saves=2)

    assert store.recommend_layout("financas") == "blur_bg"
    ctx = store.build_learning_context("financas")
    assert "JUROS COMPOSTOS" in ctx

    pack = build_publish_pack({"title": "Teste", "hook_title": "SEGREDO PIX", "cta_line": "Link na bio", "output_path": "s1.mp4", "clip_id": c1}, "youtube_shorts", "financas")
    assert "#Shorts" in pack["hashtags"]
    assert "#financas" in pack["hashtags"]

    anime_pack = build_publish_pack({"title": "Teoria", "hook_title": "TEORIA DO CAPITULO", "cta_line": "Mangas na bio", "output_path": "a1.mp4", "clip_id": 9}, "tiktok_rewards", "entretenimento_animes")
    assert "#anime" in anime_pack["hashtags"]
    assert "#teoria" in anime_pack["hashtags"]

    anime_clips = detect_highlights(
        {"duration": 100.0, "segments": [{"start": 0.0, "end": 70.0, "text": "Essa teoria do manga explica o segredo do vilao no episodio final do anime!"}]},
        platform_key="tiktok_rewards",
        niche_key="entretenimento_animes",
        num_clips=1,
        use_llm=False,
    )
    assert len(anime_clips) == 1
    assert "teoria" in anime_clips[0]["cta_line"].lower()
    assert "shopee" not in anime_clips[0]["cta_line"].lower()


def test_discovery_filtering_and_dedupe(tmp_path):
    ndjson = "\n".join([
        json.dumps({"id": "short1", "webpage_url": "https://youtu.be/short1", "title": "Ja eh short", "duration": 45, "view_count": 999999}),
        json.dumps({"id": "live1", "webpage_url": "https://youtu.be/live1", "title": "Ao vivo", "duration": 600, "live_status": "is_live", "view_count": 50000}),
        json.dumps({"id": "seen1", "webpage_url": "https://youtu.be/seen1", "title": "Ja cortado", "duration": 600, "view_count": 80000}),
        json.dumps({"id": "good1", "webpage_url": "https://youtu.be/good1", "title": "Teoria Anime 1", "duration": 520, "view_count": 120000}),
        json.dumps({"id": "good2", "webpage_url": "https://youtu.be/good2", "title": "Teoria Anime 2", "duration": 800, "view_count": 350000}),
    ])
    store = EvolutionStore(tmp_path / "evo.db")
    store.mark_source_processed("seen1", "https://youtu.be/seen1", "Ja cortado", "entretenimento_animes")

    found = parse_discovery_lines(ndjson, seen_ids=store.get_processed_ids())
    assert [v["id"] for v in found] == ["good2", "good1"]


def test_downloader_recovers_from_subtitle_429(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        if "--write-auto-subs" in cmd:
            (tmp_path / "source.pt.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\noi\n", encoding="utf-8")
            return type("P", (), {"returncode": 1})()
        (tmp_path / "source.mp4").write_bytes(b"mp4")
        return type("P", (), {"returncode": 0})()

    monkeypatch.setattr("auto_shorts.downloader.subprocess.run", fake_run)
    video, sub = download_video_and_subs("https://youtu.be/abc", tmp_path)
    assert video.name == "source.mp4"
    assert sub is not None and sub.name == "source.pt.vtt"
    assert len(calls) == 2


def test_smart_retention_and_instagram_publisher_validation(monkeypatch):
    profile = get_retention_profile("instagram_reels")
    assert profile.min_silence_sec == 0.45
    assert profile.punch_zoom > 1.0

    zoom_filter = build_pattern_interrupt_filter(720, 1280, zoom=1.05, interval_sec=6)
    assert "eval=frame" in zoom_filter
    assert "crop=720:1280" in zoom_filter

    vf = build_video_filter("blur_bg", 720, 1280, punch_zoom=1.05)
    assert "eval=frame" in vf

    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    try:
        publish_instagram_reel("https://example.com/clip.mp4", "Teste")
        assert False, "Should require IG_USER_ID and IG_ACCESS_TOKEN"
    except RuntimeError as exc:
        assert "IG_USER_ID" in str(exc)


def test_load_dotenv_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nTEST_SHORT_VAR=\"valor123\"\n", encoding="utf-8")
    monkeypatch.delenv("TEST_SHORT_VAR", raising=False)
    load_dotenv_file(env_file)
    import os
    assert os.environ.get("TEST_SHORT_VAR") == "valor123"


def test_youtube_short_upload_validation_and_resumable_flow(tmp_path, monkeypatch):
    mp4 = tmp_path / "short.mp4"
    mp4.write_bytes(b"fake-mp4-data")

    monkeypatch.delenv("YT_CLIENT_ID", raising=False)
    try:
        publish_youtube_short(mp4, "Titulo", "Desc")
        assert False, "Should require YouTube OAuth credentials"
    except RuntimeError as exc:
        assert "YT_CLIENT_ID" in str(exc)

    class FakeResp:
        def __init__(self, body, headers=None):
            self._body = body
            self.headers = headers or {}

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    seen_urls = []

    def fake_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        seen_urls.append(url)
        if "oauth2.googleapis.com/token" in url:
            return FakeResp(b'{"access_token": "tok123"}')
        if "uploadType=resumable" in url:
            return FakeResp(b"", headers={"Location": "https://upload.example.com/session1"})
        return FakeResp(b'{"id": "ytVid999"}')

    monkeypatch.setattr("auto_shorts.publisher.urllib.request.urlopen", fake_urlopen)
    res = publish_youtube_short(
        mp4, "Teoria Anime", "Explicacao", tags=["#anime"],
        client_id="cid", client_secret="csec", refresh_token="rtok",
    )
    assert res["video_id"] == "ytVid999"
    assert res["url"] == "https://youtube.com/shorts/ytVid999"
    assert len(seen_urls) == 3


def test_real_title_hook_and_complete_description():
    transcript = {
        "duration": 90.0,
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "mano mano olha isso"},
            {"start": 5.0, "end": 45.0, "text": "A teoria secreta de Bleach muda tudo sobre o retorno do anime!"},
            {"start": 45.0, "end": 85.0, "text": "O autor deixou pistas ocultas nos capitulos finais do manga."},
        ],
    }
    clips = detect_highlights(
        transcript,
        platform_key="youtube_shorts",
        niche_key="entretenimento_animes",
        num_clips=1,
        use_llm=False,
        source_title="7 TEORIAS CHOCANTES QUE VAI MUDAR TUDO EM BLEACH [OFICIAL]",
    )
    assert len(clips) == 1
    assert "Corte " not in clips[0]["title"]
    assert "7 TEORIAS CHOCANTES" in clips[0]["title"]
    assert "BLEACH" in clips[0]["hook_title"]
    assert clips[0]["clip_summary"]

    pack = build_publish_pack(
        {**clips[0], "output_path": "out.mp4", "clip_id": 10},
        platform="youtube_shorts",
        niche="entretenimento_animes",
        source_meta={
            "title": "7 TEORIAS CHOCANTES QUE VAI MUDAR TUDO EM BLEACH",
            "channel": "Bleach Brasil",
            "webpage_url": "https://www.youtube.com/watch?v=vPGK2BGblRU",
        },
    )
    assert "Sobre este corte:" in pack["caption"]
    assert "Bleach Brasil" in pack["caption"]
    assert "https://www.youtube.com/watch?v=vPGK2BGblRU" in pack["caption"]
    assert "#Shorts" in pack["caption"]


def test_advanced_thumbnail_filter_and_podcast_playlist(monkeypatch):
    vf = build_thumbnail_filter(1280, 720, "SEGREDO DO PODCAST AO VIVO", badge="PODCAST", font_path="/tmp/font.ttf")
    assert "eq=contrast=1.12" in vf
    assert "vignette=PI/4" in vf
    assert "boxcolor=#FFD400" in vf
    assert "PODCAST" in vf

    from auto_shorts.publisher import ensure_youtube_playlist, add_video_to_playlist

    class FakeResp:
        def __init__(self, body):
            self._body = body
        def read(self):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "oauth2.googleapis.com/token" in url:
            return FakeResp(b'{"access_token": "tok"}')
        if "playlists?part=snippet&mine=true" in url:
            return FakeResp(b'{"items": []}')
        if "playlists?part=snippet,status" in url:
            return FakeResp(b'{"id": "PL_PODCAST_1"}')
        if "playlistItems?part=snippet" in url:
            return FakeResp(b'{"id": "PLI_1"}')
        return FakeResp(b'{}')

    monkeypatch.setattr("auto_shorts.publisher.urllib.request.urlopen", fake_urlopen)
    pl_id = ensure_youtube_playlist("Podcasts Brasil - Shorts", client_id="c", client_secret="s", refresh_token="r")
    assert pl_id == "PL_PODCAST_1"
    item = add_video_to_playlist(pl_id, "vid123", client_id="c", client_secret="s", refresh_token="r")
    assert item["playlist_item_id"] == "PLI_1"


def test_webapp_accessibility_and_voice_styles():
    assert "anime_hype" in VOICE_STYLES
    assert "storyteller" in VOICE_STYLES

    doc = render_dashboard_html()
    assert 'role="tablist"' in doc
    assert 'aria-live="polite"' in doc
    assert 'prefers-reduced-motion' in doc
    assert 'id="channel-telemetry"' in doc
    assert 'id="btn-voice-preview"' in doc
    for field_id in ("cut-niche", "cut-platform", "cut-source", "cut-auto-publish", "voice-style", "voice-bg", "voice-script", "voice-humanize", "voice-auto-publish"):
        assert f'id="{field_id}"' in doc
        assert f'for="{field_id}"' in doc


def test_anime_release_radar_parses_anilist(monkeypatch):
    sample = {
        "data": {
            "Page": {
                "media": [
                    {
                        "id": 21,
                        "title": {"romaji": "ONE PIECE", "english": "ONE PIECE"},
                        "popularity": 768380,
                        "trending": 120,
                        "episodes": None,
                        "genres": ["Action", "Adventure"],
                        "nextAiringEpisode": {"episode": 1181, "timeUntilAiring": 36000},
                    }
                ]
            }
        }
    }

    class FakeResp:
        def read(self):
            return json.dumps(sample).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("auto_shorts.anime_trends.urllib.request.urlopen", lambda req, timeout=12: FakeResp())
    items = fetch_anilist_trending(limit=5)
    assert len(items) == 1
    assert items[0]["next_episode"] == 1181
    assert "episodio 1180" in items[0]["youtube_query"]
    assert get_releasing_anime_radar(limit=5)[0]["title"] == "ONE PIECE"


def test_male_voice_default_non_overlapping_subtitles_and_tts_cascade(tmp_path, monkeypatch):
    # Default styles must be natural PT-BR male voice (never female by default).
    assert VOICE_STYLES[DEFAULT_STYLE_KEY].voice == "pt-BR-AntonioNeural"
    assert VOICE_STYLES["storyteller"].voice == "pt-BR-AntonioNeural"

    # Overlapping SRT cues must flatten into non-overlapping ASS Dialogue lines.
    ass_file = tmp_path / "non_overlap.ass"
    generate_ass_subtitles(
        [
            {"start": 0.10, "end": 5.57, "text": "Primeira frase longa do narrador."},
            {"start": 5.52, "end": 9.80, "text": "Segunda frase que comecou antes!"},
        ],
        clip_start=0.0,
        clip_end=10.5,
        out_path=ass_file,
        max_words=3,
        margin_v=330,
    )
    ass_text = ass_file.read_text(encoding="utf-8")
    assert ",330,1" in ass_text
    dialogue_lines = [ln for ln in ass_text.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue_lines) >= 4

    def to_sec(ts: str) -> float:
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    prev_end = 0.0
    for ln in dialogue_lines:
        parts = ln.split(",", 3)
        st, en = to_sec(parts[1]), to_sec(parts[2])
        assert st >= prev_end - 1e-6
        assert en > st
        prev_end = en

    # WordBoundary grouping produces valid non-overlapping SRT cues.
    wb_srt = _word_events_to_srt(
        [
            {"offset": 1_000_000, "duration": 2_000_000, "text": "Fala"},
            {"offset": 3_100_000, "duration": 2_500_000, "text": "pessoal,"},
            {"offset": 5_700_000, "duration": 2_200_000, "text": "olha"},
            {"offset": 8_000_000, "duration": 2_200_000, "text": "esse"},
            {"offset": 10_300_000, "duration": 3_000_000, "text": "detalhe."},
        ],
        max_words=3,
    )
    parsed_wb = parse_srt(wb_srt)
    assert len(parsed_wb["segments"]) == 2
    assert parsed_wb["segments"][1]["start"] >= parsed_wb["segments"][0]["end"]

    # Weighted fallback covers full audio duration smoothly.
    weighted = _build_weighted_srt("Texto de teste com voz masculina de estudio.", 6.0, max_words=3)
    assert len(parse_srt(weighted)["segments"]) >= 2

    # Clean background resolution prefers _work/source.mp4 over already-subtitled *_short_*.mp4.
    out_dir = tmp_path / "output"
    (out_dir / "_work").mkdir(parents=True)
    raw_src = out_dir / "_work" / "source.mp4"
    raw_src.write_bytes(b"raw")
    (out_dir / "clip_short_01.mp4").write_bytes(b"subbed")
    resolved, has_subs = resolve_background_video("auto", out_dir)
    assert resolved == raw_src
    assert has_subs is False

    # ElevenLabs API optional cascade works cleanly and produces synced SRT.
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el_test_key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHATTERBOX_API_URL", raising=False)
    monkeypatch.setattr("auto_shorts.narrator._probe_media_duration", lambda p, fallback_words=10: 5.5)

    class FakeTTSResp:
        def read(self):
            return b"FAKE_MP3_BYTES"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    seen_headers = {}

    def fake_urlopen(req, timeout=60):
        seen_headers.update(dict(req.headers))
        return FakeTTSResp()

    monkeypatch.setattr("auto_shorts.narrator.urllib.request.urlopen", fake_urlopen)
    mp3_out, srt_out = synthesize_narration("Teste com voz cinematografica.", tmp_path / "tts_out", style_key="narrador_pro")
    assert mp3_out.read_bytes() == b"FAKE_MP3_BYTES"
    assert "Xi-api-key" in seen_headers or "xi-api-key" in {k.lower() for k in seen_headers}
    assert len(parse_srt(srt_out.read_text(encoding="utf-8"))["segments"]) >= 2


def test_zero_pitch_distortion_humanizer_and_validator_gate(tmp_path, monkeypatch):
    # No Edge-TTS style should apply robotic pitch shifting.
    for style in VOICE_STYLES.values():
        assert style.pitch == "+0Hz"

    assert humanize_ptbr_script("Voce nao sabia dessa historia incrivel tambem!") == "Você não sabia dessa história incrível também!"

    bad_srt = tmp_path / "overlap.srt"
    bad_srt.write_text(
        "1\n00:00:00,000 --> 00:00:04,000\nOi\n\n2\n00:00:03,500 --> 00:00:06,000\nSobreposicao\n",
        encoding="utf-8",
    )
    sub_rep = validate_subtitle_file(bad_srt)
    assert sub_rep["overlap_count"] == 1

    fake_mp4 = tmp_path / "short_ok.mp4"
    fake_mp4.write_bytes(b"0" * 120_000)
    fake_mp4.with_name("short_ok_thumb_16x9.jpg").write_bytes(b"JPG")
    fake_mp4.with_suffix(".publish.json").write_text(
        json.dumps({"title": "Titulo Real Testado", "caption": "Resumo legal", "niche": "podcast", "hashtags": ["#Shorts"]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "auto_shorts.validator.inspect_media_metrics",
        lambda p: {
            "duration": 14.5,
            "size_mb": 1.2,
            "size_bytes": 1_200_000,
            "video_codec": "h264",
            "width": 720,
            "height": 1280,
            "fps": 30.0,
            "audio_codec": "aac",
            "sample_rate": 44100,
            "channels": 2,
            "mean_volume_db": -16.2,
            "max_volume_db": -1.4,
        },
    )
    ok_rep = validate_generated_short(fake_mp4)
    assert ok_rep["valid"] is True

    # publish_pack_to_youtube uploads, sets thumb, and records pack["youtube"]
    class FakeResp:
        def __init__(self, body, headers=None):
            self._body = body
            self.headers = headers or {}
        def read(self):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "oauth2.googleapis.com/token" in url:
            return FakeResp(b'{"access_token": "tok"}')
        if "uploadType=resumable" in url:
            return FakeResp(b"", headers={"Location": "https://upload.example.com/s1"})
        if "upload.example.com/s1" in url:
            return FakeResp(b'{"id": "ytPosted1"}')
        if "playlists?part=snippet&mine=true" in url:
            return FakeResp(b'{"items": []}')
        if "playlists?part=snippet,status" in url:
            return FakeResp(b'{"id": "PL1"}')
        if "playlistItems?part=snippet" in url:
            return FakeResp(b'{"id": "PLI1"}')
        if "thumbnails/set" in url:
            return FakeResp(b'{"items": [{"default": {}}]}')
        return FakeResp(b"{}")

    monkeypatch.setenv("YT_CLIENT_ID", "cid")
    monkeypatch.setenv("YT_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YT_REFRESH_TOKEN", "rtok")
    monkeypatch.setattr("auto_shorts.publisher.urllib.request.urlopen", fake_urlopen)

    pub = publish_pack_to_youtube(fake_mp4, playlist_name="Cortes Teste")
    assert pub["video_id"] == "ytPosted1"
    assert pub["thumbnail_uploaded"] is True
    saved = json.loads(fake_mp4.with_suffix(".publish.json").read_text(encoding="utf-8"))
    assert saved["youtube"]["video_id"] == "ytPosted1"
    assert saved["validation"]["valid"] is True

    # Invalid silent/landscape video must be blocked from YouTube upload.
    monkeypatch.setattr(
        "auto_shorts.validator.inspect_media_metrics",
        lambda p: {
            "duration": 14.5, "size_mb": 1.2, "size_bytes": 1_200_000,
            "video_codec": "h264", "width": 1280, "height": 720, "fps": 30.0,
            "audio_codec": "aac", "sample_rate": 44100, "channels": 2,
            "mean_volume_db": -70.0, "max_volume_db": -65.0,
        },
    )
    try:
        publish_pack_to_youtube(fake_mp4)
        assert False, "Should block invalid video from upload"
    except RuntimeError as exc:
        assert "validacao" in str(exc).lower()


def test_full_channel_team_personas_and_weekly_planner(monkeypatch):
    personas = list_channel_personas()
    assert len(personas) == 7
    assert {p["id"] for p in personas} == {
        "trend_hunter",
        "showrunner",
        "screenwriter",
        "thumb_strategist",
        "seo_growth",
        "qa_auditor",
        "channel_manager",
    }

    brief = build_persona_script_brief("Novo episodio de One Piece", niche="entretenimento_animes", platform="youtube_shorts")
    assert brief["target_duration_sec"] == 44
    assert brief["recommended_silence_sec"] == 0.40
    assert len(brief["signed_off_by"]) == 3
    assert "0_a_3s_gancho" in brief["acts"]

    monkeypatch.setattr(
        "auto_shorts.team.get_releasing_anime_radar",
        lambda limit=4: [{"title": "Solo Leveling", "next_episode": 13, "youtube_query": "Solo Leveling episodio 12 teoria"}],
    )
    planner = generate_channel_planner(days=7, include_live_anime=True)
    assert planner["team_size"] == 7
    assert len(planner["schedule"]) == 7
    assert any(s["niche"] == "podcast" for s in planner["schedule"])
    assert any("Solo Leveling" in s["topic"] for s in planner["schedule"])

    doc = render_dashboard_html()
    assert 'id="tab-equipe"' in doc
    assert 'id="panel-equipe"' in doc
    assert 'for="brief-topic"' in doc and 'id="brief-topic"' in doc
    assert "--canvas: #F8FAFC" in doc


def test_gpt_sovits_and_f5_tts_voice_cloning_cascade(tmp_path, monkeypatch):
    class FakeResp:
        def read(self):
            return b"RIFF_FAKE_WAV"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    seen = []

    def fake_urlopen(req, timeout=180):
        seen.append((req.full_url, json.loads(req.data.decode("utf-8"))))
        return FakeResp()

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("auto_shorts.narrator.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("auto_shorts.narrator._wav_bytes_to_mp3", lambda b, out: out.write_bytes(b))
    monkeypatch.setattr("auto_shorts.narrator._probe_media_duration", lambda p, fallback_words=10: 4.5)

    monkeypatch.setenv("GPT_SOVITS_API_URL", "http://127.0.0.1:9880")
    monkeypatch.setenv("GPT_SOVITS_REF_AUDIO", "refs/voz_ref.wav")
    monkeypatch.setenv("GPT_SOVITS_PROMPT_TEXT", "Exemplo real")
    mp3_a, srt_a = synthesize_narration("Teste clonado com GPT-SoVITS!", tmp_path / "gptsovits")
    assert mp3_a.read_bytes() == b"RIFF_FAKE_WAV"
    assert seen[-1][0] == "http://127.0.0.1:9880/tts"
    assert seen[-1][1]["text_lang"] == "pt"
    assert len(parse_srt(srt_a.read_text(encoding="utf-8"))["segments"]) >= 1

    monkeypatch.delenv("GPT_SOVITS_API_URL", raising=False)
    monkeypatch.setenv("F5_TTS_API_URL", "http://127.0.0.1:9881")
    monkeypatch.setenv("F5_TTS_REF_AUDIO", "refs/voz_ref.wav")
    mp3_b, _ = synthesize_narration("Teste fluido com F5-TTS!", tmp_path / "f5")
    assert mp3_b.read_bytes() == b"RIFF_FAKE_WAV"
    assert seen[-1][0] == "http://127.0.0.1:9881/tts"
    assert seen[-1][1]["ref_audio"] == "refs/voz_ref.wav"


def test_youtube_studio_mcp_protocol_and_tools(monkeypatch):
    from auto_shorts.youtube_studio_mcp import handle_mcp_request

    init_resp = handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "youtube-studio-mcp"

    list_resp = handle_mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool_names = {t["name"] for t in list_resp["result"]["tools"]}
    assert {
        "yt_audit_channel",
        "yt_search_competitors",
        "yt_fetch_transcript",
        "yt_anime_release_radar",
        "yt_team_personas_planner",
        "yt_generate_short",
        "yt_validate_and_publish",
    }.issubset(tool_names)

    monkeypatch.setattr("auto_shorts.team.get_releasing_anime_radar", lambda limit=4: [])
    call_resp = handle_mcp_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "yt_team_personas_planner", "arguments": {"topic": "One Piece Episodio 1180", "days": 3}},
    })
    payload = json.loads(call_resp["result"]["content"][0]["text"])
    assert len(payload["personas"]) == 7
    assert len(payload["planner"]["schedule"]) == 3
    assert payload["script_brief"]["niche"] == "podcast"


def test_openrouter_free_cascade_and_local_fallback(monkeypatch):
    from auto_shorts.highlights import call_gemini_or_openai

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")

    seen_models = []

    class FakeLLMResp:
        def __init__(self, body):
            self._body = body
        def read(self):
            return json.dumps(self._body).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=45):
        data = json.loads(req.data.decode("utf-8"))
        seen_models.append((req.full_url, data["model"]))
        # Simulate first candidate returning empty content; cascade must try next :free model.
        if data["model"] == "openrouter/free":
            return FakeLLMResp({"choices": [{"message": {"content": None}}]})
        return FakeLLMResp({"choices": [{"message": {"content": '{"status":"ok"}'}}]})

    monkeypatch.setattr("auto_shorts.highlights.urllib.request.urlopen", fake_urlopen)
    out = call_gemini_or_openai("Retorne JSON")
    assert out == '{"status":"ok"}'
    assert ("https://openrouter.ai/api/v1/chat/completions", "openrouter/free") in seen_models
    assert len(seen_models) >= 2


def test_youtube_algorithm_scorer_and_studio_feed():
    from auto_shorts.yt_algorithm import rank_feed_for_channel, score_short_for_youtube_algorithm
    from auto_shorts.webapp import render_dashboard_html

    strong = score_short_for_youtube_algorithm(
        pack={
            "title": "O segredo oculto do podcast",
            "hook_title": "VOCE VIU ISSO",
            "caption": "Entenda exatamente por que essa cena viralizou em todo o Brasil hoje no podcast! #Shorts",
            "hashtags": ["#Shorts", "#PodcastBrasil", "#Cortes", "#Brasil"],
        },
        validation={"valid": True, "duration": 18.0, "subtitle_cues": 6, "subtitle_overlaps": 0, "mean_volume_db": -16.5},
    )
    assert strong["algo_score"] >= 85
    assert strong["viewed_forecast"] == "75%+ Viewed"
    assert strong["tips"] == []

    weak = score_short_for_youtube_algorithm(
        pack={"title": "Corte generico (1s-45s)", "hook_title": "", "caption": "curto", "hashtags": ["#Shorts"]},
        validation={"valid": False, "duration": 65.0, "subtitle_cues": 0, "subtitle_overlaps": 1},
    )
    assert weak["algo_score"] < 40
    assert len(weak["tips"]) >= 4

    ranked = rank_feed_for_channel([
        {"filename": "b.mp4", "title": "Corte fraco", "validation": {"valid": False}},
        {"filename": "a.mp4", "title": "Segredo forte", "hook_title": "NAO PULE ISSO", "caption": "Contexto detalhado com mais de quarenta caracteres para busca. #Shorts", "hashtags": ["#Shorts", "#A", "#B", "#C"], "validation": {"valid": True, "duration": 16.0, "subtitle_cues": 5, "subtitle_overlaps": 0, "mean_volume_db": -16.0}},
    ])
    assert ranked[0]["filename"] == "a.mp4"
    assert ranked[0]["algorithm"]["algo_score"] > ranked[1]["algorithm"]["algo_score"]

    doc = render_dashboard_html()
    assert 'id="tab-videos"' in doc
    assert 'id="studio-search"' in doc


def test_highlight_sanitizer_rejects_placeholders_and_caps_shorts_duration():
    from auto_shorts.highlights import detect_highlights

    transcript = {
        "duration": 90.0,
        "segments": [
            {"start": 0.0, "end": 18.0, "text": "Como prosperar dez vezes mais rapido aplicando disciplina todo dia."},
            {"start": 18.0, "end": 42.0, "text": "O segredo que quase ninguem aplica na pratica quando comeca um projeto."},
            {"start": 42.0, "end": 75.0, "text": "Comenta aqui qual passo voce vai testar hoje mesmo."},
        ],
    }

    def fake_placeholder_llm(_prompt):
        return json.dumps({
            "highlights": [{
                "title": "string",
                "hook_title": "STRING CURTA",
                "start_time": 0.0,
                "end_time": 65.0,
                "score": 90,
                "virality_reason": "string",
                "cta_line": "string",
            }]
        })

    clips = detect_highlights(
        transcript,
        platform_key="youtube_shorts",
        niche_key="podcast",
        num_clips=1,
        llm_fn=fake_placeholder_llm,
        use_llm=True,
        source_title="Como prosperar mais rapido no Podcast",
    )
    assert len(clips) == 1
    assert clips[0]["title"].lower() != "string"
    assert clips[0]["hook_title"] != "STRING CURTA"
    assert clips[0]["end_time"] - clips[0]["start_time"] <= 57.0


def test_wifi_resilience_pwa_manifest_and_c_runner_sources(monkeypatch):
    from auto_shorts import webapp

    def fail_conn(_target, timeout=2.5):
        raise OSError("network unreachable")

    monkeypatch.setattr("auto_shorts.webapp.socket.create_connection", fail_conn)
    assert webapp._has_internet(timeout=0.1) is False

    root = Path(__file__).resolve().parents[1]
    c_src = (root / "native-c" / "autoshorts.c").read_text(encoding="utf-8")
    h_src = (root / "native-c" / "mp4_audit.h").read_text(encoding="utf-8")
    assert "is_internet_online" in c_src
    assert "cmd_watch" in c_src
    assert "mp4_audit_and_print" in h_src


def test_youtube_rolling_vtt_no_duplicates_bpe_and_hook_wrap(tmp_path):
    from auto_shorts.transcript import parse_vtt, parse_whisper_cpp_json
    from auto_shorts.silence import remap_transcript_segments
    from auto_shorts.renderer import _format_hook_banner

    vtt = """WEBVTT
Kind: captions
Language: pt

00:00:01.400 --> 00:00:03.110 align:start position:0%
 
o<00:00:01.560><c> que</c><00:00:01.720><c> cada</c><00:00:02.040><c> trabalhava</c>

00:00:03.110 --> 00:00:03.120 align:start position:0%
o que cada trabalhava
 

00:00:03.120 --> 00:00:05.670 align:start position:0%
o que cada trabalhava
cara<00:00:04.200><c> eu</c><00:00:04.400><c> venci</c><00:00:05.000><c> [&nbsp;__&nbsp;]</c><00:00:05.400><c> tudo</c>

00:00:05.670 --> 00:00:05.680 align:start position:0%
cara eu venci tudo
"""
    parsed = parse_vtt(vtt)
    full_txt = " ".join(s["text"] for s in parsed["segments"])
    assert full_txt.count("o que cada trabalhava") == 1
    assert full_txt.count("cara eu venci tudo") == 1
    assert "__" not in full_txt and "&nbsp;" not in full_txt
    assert parsed["segments"][0]["words"][1]["word"] == "que"

    # Splitting across silence gap must NOT duplicate words or sentence text
    remapped = remap_transcript_segments(parsed["segments"], [(0.0, 2.8), (3.5, 6.0)])
    rem_txt = " ".join(s["text"] for s in remapped)
    assert rem_txt.count("trabalhava") == 1
    assert rem_txt.count("venci") == 1

    # BPE subwords from whisper.cpp -ojf must stay merged into whole words
    wjson = json.dumps({
        "transcription": [{
            "offsets": {"from": 0, "to": 2000},
            "text": " Eu trabalhei muito",
            "tokens": [
                {"text": " Eu", "offsets": {"from": 100, "to": 300}},
                {"text": " trabal", "offsets": {"from": 310, "to": 700}},
                {"text": "hei", "offsets": {"from": 700, "to": 1000}},
                {"text": " muito", "offsets": {"from": 1010, "to": 1600}},
            ],
        }]
    })
    wp = parse_whisper_cpp_json(wjson)
    assert [w["word"] for w in wp["segments"][0]["words"]] == ["Eu", "trabalhei", "muito"]

    # Word-synced ASS must produce clean whole words
    ass_path = tmp_path / "synced.ass"
    generate_ass_subtitles(wp["segments"], 0.0, 2.0, ass_path)
    ass_txt = ass_path.read_text(encoding="utf-8")
    assert "TRABALHEI" in ass_txt

    # Hook banner must wrap cleanly into 2 balanced lines
    banner, longest = _format_hook_banner("SHOPPING MUITO TEMPO SEM GANHAR DINHEIRO")
    assert "\n" in banner
    assert longest <= 20


def test_world_news_public_apis_and_security_hardening(tmp_path, monkeypatch):
    from auto_shorts.world_news import build_brazil_news_story_pack, fetch_world_news_headlines
    from auto_shorts.narrator import resolve_background_video
    from auto_shorts.webapp import _is_safe_public_http_url, _safe_child_path, render_dashboard_html
    from auto_shorts.youtube_studio_mcp import handle_mcp_request

    rss_sample = """<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Global chip market surges</title><description>New mobile processors break records.</description><link>https://feeds.bbci.co.uk/news/world-1</link><media:thumbnail url="https://ichef.bbci.co.uk/ace/ws/240/test.jpg"/></item></channel></rss>"""
    sf_sample = json.dumps({"results": [{"title": "Rocket launches satellite", "summary": "Orbital mission succeeds.", "url": "https://spaceflightnewsapi.net/1", "news_site": "Spaceflight"}]})

    def fake_fetch(url):
        if "portuguese" in url or "euronews" in url:
            return """<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Acordo internacional muda regras de energia</title><description>Decisao impacta mercados globais.</description><link>https://feeds.bbci.co.uk/portuguese/1</link><media:thumbnail url="https://ichef.bbci.co.uk/ace/ws/240/br.jpg"/></item></channel></rss>"""
        if "bbci.co.uk/news" in url or "theguardian.com" in url:
            return rss_sample
        if "spaceflightnewsapi" in url:
            return sf_sample
        return "{}"

    headlines = fetch_world_news_headlines(topic="world", limit=6, fetcher=fake_fetch)
    assert len(headlines) >= 2
    assert headlines[0]["image_url"] == "https://ichef.bbci.co.uk/ace/ws/800/br.jpg"
    en_story = next(h for h in headlines if h.get("lang") == "en")

    # Never hijack an already-rendered anime clip when selecting "auto" background
    out_fake = tmp_path / "output"
    out_fake.mkdir()
    (out_fake / "vPGK2BGblRU_short_01_youtube_shorts.mp4").write_bytes(b"anime")
    monkeypatch.setattr("auto_shorts.narrator.subprocess.run", lambda cmd, check=True: Path(cmd[-1]).write_bytes(b"clean_bg"))
    bg_chosen, _ = resolve_background_video("auto", out_fake)
    assert bg_chosen.name == "clean_studio_bg.mp4"

    pack = build_brazil_news_story_pack(
        en_story,
        use_llm=False,
        translator=lambda t: f"Traduzido PT-BR: {t}",
    )
    assert "Traduzido PT-BR:" in pack["caption"]
    assert "https://feeds.bbci.co.uk/news/world-1" in pack["caption"]
    assert "#NoticiasMundiais" in pack["hashtags"]
    assert "link recomendado no comentario fixado" not in pack["caption"].lower()

    # SSRF / CLI-option-injection / path-traversal checks
    assert _is_safe_public_http_url("https://www.youtube.com/watch?v=123") is True
    assert _is_safe_public_http_url("http://127.0.0.1:8787/secret") is False
    assert _is_safe_public_http_url("http://169.254.169.254/latest/meta-data") is False
    assert _is_safe_public_http_url("file:///etc/passwd") is False
    assert _is_safe_public_http_url("--exec=whoami") is False
    assert _safe_child_path(Path("."), "../../etc/passwd") is None
    assert _safe_child_path(Path("."), "video_01.mp4") is not None

    list_resp = handle_mcp_request({"jsonrpc": "2.0", "id": 9, "method": "tools/list"})
    assert "yt_world_news_brazil" in {t["name"] for t in list_resp["result"]["tools"]}
    assert 'id="btn-world-news"' in render_dashboard_html()


def test_motor_v2_ptbr_english_detection_hook_polish_and_pack_healer(tmp_path, monkeypatch):
    from auto_shorts.highlights import _looks_english_title, _polish_hook_phrase
    from auto_shorts.publisher import optimize_existing_publish_pack

    assert _looks_english_title("LUFFY'S MOST DEVASTATING PUNCH REVEALED!!! ONE PIECE 1192") is True
    assert _looks_english_title("HE WENT TO CRITICIZE CHINA AND GOT A REALITY CHECK") is True
    assert _looks_english_title("7 TEORIAS CHOCANTES QUE VAI MUDAR TUDO EM BLEACH") is False

    hook = _polish_hook_phrase(["dele", "nesse", "arco", "luffy", "maior"])
    assert not hook.startswith("DELE")
    assert not hook.endswith("MAIOR")

    anime_pack = build_publish_pack(
        {"title": "A Nova Forma do Luffy", "hook_title": "PODER DO LUFFY"},
        "youtube_shorts",
        "entretenimento_animes",
    )
    assert len(anime_pack["hashtags"]) <= 5
    assert "#Shorts" in anime_pack["hashtags"]

    # Self-heal orphaned or 6-tag MP4 package
    mp4 = tmp_path / "orphan_clip_short_01.mp4"
    mp4.write_bytes(b"\x00" * 60000)
    monkeypatch.setattr(
        "auto_shorts.validator.validate_generated_short",
        lambda p, ass_path=None: {
            "valid": True, "errors": [], "warnings": [],
            "duration": 44.0, "resolution": "720x1280", "fps": 24.0,
            "mean_volume_db": -17.0, "subtitle_cues": 20, "subtitle_overlaps": 0,
        },
    )
    monkeypatch.setattr("auto_shorts.highlights._translate_title_to_ptbr", lambda t: "A Crítica na China e o Choque de Realidade")
    mp4.with_suffix(".publish.json").write_text(
        json.dumps({
            "title": "HE WENT TO CRITICIZE CHINA AND GOT A REALITY CHECK",
            "hook_title": "IMU FINALMENTE CONSEGUE SE",
            "hashtags": ["#anime", "#manga", "#teoria", "#otaku", "#animesbrasil", "#Shorts"],
            "niche": "entretenimento_animes",
            "caption": "Contexto detalhado com mais de quarenta caracteres para YouTube Search.",
        }),
        encoding="utf-8",
    )
    healed = optimize_existing_publish_pack(mp4)
    assert len(healed["hashtags"]) == 5
    assert "China" in healed["title"]
    assert not healed["hook_title"].endswith(" SE")
    assert healed["algorithm"]["algo_score"] == 100


def test_human_tts_cascade_kokoro_fish_and_speech_normalization(tmp_path, monkeypatch):
    from auto_shorts.narrator import _prepare_speech_text, active_tts_engine_label

    normalized = _prepare_speech_text("Veja R$ 275 mil e 75% de alta — saiba mais em https://exemplo.com/noticia!")
    assert "275 reais" in normalized
    assert "75 por cento" in normalized
    assert "https://" not in normalized

    assert VOICE_STYLES["thalita_hd"].voice == "pt-BR-ThalitaMultilingualNeural"
    assert VOICE_STYLES["kokoro_alex"].kokoro_voice == "pm_alex"

    # Verify Fish Speech S1/S2 HTTP bridge takes priority when configured
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
    assert "Fish Speech" in active_tts_engine_label()
    monkeypatch.setattr("auto_shorts.narrator._synthesize_fish_audio", lambda txt, out, st, api_key="", api_url="": out.write_bytes(b"ID3" + b"\x00" * 500) is not None)
    monkeypatch.setattr("auto_shorts.narrator._probe_media_duration", lambda p, fallback_words=10: 5.0)
    mp3_f, srt_f = synthesize_narration("Ganho de 50% hoje.", tmp_path / "fish_out", style_key="thalita_hd")
    assert mp3_f.is_file() and mp3_f.stat().st_size > 100
    assert srt_f.is_file() and "por cento" not in srt_f.read_text(encoding="utf-8")

    # Verify local Kokoro-82M ONNX offline engine label & fallback path
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    m_file = tts_dir / "kokoro-v1.0.int8.onnx"
    v_file = tts_dir / "voices-v1.0.bin"
    m_file.write_bytes(b"onnx")
    v_file.write_bytes(b"voices")
    monkeypatch.setenv("KOKORO_MODEL_PATH", str(m_file))
    monkeypatch.setenv("KOKORO_VOICES_PATH", str(v_file))
    assert "Kokoro-82M" in active_tts_engine_label()
    monkeypatch.setattr("auto_shorts.narrator._synthesize_kokoro_onnx", lambda txt, out, st: out.write_bytes(b"ID3" + b"\x00" * 500) is not None)
    mp3_k, _ = synthesize_narration("Teste Kokoro natural.", tmp_path / "kokoro_out", style_key="kokoro_alex")
    assert mp3_k.is_file()

    # Verify real-time ASS karaoke highlighting when word timestamps exist
    k_ass = tmp_path / "karaoke.ass"
    generate_ass_subtitles(
        [{"start": 0.0, "end": 1.8, "text": "Poder oculto", "words": [{"start": 0.1, "end": 0.6, "word": "Poder"}, {"start": 0.7, "end": 1.5, "word": "oculto"}]}],
        0.0, 2.0, k_ass,
    )
    ass_txt = k_ass.read_text(encoding="utf-8")
    assert ",Karaoke,," in ass_txt
    assert r"{\k" in ass_txt


def test_synapse_cinema_filter_and_youtube_most_replayed_heatmap():
    vf = build_video_filter("blur_bg", 720, 1280, hook_title="SEGREDO REVELADO", font_path="/tmp/font.ttf")
    assert "eq=contrast=1.06:saturation=1.14" in vf
    assert "0xFACC15" in vf

    # YouTube Most Replayed heatmap peak should promote the 2nd window over an unheated 1st window
    transcript = {
        "duration": 100.0,
        "segments": [
            {"start": 0.0, "end": 42.0, "text": "Introducao calma sobre economia e assunto geral."},
            {"start": 45.0, "end": 88.0, "text": "Revelacao absurda que chocou todo mundo ao vivo!"},
        ],
    }
    heatmap = [
        {"start_time": 0.0, "end_time": 42.0, "value": 0.15},
        {"start_time": 45.0, "end_time": 88.0, "value": 0.96},
    ]
    picked = detect_highlights(
        transcript,
        platform_key="youtube_shorts",
        niche_key="podcast",
        num_clips=1,
        use_llm=False,
        heatmap=heatmap,
    )
    assert len(picked) == 1
    assert picked[0]["start_time"] == 45.0
    assert "Most Replayed 96%" in picked[0]["virality_reason"]


def test_horizon_radar_opens_all_niches_and_webapp_has_explorer():
    from auto_shorts.horizon_radar import fetch_horizon_trends

    res = fetch_horizon_trends(
        horizon="todos",
        limit=10,
        news_fetcher=lambda t, l: [{"title": "IA revoluciona mercado", "url": "https://bbc.com/1", "source": "BBC"}],
        anime_fetcher=lambda l: [{"title": "Solo Leveling", "youtube_query": "solo leveling teoria"}],
    )
    horizons = {c["horizon"] for c in res["items"]}
    assert "podcast_debates" in horizons
    assert "dinheiro_ia" in horizons
    assert "psicologia_misterios" in horizons
    assert "saude_treino" in horizons
    html = render_dashboard_html()
    assert 'id="btn-horizon-radar"' in html
    assert 'id="btn-start-tunnel"' in html


def test_synced_jump_cut_and_clean_overlay_without_giant_bands(tmp_path):
    from auto_shorts.renderer import build_jump_cut_filter

    vf = build_video_filter("blur_bg", 720, 1280, ass_path=tmp_path / "c.ass", hook_title="TESTE", font_path="/tmp/f.ttf")
    assert "w=iw:" not in vf
    assert "0xFACC15" in vf
    assert "setsar=1" in vf

    jg = build_jump_cut_filter([(0.12, 3.45), (4.80, 9.10)])
    assert "select='" in jg
    assert "aselect='" in jg
    assert "setpts=N/30/TB" in jg
    assert "asetpts=N/44100/TB" in jg


def test_compact_subtitles_chunked_kokoro_gameplay_and_horizon_script(tmp_path, monkeypatch):
    from auto_shorts.gameplay import gameplay_cache_dir, list_gameplay_clips
    from auto_shorts.horizon_radar import build_horizon_spoken_script
    from auto_shorts.narrator import VOICE_STYLES, _split_tts_chunks, _synthesize_kokoro_onnx

    # 1. Subtitles must be crisp & compact (never giant 46px middle-of-screen text)
    compact_ass = tmp_path / "compact.ass"
    generate_ass_subtitles(
        [{"start": 0.0, "end": 2.4, "text": "Tres palavras limpas"}],
        0.0, 2.5, compact_ass, width=720, height=1280,
    )
    ass_raw = compact_ass.read_text(encoding="utf-8")
    assert "Style: Karaoke,DejaVu Sans,30," in ass_raw
    assert ",190,1" in ass_raw

    # 2. Kokoro chunking must split long scripts (>210 chars) so audio never truncates at 13.71s
    long_script = ". ".join([f"Frase numero {i} explicando uma descoberta financeira importante no Brasil" for i in range(1, 10)]) + "."
    chunks = _split_tts_chunks(long_script, max_chars=210)
    assert len(chunks) >= 3
    assert all(len(c) <= 210 for c in chunks)

    # 3. Horizon spoken script must be 60+ words and never speak meta why_viral notes
    spoken = build_horizon_spoken_script(
        {
            "horizon": "dinheiro_ia",
            "title_pt": "Erros invisiveis que corroem salario, juros e investimentos",
            "hook_suggestion": "O ERRO QUE CUSTA SEU SALARIO",
            "why_viral": "Aversão à perda — o cérebro presta atenção imediata quando sente risco financeiro.",
            "source": "Radar Financas",
        },
        use_llm=False,
    )
    assert len(spoken.split()) >= 60
    assert "Aversão à perda" not in spoken
    assert ".gguf" not in spoken.lower()
    assert "/data/" not in spoken.lower()

    # 4. Gameplay cache folder rotates across distinct games without repeating consecutively
    out_fake = tmp_path / "output"
    out_fake.mkdir()
    gp_dir = gameplay_cache_dir(out_fake)
    (gp_dir / "gp_minecraft_demo.mp4").write_bytes(b"0" * 250_000)
    (gp_dir / "gp_subway_demo.mp4").write_bytes(b"0" * 250_000)
    found = list_gameplay_clips(out_fake)
    assert len(found) == 2
    from auto_shorts.gameplay import pick_gameplay_segment
    g1, _ = pick_gameplay_segment(out_fake, auto_download=False)
    g2, _ = pick_gameplay_segment(out_fake, auto_download=False)
    assert g1.name != g2.name


def test_multimodal_auto_validator_approves_motion_and_rejects_blank_or_garbage(tmp_path):
    import shutil
    import subprocess
    from auto_shorts.validator import _extract_raw_gray_stats, audit_short_end_to_end

    # Pure-Python pixel brightness/contrast math check (runs on any host)
    low_m, low_s = _extract_raw_gray_stats(bytes([5] * 4096))
    assert low_m < 12.0 and low_s == 0.0
    varied_m, varied_s = _extract_raw_gray_stats(bytes([i % 256 for i in range(4096)]))
    assert 100.0 <= varied_m <= 150.0 and varied_s > 40.0

    good_mp4 = tmp_path / "narrated_ok_01.mp4"
    if shutil.which("ffmpeg"):
        # 1. Real moving 720x1280 18s MP4 with audible sine audio -> APPROVE
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=18",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=18",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", "44100",
                str(good_mp4),
            ],
            check=True,
        )
        ok_res = audit_short_end_to_end(
            good_mp4,
            pack={"title": "Dica de Produtividade", "hook_title": "PRODUTIVIDADE REAL", "caption": "Texto limpo PT-BR sobre eficiencia.\n#Shorts"},
            vision_check=False,
        )
        assert ok_res["approved"] is True
        assert ok_res["decision"] == "APPROVE"
        assert ok_res["visual"]["has_motion"] is True

        # 2. Solid blank black screen -> REJECT
        bad_blank = tmp_path / "cut_blank_01.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=0x050810:s=720x1280:r=24:d=18",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=18",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", "44100",
                str(bad_blank),
            ],
            check=True,
        )
        rej_blank = audit_short_end_to_end(
            bad_blank,
            pack={"title": "Tela Parada", "hook_title": "TESTE", "caption": "Ok"},
            vision_check=False,
        )
        assert rej_blank["approved"] is False
        assert rej_blank["decision"] == "REJECT"
    else:
        good_mp4.write_bytes(b"0" * 120_000)

    # 3. Leaked model path / garbage in copy -> REJECT on all platforms
    stub_val = {
        "valid": True, "errors": [], "warnings": [], "duration": 22.0, "resolution": "720x1280",
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac", "sample_rate": 44100,
        "mean_volume_db": -16.5, "max_volume_db": -2.0, "subtitle_cues": 10, "subtitle_overlaps": 0, "size_mb": 1.2,
    }
    ok_stub = audit_short_end_to_end(
        good_mp4,
        pack={"title": "Dica Real", "hook_title": "DICA REAL", "caption": "Texto natural PT-BR.\n#Shorts"},
        vision_check=False,
        media_val=stub_val,
    )
    assert ok_stub["approved"] is True

    rej_leak = audit_short_end_to_end(
        good_mp4,
        pack={"title": "Teste", "hook_title": "PATH", "caption": "carregando /data/data/com.termux/qwen.gguf"},
        vision_check=False,
        media_val=stub_val,
    )
    assert rej_leak["approved"] is False
    assert rej_leak["decision"] == "REJECT"
    assert any(".gguf" in r or "/data/data/" in r for r in rej_leak["reject_reasons"])

    # 4. Leaked LLM prompt-thinking English words inside PT-BR Short -> REJECT (zero false positive)
    rej_meta = audit_short_end_to_end(
        good_mp4,
        pack={"title": "Saude Hoje", "hook_title": "MUDE ISSO", "caption": 'Need craft spoken text. They ask: "Voce sabia?"\n#Shorts'},
        vision_check=False,
        media_val=stub_val,
    )
    assert rej_meta["approved"] is False
    assert rej_meta["decision"] == "REJECT"

    # 5. Adaptive UCB1 background evolution & Rich Topic Cards UI
    from auto_shorts.evolution import EvolutionStore
    from auto_shorts.gameplay import discover_dynamic_visual_queries, gameplay_cache_dir, pick_evolving_background

    store = EvolutionStore(tmp_path / "evo.db")
    store.record_background_outcome("financas", "finance_minimal", quality_score=94.0, views=4200, avg_watch_pct=88.0)
    store.record_background_outcome("financas", "subway", quality_score=72.0, views=400, avg_watch_pct=52.0)
    picked_style = store.select_evolving_background_style("financas", ["finance_minimal", "subway"], last_style="subway")
    assert picked_style == "finance_minimal"

    dyn_slug, dyn_queries = discover_dynamic_visual_queries("ia_tech", "Energia Solar Espacial")
    assert dyn_slug.startswith("adaptive_") and len(dyn_queries) >= 2

    out_evo = tmp_path / "out_evo"
    out_evo.mkdir()
    gdir = gameplay_cache_dir(out_evo)
    (gdir / "gp_drone_cinema_1.mp4").write_bytes(b"0" * 250_000)
    (gdir / "gp_space_cosmos_2.mp4").write_bytes(b"0" * 250_000)
    e1 = pick_evolving_background(out_evo, niche="ia_tech", auto_download=False)
    e2 = pick_evolving_background(out_evo, niche="ia_tech", auto_download=False)
    assert e1 is not None and e2 is not None and e1[2] != e2[2]

    html = render_dashboard_html()
    assert "topic-card" in html
    assert "buildTopicMediaNode" in html


def test_rich_feeds_cards_ui_pro_max_and_telemetry(monkeypatch):
    from auto_shorts.anime_trends import get_releasing_anime_radar
    from auto_shorts.horizon_radar import fetch_horizon_trends
    from auto_shorts.world_news import fetch_world_news_headlines

    g1_rss = (
        '<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel>'
        '<item><title>Nova IA brasileira acelera industria</title>'
        '<description>Modelo aberto reduz custos de nuvem.</description>'
        '<link>https://g1.globo.com/tecnologia/1</link>'
        '<media:content url="https://s2-g1.glbimg.com/tech1.jpg"/></item></channel></rss>'
    )
    sf_json = json.dumps({
        "results": [{
            "title": "New orbital station reaches orbit",
            "summary": "Commercial flight test completes safely.",
            "url": "https://spaceflightnewsapi.net/article/99",
            "image_url": "https://cdn.spaceflight.org/rocket99.jpg",
            "news_site": "Spaceflight",
        }]
    })

    def fake_news_fetch(url):
        if "g1.globo.com" in url:
            return g1_rss
        if "spaceflightnewsapi" in url:
            return sf_json
        return ""

    news = fetch_world_news_headlines(topic="world", limit=10, fetcher=fake_news_fetch)
    assert any(h.get("image_url") == "https://cdn.spaceflight.org/rocket99.jpg" for h in news)
    assert any("g1.globo.com" in str(h.get("url", "")) for h in news)

    anilist_payload = {
        "data": {
            "Page": {
                "media": [{
                    "id": 21,
                    "title": {"romaji": "Solo Leveling", "english": "Solo Leveling"},
                    "popularity": 195000,
                    "averageScore": 87,
                    "episodes": 12,
                    "genres": ["Action", "Fantasy"],
                    "coverImage": {"large": "https://s4.anilist.co/solo.jpg"},
                    "nextAiringEpisode": {"episode": 11, "timeUntilAiring": 7200},
                }]
            }
        }
    }

    class FakeAnimeResp:
        def __init__(self, body: bytes):
            self._body = body
        def read(self):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=12):
        url = getattr(req, "full_url", str(req))
        if "jikan" in url:
            return FakeAnimeResp(json.dumps({"data": []}).encode("utf-8"))
        return FakeAnimeResp(json.dumps(anilist_payload).encode("utf-8"))

    monkeypatch.setattr("auto_shorts.anime_trends.urllib.request.urlopen", fake_urlopen)
    animes = get_releasing_anime_radar(limit=14)
    assert len(animes) >= 1
    assert animes[0]["score"] == 87
    assert animes[0]["image_url"] == "https://s4.anilist.co/solo.jpg"

    res = fetch_horizon_trends(
        horizon="todos",
        limit=18,
        news_fetcher=lambda t, l: [{
            "title": "New AI chip breaks speed record",
            "url": "https://example.com/news1",
            "source": "BBC World",
            "image_url": "https://example.com/news1.jpg",
            "lang": "en",
        }],
        anime_fetcher=lambda l: animes,
        include_live_youtube=False,
    )
    items = res["items"]
    assert any(c.get("category_kind") == "noticia" and c.get("image_url") == "https://example.com/news1.jpg" for c in items)
    assert any(c.get("category_kind") == "anime" and "Nota 87%" in str(c.get("metric_badge", "")) and c.get("image_url") == "https://s4.anilist.co/solo.jpg" for c in items)
    assert all(c.get("metric_badge") and c.get("rpm_hint") for c in items)

    html = render_dashboard_html()
    assert 'id="kpi-strip"' in html
    assert "filter-chips" in html
    assert "buildTopicMediaNode" in html
    assert "meta-fold" in html


def test_multi_category_animes_mobile_ui_and_synapse_re_engine(tmp_path, monkeypatch):
    from auto_shorts.anime_trends import get_releasing_anime_radar
    from auto_shorts.re_engine import (
        analyze_kinetic_pacing,
        get_synapse_overview,
        inspect_youtube_innertube,
        rea_trace_system,
        record_synapse_stage,
    )

    # 1. Multi-category AniList radar: airing, famous of year, top liked season, upcoming
    def fake_ql(req, timeout=12):
        url = getattr(req, "full_url", str(req))
        if "jikan" in url:
            payload = {"data": []}
        else:
            body = json.loads(req.data.decode("utf-8"))
            v = body.get("variables") or {}
            status = v.get("status")
            if status == "NOT_YET_RELEASED":
                title, yr = "Witch Hat Atelier", 2026
            elif v.get("season"):
                title, yr = "Frieren Season 2", 2026
            elif v.get("seasonYear"):
                title, yr = "Jujutsu Kaisen Year", 2026
            else:
                title, yr = "One Piece Airing", 2026
            payload = {
                "data": {
                    "Page": {
                        "media": [{
                            "id": 77,
                            "title": {"romaji": title, "english": title},
                            "popularity": 250000,
                            "trending": 1800,
                            "favourites": 34000,
                            "averageScore": 91,
                            "episodes": 24,
                            "season": "SPRING",
                            "seasonYear": yr,
                            "genres": ["Action", "Adventure"],
                            "coverImage": {"large": "https://s4.anilist.co/cover.jpg"},
                            "nextAiringEpisode": {"episode": 12, "timeUntilAiring": 3600} if status == "RELEASING" else None,
                        }]
                    }
                }
            }

        class Resp:
            def read(self):
                return json.dumps(payload).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        return Resp()

    monkeypatch.setattr("auto_shorts.anime_trends.urllib.request.urlopen", fake_ql)
    all_animes = get_releasing_anime_radar(limit=20, category="all")
    cats = {a.get("anime_category") for a in all_animes}
    assert {"em_exibicao", "famosos_ano", "mais_curtidos", "proximos"} <= cats
    upcoming = get_releasing_anime_radar(limit=5, category="proximos")
    assert upcoming and upcoming[0]["anime_category"] == "proximos"

    # 2. InnerTube Heatmap Reverse Engineering + Kinetic Pacing + REA Trace + Synapse
    fake_watch = (
        '<html><script>var ytInitialPlayerResponse = {"videoDetails":'
        '{"videoId":"dQw4w9WgXcQ","title":"Podcast IA","author":"Canal Tech","lengthSeconds":"600","viewCount":"95000"}};</script>'
        '<script>var ytInitialData = {"overlay":{"heatMarkerRenderer":{"timeRangeStartMillis":142000,"markerDurationMillis":8000,"heatMarkerIntensityScoreNormalized":0.94}}};</script></html>'
    )
    it = inspect_youtube_innertube("https://www.youtube.com/watch?v=dQw4w9WgXcQ", fetcher=lambda u: fake_watch)
    assert it["ok"] is True
    assert it["heatmap_points"] == 1
    assert it["peaks"][0]["intensity_pct"] == 94.0

    pacing = analyze_kinetic_pacing("Palavra " * 110, duration_sec=36.0)
    assert pacing["cadence_status"] == "ideal_shorts"
    assert pacing["visual_beats_3s"] == 12

    tr = rea_trace_system("moov")
    assert tr["ok"] is True and tr["total_hits"] >= 1
    assert any(m["layer"] == "c11_native" for m in tr["matches"])

    record_synapse_stage(tmp_path, "tts_kokoro", 420.5, ok=True)
    ov = get_synapse_overview(tmp_path)
    assert ov["immunity_count"] >= 6
    assert any(s["stage"] == "tts_kokoro" and s["p50_ms"] == 420.5 for s in ov["stage_latencies"])

    # 3. Mobile-Responsive Studio CSS + Synapse Tab + Anime Filters
    html = render_dashboard_html()
    assert 'class="mobile-nav"' in html
    assert "@media (max-width: 768px)" in html
    assert 'id="tab-synapse"' in html and 'id="panel-synapse"' in html
    assert 'id="anime-cat-chips"' in html


def test_github_upgrades_karaoke_kf_face_crop_innertube_and_instagram_reels(tmp_path):
    from auto_shorts.publisher import publish_pack_to_instagram_reels
    from auto_shorts.re_engine import call_innertube_player, get_synapse_overview
    from auto_shorts.subtitles import generate_ass_subtitles

    ass_kf = tmp_path / "kf.ass"
    generate_ass_subtitles(
        [{"start": 0.0, "end": 3.0, "text": "Isso muda todo o jogo agora"}],
        clip_start=0.0,
        clip_end=3.0,
        out_path=ass_kf,
        max_words=3,
    )
    ass_txt = ass_kf.read_text(encoding="utf-8")
    assert r"{\kf" in ass_txt or r"\kf" in ass_txt
    assert "Karaoke" in ass_txt

    vf_face = build_video_filter("center_crop", 720, 1280, focus_x=0.25)
    assert "iw*0.250-ow/2" in vf_face

    captured = {}

    def fake_post(url, body):
        captured["url"] = url
        captured["client"] = body["context"]["client"]["clientName"]
        return {"videoDetails": {"videoId": "abc12345678", "title": "InnerTube Demo"}}

    it_res = call_innertube_player("abc12345678", poster=fake_post)
    assert captured["client"] == "ANDROID"
    assert it_res["videoDetails"]["title"] == "InnerTube Demo"

    ov = get_synapse_overview(tmp_path)
    assert ov["immunity_count"] >= 9

    fake_mp4 = tmp_path / "reel.mp4"
    fake_mp4.write_bytes(b"ftypmp42" + b"0" * 100)
    ig = publish_pack_to_instagram_reels(fake_mp4, username="", password="")
    assert ig["status"] == "skipped_unconfigured"


def test_opus_pro_caption_hold_signalstats_and_runbook_scorecard(tmp_path):
    from auto_shorts.re_engine import get_synapse_overview, score_short_opus_runbook
    from auto_shorts.subtitles import generate_ass_subtitles
    from auto_shorts.validator import inspect_ffmpeg_signalstats

    # 1. OpusClip caption_cues clause split + 0.50s anti-flicker bridge vs >0.50s clear pause
    ass_path = tmp_path / "opus_hold.ass"
    generate_ass_subtitles(
        [
            {"start": 0.0, "end": 1.0, "text": "Primeiro bloco."},
            {"start": 1.25, "end": 2.4, "text": "Segundo bloco continua"},
            {"start": 3.6, "end": 4.8, "text": "Pausa longa antes"},
        ],
        clip_start=0.0,
        clip_end=5.0,
        out_path=ass_path,
        max_words=4,
    )
    dlg = [ln for ln in ass_path.read_text(encoding="utf-8").splitlines() if ln.startswith("Dialogue:")]
    assert len(dlg) == 3
    # Cue 0 end should hold seamlessly up to Cue 1 start (0:00:01.25) since gap was 0.25s <= 0.50s
    assert "0:00:01.25,Karaoke" in dlg[0]

    # 2. OpusClip reel-runbook calibrated 0-100 scorecard
    sc_good = score_short_opus_runbook(
        {
            "hook_title": "O SEGREDO QUE MUDA TUDO",
            "caption": "Entenda porque esse detalhe muda seu dia.",
            "background_style": "minecraft+subway",
            "visual_audit": {"visual": {"luma_std": 42.0, "motion_delta": 24.0}},
        },
        validation={"duration": 34.0, "subtitle_cues": 20, "mean_volume_db": -16.8, "subtitle_overlaps": 0},
    )
    assert sc_good["opus_score"] >= 70
    assert "ESCALAR" in sc_good["band"]

    # 3. FFmpeg signalstats safe empty dict on small/non-ftyp stubs + 10 Dharma immunities
    stub = tmp_path / "stub.mp4"
    stub.write_bytes(b"0" * 100)
    assert inspect_ffmpeg_signalstats(stub) == {}
    assert get_synapse_overview(tmp_path)["immunity_count"] >= 10

    # 4. Refactored modular frontend contract + live 5-stage render stepper + inspector dialog + UX upgrades
    dash = render_dashboard_html()
    for token in (
        'id="render-bar"', 'id="render-fill"', 'id="render-badge"', 'class="stage-pills"',
        'id="short-inspector-dlg"', 'id="toast-stack"', 'id="floating-render-dock"',
        'class="side-rail"', 'class="layout-picker"', 'id="phone-preview-bg"',
        'id="preview-hook-title"', 'id="voice-pace-meta"', 'id="mode-radar-horizon"',
        'id="btn-radar-more"', 'id="acervo-filter-chips"',
    ):
        assert token in dash, f"Missing refactored UI element: {token}"


def test_webapp_no_store_cache_headers_and_horizon_fallback(tmp_path, monkeypatch):
    import threading
    import urllib.request
    from auto_shorts import webapp

    def boom_horizon(**kwargs):
        raise RuntimeError("transient network error")

    monkeypatch.setattr("auto_shorts.webapp.fetch_horizon_trends", boom_horizon)
    srv = webapp._StudioHTTPServer(("127.0.0.1", 0), webapp.make_handler(tmp_path))
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5)
        cc = r.headers.get("Cache-Control", "")
        assert "no-store" in cc and "no-cache" in cc
        assert r.headers.get("Pragma") == "no-cache"

        r2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/horizon?topic=todos", timeout=5)
        body = json.loads(r2.read().decode("utf-8"))
        assert body["horizon"] == "todos"
        assert body["items"] == []
        assert "transient network error" in body["error"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_offline_llm_title_hygiene_and_v1_endpoints(tmp_path):
    from auto_shorts.highlights import _clean_source_title, _looks_english_title, _polish_hook_phrase
    from auto_shorts.offline_llm import (
        answer_studio_question_offline,
        benchmark_local_llm,
        bm25_search_shorts,
        detect_android_llm_capabilities,
        strip_reasoning_tags,
    )
    from auto_shorts.re_engine import score_short_opus_runbook

    # 1. CoT <think> stripping (closed + truncated unclosed)
    assert strip_reasoning_tags("<think>raciocinio interno</think>Texto final limpo.") == "Texto final limpo."
    assert strip_reasoning_tags("Resposta pronta<thought>rascunho cortado") == "Resposta pronta"

    # 2. Title & hook hygiene fixes (no >>, greetings, dangling words, or English leakage)
    assert _clean_source_title('>> "Salve, Salve!"') == "Salve, Salve!"
    assert _looks_english_title("Brazil has more elderly people than young people | Band News") is True
    assert _looks_english_title("FUX RESPONDS TO GILMAR MENDES' ACCUSATION: 'A PARALLEL FEDERAL POLICE WAS CREATED'") is True
    assert _polish_hook_phrase(['"SALVE,', 'SALVE', 'SEGREDO', 'OCULTO']) == "SEGREDO OCULTO"
    assert _polish_hook_phrase(["RAPPERS", "DO", "HIP"]) == "RAPPERS"

    # 3. Opus scorecard penalizes zero subtitles instead of awarding max score
    sc_no_subs = score_short_opus_runbook(
        {"title": "Teste", "hook_title": "GANCHO LIMPO", "caption": "Resumo teste"},
        validation={"duration": 35.0, "subtitle_cues": 0, "mean_volume_db": -16.5, "subtitle_overlaps": 0},
    )
    assert sc_no_subs["dimensions"]["audio_clarity"] <= 10
    assert any("Zero legendas" in f for f in sc_no_subs["flaws"])

    # 4. BM25 offline retrieval + capabilities + CPU fallback benchmark
    (tmp_path / "ai_short.publish.json").write_text(
        json.dumps({
            "title": "Como IA Economiza Horas No Dia",
            "hook_title": "IA ECONOMIZA HORAS",
            "caption": "Automacao offline no Android com Termux e Kokoro PT-BR.",
            "niche": "ia_tech",
            "hashtags": ["#ia", "#Shorts"],
        }),
        encoding="utf-8",
    )
    caps = detect_android_llm_capabilities(llama_url="http://127.0.0.1:59999")
    assert caps["cpu_cores"] >= 1 and caps["recommended_tier"]["id"]
    bench = benchmark_local_llm(llama_url="http://127.0.0.1:59999")
    assert bench["ok"] is True and bench["mode"] == "cpu-heuristic"
    hits = bm25_search_shorts("economiza horas android", tmp_path)
    assert len(hits) == 1 and hits[0]["filename"] == "ai_short.mp4"
    chat = answer_studio_question_offline("Tem video sobre IA no Android?", tmp_path, llama_url="http://127.0.0.1:59999")
    assert chat["ok"] is True and chat["backend"] == "bm25-offline" and len(chat["sources"]) == 1

    # 5. CosyVoice / FalaBrasil PT-BR spoken text normalization + Open-Swara reference WAVs
    from auto_shorts.narrator import _prepare_speech_text, resolve_open_swara_pt_ref

    spoken = _prepare_speech_text("IA nos EUA subiu 45% e custou R$ 120 a 300 km/h!")
    assert "inteligência artificial" in spoken
    assert "Estados Unidos" in spoken
    assert "45 por cento" in spoken
    assert "120 reais" in spoken
    assert "quilômetros por hora" in spoken
    assert resolve_open_swara_pt_ref("narrador_pro").endswith("pt_male_ref.wav")
    assert resolve_open_swara_pt_ref("podcast_female").endswith("pt_female_ref.wav")

    # 6. Hook cleanliness against weak Portuguese copulas/auxiliaries + Autopilot seen_ids
    assert _polish_hook_phrase(["SENADO.", "ISSO", "FOI", "UMA", "GRANDE"]) == "SENADO. ISSO"
    assert _polish_hook_phrase(["JÁ", "TÁ", "NO", "AR", "SEGREDO", "REAL"]) == "AR SEGREDO REAL"
    from auto_shorts.horizon_radar import build_horizon_spoken_script

    anime_script = build_horizon_spoken_script(
        {"horizon": "entretenimento_cultura", "title_pt": "Teoria secreta do episodio novo de Solo Leveling", "hook_suggestion": "NINGUEM NOTOU ESSA CENA"},
        use_llm=False,
    )
    assert len(anime_script.split()) >= 50 and "episódio" in anime_script.lower()
    tech_script = build_horizon_spoken_script(
        {"horizon": "dinheiro_ia", "title_pt": "Como celulares ARM rodam IA offline", "hook_suggestion": "IA OFFLINE NO CELULAR"},
        use_llm=False,
    )
    assert "inteligência artificial" in tech_script.lower() and "compras por impulso" not in tech_script.lower()
    from auto_shorts.narrator import _build_narrated_title

    assert _build_narrated_title("IA OFFLINE NO CELULAR", "") == "IA Offline no Celular"

    # 7. Smart storage retention (cleans stale temp dirs, duplicates & oldest published while keeping unpublished queue)
    import os
    from auto_shorts.retention import prune_storage

    s_dir = tmp_path / "storage_test"
    s_dir.mkdir()
    stale_work = s_dir / "_work_old"
    stale_work.mkdir()
    (stale_work / "raw.mp4").write_bytes(b"0" * 50000)
    os.utime(stale_work, (1000.0, 1000.0))

    pub1 = s_dir / "pub_old.mp4"
    pub1.write_bytes(b"0" * 40000)
    pub1.with_suffix(".publish.json").write_text(json.dumps({"youtube": {"video_id": "YT123"}, "validation": {"valid": True}}))
    os.utime(pub1, (1000.0, 1000.0))

    dup1 = s_dir / "dup.mp4"
    dup1.write_bytes(b"0" * 40000)
    dup1.with_suffix(".publish.json").write_text(json.dumps({"duplicate_of": "queued.mp4", "validation": {"valid": True}}))

    q1 = s_dir / "queued.mp4"
    q1.write_bytes(b"0" * 40000)
    q1.with_suffix(".publish.json").write_text(json.dumps({"queued_for_auto_publish": True, "validation": {"valid": True}}))

    pr = prune_storage(s_dir, max_videos=1, max_output_mb=50.0, keep_recent_work_hours=0.1)
    assert not stale_work.exists()
    assert not dup1.exists()
    assert not pub1.exists()
    assert q1.exists() and pr["freed_mb"] > 0.1


def test_tiktok_content_posting_v2(tmp_path: Path, monkeypatch) -> None:
    import io
    import threading
    import urllib.request
    from auto_shorts.publisher import (
        TIKTOK_DEFAULT_CHUNK_BYTES,
        TIKTOK_DIRECT_INIT_URL,
        TIKTOK_INBOX_INIT_URL,
        compute_tiktok_chunk_plan,
        publish_pack_to_tiktok,
    )
    from auto_shorts.webapp import _StudioHTTPServer, make_handler

    # 1. Chunk planning: <=64 MB single chunk, >64 MB floor division (trailing bytes merge into final chunk)
    assert compute_tiktok_chunk_plan(3_000_000) == (3_000_000, 1)
    assert compute_tiktok_chunk_plan(64 * 1024 * 1024) == (64 * 1024 * 1024, 1)
    assert compute_tiktok_chunk_plan(75_000_123) == (TIKTOK_DEFAULT_CHUNK_BYTES, 7)

    # 2. Unconfigured env returns safe skipped_unconfigured status without network I/O
    for key in ("TIKTOK_ACCESS_TOKEN", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    mp4 = tmp_path / "tiktok_sample.mp4"
    mp4.write_bytes(b"FTYPMP4DATA" * 8000)
    mp4.with_suffix(".publish.json").write_text(
        json.dumps({"title": "Teste TikTok", "caption": "Legenda #ia"}),
        encoding="utf-8",
    )
    skipped = publish_pack_to_tiktok(mp4)
    assert skipped["status"] == "skipped_unconfigured"

    # 3. Mocked Inbox + Direct API init and sequential Content-Range PUT upload
    seen_calls = []
    orig_urlopen = urllib.request.urlopen

    class _FakeHTTPResp:
        def __init__(self, body_bytes: bytes, status: int = 200):
            self._buf = io.BytesIO(body_bytes)
            self.status = status

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=30):
        headers = {k.lower(): v for k, v in req.header_items()}
        seen_calls.append({
            "method": req.get_method(),
            "url": req.full_url,
            "headers": headers,
            "data": req.data,
        })
        if req.full_url in (TIKTOK_INBOX_INIT_URL, TIKTOK_DIRECT_INIT_URL):
            return _FakeHTTPResp(json.dumps({
                "data": {"publish_id": "v_inbox_123", "upload_url": "https://upload.tiktokapis.com/chunk/abc"},
                "error": {"code": "ok", "message": ""},
            }).encode("utf-8"))
        return _FakeHTTPResp(b"", status=201)

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tt_tok_test")

    inbox_res = publish_pack_to_tiktok(mp4, mode="inbox")
    assert inbox_res["status"] == "published_tiktok_inbox"
    assert inbox_res["publish_id"] == "v_inbox_123"
    assert seen_calls[0]["url"] == TIKTOK_INBOX_INIT_URL
    assert seen_calls[1]["method"] == "PUT"
    assert seen_calls[1]["headers"]["content-range"] == f"bytes 0-{mp4.stat().st_size - 1}/{mp4.stat().st_size}"

    seen_calls.clear()
    direct_res = publish_pack_to_tiktok(mp4, mode="direct", privacy_level="PUBLIC_TO_EVERYONE")
    assert direct_res["status"] == "published_tiktok_direct"
    init_payload = json.loads(seen_calls[0]["data"].decode("utf-8"))
    assert init_payload["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert "Teste TikTok" in init_payload["post_info"]["title"] or "Legenda" in init_payload["post_info"]["title"]
    saved_pack = json.loads(mp4.with_suffix(".publish.json").read_text(encoding="utf-8"))
    assert saved_pack["tiktok"]["mode"] == "direct"

    # 4. Webapp POST /api/publish-tiktok route + /api/system keys check
    monkeypatch.setattr(urllib.request, "urlopen", orig_urlopen)
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    srv = _StudioHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system", timeout=5) as r:
            sys_data = json.loads(r.read().decode("utf-8"))
        assert "tiktok" in sys_data["keys"] and sys_data["keys"]["tiktok"] is False

        req_tt = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/publish-tiktok",
            data=json.dumps({"filename": "tiktok_sample.mp4"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_tt, timeout=5) as r:
            tt_api = json.loads(r.read().decode("utf-8"))
        assert tt_api["status"] == "skipped_unconfigured"
    finally:
        srv.shutdown()
        srv.server_close()

    # 5. TikTok Desktop OAuth2 PKCE hexdigest helper validation
    import hashlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tiktok_auth", Path(__file__).resolve().parents[1] / "scripts" / "tiktok_auth.py"
    )
    tt_auth = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(tt_auth)
    verifier, challenge = tt_auth.generate_pkce_pair()
    assert len(verifier) == 64
    assert challenge == hashlib.sha256(verifier.encode("utf-8")).hexdigest()
    auth_u = tt_auth.build_tiktok_authorize_url("ck_demo", code_challenge=challenge)
    assert f"code_challenge={challenge}" in auth_u and "code_challenge_method=S256" in auth_u

    # 6. Autonomous pending flush dispatches queued validated Short to TikTok
    from auto_shorts import webapp as wa_mod
    q_dir = tmp_path / "flush_tt"
    q_dir.mkdir()
    q_mp4 = q_dir / "ready_tiktok.mp4"
    q_mp4.write_bytes(b"MP4" * 20000)
    q_mp4.with_suffix(".publish.json").write_text(
        json.dumps({
            "title": "Short Pronto",
            "validation": {"valid": True},
            "visual_audit": {"approved": True},
            "queued_for_auto_publish": True,
        }),
        encoding="utf-8",
    )
    flushed = []
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "tt_flush_tok")
    monkeypatch.setattr(wa_mod, "publish_pack_to_tiktok", lambda p, **kw: flushed.append(p.name) or {"publish_id": "v_flush_1", "mode": "inbox"})
    assert wa_mod._flush_pending_publishes(q_dir) is True
    assert flushed == ["ready_tiktok.mp4"]


def test_tiktok_algorithm_and_mentalism_engine(tmp_path: Path) -> None:
    import threading
    import urllib.request
    from auto_shorts.tiktok_algorithm import (
        NICHE_MENTALISM_PLAYBOOKS,
        build_mentalist_script_blueprint,
        get_tiktok_algorithm_blueprint,
        score_short_for_tiktok_algorithm,
    )
    from auto_shorts.webapp import _StudioHTTPServer, make_handler

    assert "financas" in NICHE_MENTALISM_PLAYBOOKS and "ia_tech" in NICHE_MENTALISM_PLAYBOOKS
    scored = score_short_for_tiktok_algorithm(
        pack={
            "niche": "financas",
            "hook_title": "O ERRO DO PIX",
            "title": "Por que seu banco esconde esse detalhe?",
            "caption": "Veja agora esse segredo financeiro e comenta qual sua escolha! #financas #dinheiro #educacaofinanceira",
            "hashtags": ["#financas", "#dinheiro", "#educacaofinanceira", "#tiktokbrasil"],
            "background_style": "minecraft+urban_rain",
            "visual_audit": {"approved": True, "visual": {"motion_delta": 18.0}},
        },
        validation={"valid": True, "duration": 64.0, "subtitle_cues": 16, "subtitle_overlaps": 0},
    )
    assert scored["tiktok_score"] >= 85
    assert scored["monetization_eligible_60s"] is True
    assert "Aversao a Perda" in scored["playbook"]["brain_trigger"]

    bp = build_mentalist_script_blueprint("IA offline no Android", niche="ia_tech", target_duration_sec=64)
    assert bp["beats"]["0_a_2s_pattern_interrupt"]
    assert "full_narration_script" in bp and len(bp["full_narration_script"]) > 80

    # HTTP endpoints check (/api/tiktok/intelligence & /api/tiktok/mentalist-brief)
    srv = _StudioHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tiktok/intelligence", timeout=5) as r:
            intel = json.loads(r.read().decode("utf-8"))
        assert sum(w["weight_pct"] for w in intel["signal_weights"]) == 100
        assert len(intel["cohort_stages"]) == 4

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/tiktok/mentalist-brief",
            data=json.dumps({"topic": "Juros compostos", "niche": "financas", "duration_sec": 64}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            mb = json.loads(r.read().decode("utf-8"))
        assert mb["niche"] == "financas" and mb["recommended_layout"] == "blur_bg"
    finally:
        srv.shutdown()
        srv.server_close()


def test_smart_autopublish_priority_and_cadence(tmp_path: Path, monkeypatch) -> None:
    import os
    from auto_shorts.smart_autopublish import (
        can_publish_channel,
        get_autopublish_plan,
        load_publish_ledger,
        rank_publish_candidates,
        run_smart_publish_cycle,
    )

    # Video A: weak score, old, already posted niche "financas"
    v_weak = tmp_path / "weak_short.mp4"
    v_weak.write_bytes(b"MP4" * 20000)
    v_weak.with_suffix(".publish.json").write_text(
        json.dumps({
            "title": ">> Corte qualquer",
            "niche": "financas",
            "caption": "curta",
            "hashtags": ["#geral"],
            "validation": {"valid": True, "duration": 22.0, "subtitle_cues": 2, "subtitle_overlaps": 0},
            "visual_audit": {"approved": True, "quality_score": 70},
            "queued_for_auto_publish": True,
        }),
        encoding="utf-8",
    )

    # Video B: high opus + 64s Creator Rewards + distinct niche "ia_tech"
    v_top = tmp_path / "top_ia_64s.mp4"
    v_top.write_bytes(b"MP4" * 20000)
    v_top.with_suffix(".publish.json").write_text(
        json.dumps({
            "title": "Por que IAs offline rodam no Android sem nuvem",
            "hook_title": "IA OFFLINE NO CELULAR",
            "niche": "ia_tech",
            "caption": "Descubra como rodar modelos GGUF no Android sem internet. Comenta TESTAR!",
            "hashtags": ["#inteligenciaartificial", "#tecnologia", "#ia", "#produtividade"],
            "background_style": "minecraft+urban_rain",
            "validation": {"valid": True, "duration": 64.0, "subtitle_cues": 18, "subtitle_overlaps": 0},
            "visual_audit": {"approved": True, "quality_score": 94, "visual": {"motion_delta": 22.0, "luma_std": 42.0}},
            "queued_for_auto_publish": True,
        }),
        encoding="utf-8",
    )

    ledger = load_publish_ledger(tmp_path)
    ledger["tiktok"]["last_niche"] = "financas"
    cands = rank_publish_candidates(tmp_path, "tiktok", ledger=ledger)
    assert len(cands) == 2 and cands[0]["filename"] == "top_ia_64s.mp4"

    # Run smart cycle dispatching to mocked TikTok & mocking YouTube uploadLimitExceeded cooldown
    sent_tt = []
    res = run_smart_publish_cycle(
        tmp_path,
        youtube_ready=True,
        tiktok_ready=True,
        yt_publisher=lambda p: (_ for _ in ()).throw(RuntimeError("uploadLimitExceeded")),
        tt_publisher=lambda p: sent_tt.append(p.name) or {"publish_id": "v_smart_1", "mode": "inbox"},
    )
    assert res["dispatched"] is True
    assert sent_tt == ["top_ia_64s.mp4"]
    assert res["results"]["youtube"]["status"] == "quota_cooldown_4h"

    # Immediately afterwards, TikTok hits organic_spacing and YouTube hits quota_cooldown
    lg_after = load_publish_ledger(tmp_path)
    ok_tt, r_tt, _ = can_publish_channel(lg_after, "tiktok")
    ok_yt, r_yt, _ = can_publish_channel(lg_after, "youtube")
    assert ok_tt is False and "organic_spacing" in r_tt
    assert ok_yt is False and r_yt == "quota_cooldown"

    plan = get_autopublish_plan(tmp_path, youtube_ready=True, tiktok_ready=True)
    assert plan["channels"]["tiktok"]["daily_used"] == 1
    assert plan["channels"]["youtube"]["gate_reason"] == "quota_cooldown"

    # Simulate TikTok spam_risk_too_many_pending_share setting automatic 2h cooldown cleanly
    tt_cd_res = run_smart_publish_cycle(
        tmp_path,
        youtube_ready=False,
        tiktok_ready=True,
        force=True,
        tt_publisher=lambda p: (_ for _ in ()).throw(RuntimeError("spam_risk_too_many_pending_share")),
    )
    assert tt_cd_res["results"]["tiktok"]["status"] == "inbox_pending_cooldown_2h"
    assert can_publish_channel(load_publish_ledger(tmp_path), "tiktok")[1] == "quota_cooldown"


def test_universal_multi_niche_cinema_story_and_hook_safety(tmp_path):
    from auto_shorts.highlights import _polish_hook_phrase, heal_proper_nouns_and_asr
    from auto_shorts.story_engine import (
        NarrativeContinuityStore,
        StoryEngine,
        detect_universal_genre_and_niche,
    )

    # 1. Word-safe hook polishing NEVER truncates mid-word like "O SEGREDO PROIBIDO SOBRE O S"
    hook = _polish_hook_phrase("O Segredo Proibido de Brook e Imu em One Piece 1185", max_chars=34)
    assert not hook.endswith(" O S")
    assert not hook.endswith(" DE")
    assert len(hook) <= 34

    # 2. Universal multi-niche auto-detection routes Finance, AI, Psychology, Podcast & Anime accurately
    assert detect_universal_genre_and_niche("Como a taxa Selic afeta seus investimentos em 2026")[1] == "financas"
    assert detect_universal_genre_and_niche("Novos modelos de inteligência artificial rodando no celular")[1] == "ia_tech"
    assert detect_universal_genre_and_niche("Como a dopamina e o sono controlam seu foco diário")[1] == "desenvolvimento_pessoal"
    assert detect_universal_genre_and_niche("O segredo proibido de Brook e Imu em One Piece 1185")[1] == "entretenimento_animes"

    # 3. StoryEngine produces non-repetitive, domain-specific scripts across all niches
    store = NarrativeContinuityStore(tmp_path / "continuity.db")
    engine = StoryEngine(continuity_store=store)

    fin_script = engine.generate_story_script(
        prompt="O segredo oculto sobre a Taxa Selic e os Juros Compostos",
        genre="financas_negocios",
        use_local_llm=False,
    )
    fin_text = " ".join(s.dialogue for s in fin_script.scenes)
    assert "o segredo oculto sobre o segredo oculto" not in fin_text.lower()
    assert "mercado" in fin_text.lower() or "patrimônio" in fin_text.lower() or "caixa" in fin_text.lower()

    ai_script = engine.generate_story_script(
        prompt="A verdade sobre Inteligência Artificial Offline no Android",
        genre="ia_futuro_tech",
        use_local_llm=False,
    )
    ai_text = " ".join(s.dialogue for s in ai_script.scenes)
    assert "a verdade sobre a verdade sobre" not in ai_text.lower()
    assert "algoritmo" in ai_text.lower() or "infraestrutura" in ai_text.lower()

    # 4. Multi-niche ASR healer fixes Tech, Finance, Podcast, and Pop Culture proper nouns
    healed = heal_proper_nouns_and_asr("No pód pá falaram de xat gpt, dip sik, taixa selic e uma peça com bruke")
    assert "Podpah" in healed
    assert "ChatGPT" in healed
    assert "DeepSeek" in healed
    assert "Selic" in healed
    assert "One Piece" in healed
    assert "Brook" in healed
















