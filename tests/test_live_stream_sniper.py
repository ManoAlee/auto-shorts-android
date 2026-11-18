import math
import struct
import pytest
from auto_shorts.live_stream_sniper import (
    AudioEnergyAnalyzer,
    GTA6_LAUNCH_WATCHLIST,
    build_gamer_split_filter,
)


def test_watchlist_contains_major_streamers():
    names = {s.name for s in GTA6_LAUNCH_WATCHLIST}
    assert "Davy Jones" in names
    assert "Alanzoka" in names
    assert "Gaules" in names
    assert "Coringa" in names
    assert "KaiCenat" in names
    for s in GTA6_LAUNCH_WATCHLIST:
        assert s.channel_url.startswith("http")
        assert s.default_facecam_pos in ("top_left", "top_right", "bottom_left", "bottom_right")


def test_audio_energy_analyzer_silence_vs_scream():
    analyzer = AudioEnergyAnalyzer(spike_threshold_db=6.0, min_absolute_db=-20.0)

    # 1. Generate silence (low amplitude PCM16)
    silence_pcm = struct.pack("<1000h", *([100] * 1000))
    is_spike, cur_db, avg_db = analyzer.evaluate_frame(silence_pcm)
    assert cur_db < -40.0
    assert not is_spike

    # Populate rolling average with normal talking audio (~ -25 dB)
    normal_pcm = struct.pack("<1000h", *([2000] * 1000))
    for _ in range(10):
        analyzer.evaluate_frame(normal_pcm)

    # 2. Sudden scream / explosion (near 0 dB peak: amplitude ~ 28000)
    scream_pcm = struct.pack("<1000h", *([28000] * 1000))
    is_spike, cur_db, avg_db = analyzer.evaluate_frame(scream_pcm)

    assert cur_db > -4.0
    assert is_spike is True


def test_build_gamer_split_filter():
    filt = build_gamer_split_filter(facecam_pos="bottom_right", facecam_pct=0.34, canvas_w=1080, canvas_h=1920)
    assert "[0:v]split=2" in filt
    assert "vstack=inputs=2" in filt
    assert "1080" in filt
    assert "drawbox=" in filt
