from pathlib import Path
import pytest

from auto_shorts.cross_platform_adapter import (
    adapt_short_for_all_platforms,
    build_instagram_caption,
    build_tiktok_metadata,
    build_youtube_shorts_metadata,
    PLATFORM_SAFE_ZONES,
)
from auto_shorts.pro_editor_engine import (
    compute_speech_intervals_from_silences,
    generate_capcut_word_pop_ass,
    generate_cinematic_filter_chain,
    parse_silence_intervals_from_ffmpeg,
)


def test_cross_platform_adaptation():
    title = "OpenAI lança modelo revolucionário com raciocínio quântico"
    body = "O novo sistema superou benchmarks de matemática e programação em testes cegos realizados por universidades parceiras."
    adapted = adapt_short_for_all_platforms(
        title=title,
        body_text=body,
        niche="tech_ia",
        hook_banner="IA REVOLUCIONÁRIA",
        source_attribution="TechCrunch",
    )

    assert adapted["niche"] == "tech_ia"
    # Instagram checks
    ig = adapted["instagram"]
    assert len(ig["hashtags"]) <= 5
    assert len(ig["hashtags"]) >= 3
    assert "TechCrunch" in ig["caption"]
    assert ig["is_within_limit"] is True

    # TikTok checks
    tt = adapted["tiktok"]
    assert tt["hook_banner"] == "IA REVOLUCIONÁRIA"
    assert len(tt["title"]) <= 90
    assert len(tt["hashtags"]) <= 4

    # YouTube checks
    yt = adapted["youtube"]
    assert len(yt["title"]) <= 70
    assert "#Shorts" in yt["title"]
    assert len(yt["hashtags"]) <= 3

    # Safe zones check
    assert "instagram_reels" in adapted["safe_zones"]
    assert "tiktok" in adapted["safe_zones"]
    assert "youtube_shorts" in adapted["safe_zones"]


def test_silence_detection_and_speech_intervals():
    log_sample = """
    [silencedetect @ 0x123] silence_start: 3.200
    [silencedetect @ 0x123] silence_end: 4.500 | silence_duration: 1.300
    [silencedetect @ 0x123] silence_start: 12.100
    [silencedetect @ 0x123] silence_end: 12.300 | silence_duration: 0.200
    [silencedetect @ 0x123] silence_start: 18.000
    [silencedetect @ 0x123] silence_end: 20.000 | silence_duration: 2.000
    """
    silences = parse_silence_intervals_from_ffmpeg(log_sample, min_silence_duration=0.45)
    # The 0.200s silence should be skipped (too short)
    assert len(silences) == 2
    assert silences[0] == (3.2, 4.5)
    assert silences[1] == (18.0, 20.0)

    # Invert to speech intervals
    speech = compute_speech_intervals_from_silences(silences, total_duration=25.0, padding=0.15)
    assert len(speech) >= 2
    # First chunk covers 0.0 to ~3.35
    assert speech[0][0] == 0.0
    assert speech[0][1] >= 3.2


def test_cinematic_filter_chain():
    fc = generate_cinematic_filter_chain(720, 1280, apply_vignette=True, apply_color_grade=True, zoom_scale=1.15)
    assert "scale=720:1280" in fc
    assert "vignette" in fc
    assert "eq=contrast" in fc
    assert "crop=" in fc


def test_capcut_word_pop_ass_generation(tmp_path):
    segments = [
        {
            "start": 0.0,
            "end": 2.5,
            "text": "GTA 6 LANÇAMENTO",
            "words": [
                {"word": "GTA", "start": 0.0, "end": 0.5},
                {"word": "6", "start": 0.5, "end": 0.9},
                {"word": "LANÇAMENTO", "start": 0.9, "end": 2.2},
            ],
        }
    ]
    ass_path = tmp_path / "test_capcut.ass"
    out_file = generate_capcut_word_pop_ass(segments, ass_path, video_width=720, video_height=1280)

    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "CapCutPop" in content
    assert "\\c&H0000FFFF&" in content  # Vibrant yellow highlight code
    assert "GTA" in content
