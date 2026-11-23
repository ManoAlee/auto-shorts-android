"""Unit and integration tests for smart_media_engine (distilled from ffmpeg-skill)."""

from pathlib import Path
import pytest

from auto_shorts.smart_media_engine import (
    PLATFORM_DELIVERY_SPECS,
    get_platform_safe_margins_px,
    probe_stream_params,
    probe_audio_stream_params,
    probe_keyframes,
    smart_cut_segment,
    measure_audio_loudness,
    build_two_pass_loudnorm_filter,
    detect_color_profile,
    build_hdr_to_sdr_filter_chain,
    build_primary_color_grade,
    get_bt709_vui_args,
    detect_scene_cuts,
    detect_audio_peaks,
    verify_video_compliance,
)
from auto_shorts.renderer import (
    build_ffmpeg_command,
    build_video_filter,
    cut_segment_temp,
)
from auto_shorts.subtitles import generate_ass_subtitles


def test_platform_delivery_specs_integrity():
    """Verify delivery specifications conform to TikTok, Reels, and Shorts platform standards."""
    assert "tiktok" in PLATFORM_DELIVERY_SPECS
    assert "instagram_reels" in PLATFORM_DELIVERY_SPECS
    assert "youtube_shorts" in PLATFORM_DELIVERY_SPECS

    tt = PLATFORM_DELIVERY_SPECS["tiktok"]
    assert tt["aspect_ratio"] == "9:16"
    assert tt["lufs_target"] == -14.0
    assert tt["tp_ceiling"] == -1.0
    assert tt["safe_margins"]["right"] == 0.14  # 14% right rail for action buttons
    assert tt["safe_margins"]["bottom"] == 0.22 # 22% bottom description/sound area


def test_platform_safe_margins_pixel_calculation():
    """Verify pixel margins calculated correctly for 720p and 1080p vertical canvases."""
    m_720 = get_platform_safe_margins_px("tiktok", width=720, height=1280)
    assert m_720["right"] == 101  # 720 * 0.14
    assert m_720["bottom"] == 282 # 1280 * 0.22
    assert m_720["safe_width"] == 583
    assert m_720["safe_height"] == 870

    m_1080 = get_platform_safe_margins_px("tiktok", width=1080, height=1920)
    assert m_1080["right"] == 151 # 1080 * 0.14
    assert m_1080["bottom"] == 422 # 1920 * 0.22


def test_build_two_pass_loudnorm_filter_linear():
    """Verify Pass 2 linear loudnorm filter constructed with Pass 1 measurements."""
    stats = {
        "input_i": "-18.50",
        "input_tp": "-2.30",
        "input_lra": "7.50",
        "input_thresh": "-28.50",
        "target_offset": "0.50",
        "silent": False,
    }
    af = build_two_pass_loudnorm_filter(stats, target_i=-14.0, target_tp=-1.0, target_lra=11.0)
    assert "loudnorm=I=-14.0:TP=-1.0:LRA=11.0" in af
    assert "measured_I=-18.50" in af
    assert "measured_TP=-2.30" in af
    assert "measured_LRA=7.50" in af
    assert "measured_thresh=-28.50" in af
    assert "offset=0.50" in af
    assert "linear=true" in af


def test_build_two_pass_loudnorm_filter_silent_fallback():
    """Verify fallback to standard loudnorm when audio is silent or unmeasured."""
    stats = {"silent": True}
    af = build_two_pass_loudnorm_filter(stats, target_i=-14.0, target_tp=-1.0)
    assert af == "loudnorm=I=-14.0:TP=-1.0:LRA=11.0"


def test_hdr_to_sdr_filter_chain():
    """Verify tone mapping filter chain converting HDR/BT.2020 to BT.709 SDR."""
    filter_chain = build_hdr_to_sdr_filter_chain(tonemap="mobius")
    assert "zscale=t=linear:npl=100" in filter_chain
    assert "tonemap=mobius:desat=0.5" in filter_chain
    assert "zscale=t=bt709:m=bt709" in filter_chain
    assert "format=yuv420p" in filter_chain


def test_primary_color_grade():
    """Verify subtle cinema grade filter generation."""
    grade = build_primary_color_grade(contrast=1.08, saturation=1.16, brightness=0.01, unsharp=True)
    assert "eq=contrast=1.08:saturation=1.16:brightness=0.01" in grade
    assert "unsharp=3:3:0.45:3:3:0.0" in grade


def test_bt709_vui_args():
    """Verify encoder VUI tags preserve color profile across mobile players."""
    x264_args = get_bt709_vui_args("libx264")
    assert x264_args == ["-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]

    x265_args = get_bt709_vui_args("libx265")
    assert x265_args == ["-x265-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]


def test_renderer_build_ffmpeg_command_with_smart_media_enhancements():
    """Verify build_ffmpeg_command integrates two-pass loudnorm and VUI parameters."""
    stats = {
        "input_i": "-16.20",
        "input_tp": "-1.80",
        "input_lra": "6.00",
        "input_thresh": "-26.50",
        "target_offset": "0.20",
        "silent": False,
    }
    cmd = build_ffmpeg_command(
        source_path="dummy.mp4",
        out_path="out.mp4",
        start_time=5.0,
        end_time=35.0,
        layout="blur_bg",
        quality="mobile",
        encoder="libx264",
        normalize_audio=True,
        loudnorm_stats=stats,
        is_hdr=True,
    )

    cmd_str = " ".join(cmd)
    # Check VUI color flags
    assert "-x264-params colorprim=bt709:transfer=bt709:colormatrix=bt709" in cmd_str
    # Check linear two-pass loudnorm
    assert "measured_I=-16.20" in cmd_str
    assert "linear=true" in cmd_str
    # Check HDR-to-SDR tonemap in filtergraph
    assert "tonemap=mobius" in cmd_str


def test_subtitles_safe_zone_margins(tmp_path):
    """Verify generated ASS subtitles respect TikTok/Reels safe side margins."""
    segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "SEGREDO REVELADO AGORA",
            "words": [
                {"word": "SEGREDO", "start": 0.0, "end": 0.6},
                {"word": "REVELADO", "start": 0.6, "end": 1.3},
                {"word": "AGORA", "start": 1.3, "end": 1.9},
            ],
        }
    ]
    out_ass = tmp_path / "safe_subs.ass"
    generate_ass_subtitles(
        segments=segments,
        clip_start=0.0,
        clip_end=2.0,
        out_path=out_ass,
        width=1080,
        height=1920,
    )
    assert out_ass.is_file()
    content = out_ass.read_text(encoding="utf-8")
    # MarginR must be at least 151px (14% on 1080p) to avoid TikTok right rail icons
    assert ",151," in content
    # MarginV should protect bottom description
    assert ",450," in content
