import wave
from pathlib import Path
import pytest
from auto_shorts.procedural_music import (
    GENRE_PRESETS,
    generate_procedural_soundtrack,
    compute_beat_synced_video_cuts,
)


def test_genre_presets_exist():
    assert "synthwave" in GENRE_PRESETS
    assert "lofi" in GENRE_PRESETS
    assert "cinematic_tension" in GENRE_PRESETS
    assert "hyper_trap" in GENRE_PRESETS
    assert GENRE_PRESETS["synthwave"]["bpm"] == 120.0
    assert GENRE_PRESETS["lofi"]["bpm"] == 84.0


def test_generate_procedural_soundtrack(tmp_path: Path):
    out_file = tmp_path / "test_synthwave.wav"
    wav_path, meta = generate_procedural_soundtrack(
        genre="synthwave",
        duration_sec=3.0,
        out_wav_path=out_file,
    )

    assert wav_path.is_file()
    assert meta["genre"] == "synthwave"
    assert meta["bpm"] == 120.0
    assert meta["sec_per_beat"] == 0.5
    assert meta["sec_per_bar"] == 2.0
    assert len(meta["beat_timestamps"]) >= 6
    assert 0.0 in meta["beat_timestamps"]
    assert 0.5 in meta["beat_timestamps"]
    assert 1.0 in meta["beat_timestamps"]
    assert 0.0 in meta["downbeat_timestamps"]
    assert 2.0 in meta["downbeat_timestamps"]

    # Verify WAV header
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 44100 * 2.5


def test_generate_lofi_soundtrack(tmp_path: Path):
    out_file = tmp_path / "test_lofi.wav"
    wav_path, meta = generate_procedural_soundtrack(
        genre="lofi",
        duration_sec=2.0,
        out_wav_path=out_file,
    )
    assert wav_path.is_file()
    assert meta["bpm"] == 84.0


def test_compute_beat_synced_video_cuts():
    meta = {
        "bpm": 120.0,
        "sec_per_beat": 0.5,
        "sec_per_bar": 2.0,
        "downbeat_timestamps": [0.0, 2.0, 4.0, 6.0, 8.0, 10.0],
    }
    cuts = compute_beat_synced_video_cuts(
        total_duration=10.0,
        beat_metadata=meta,
        min_cut_interval=2.0,
    )

    assert len(cuts) >= 4
    assert cuts[0]["start"] == 0.0
    assert cuts[0]["end"] == 2.0
    assert cuts[0]["duration"] == 2.0
    # Alternating punch-zoom check
    assert cuts[0]["punch_zoom"] in (1.0, 1.14)
    assert cuts[1]["punch_zoom"] in (1.0, 1.14)
    assert cuts[0]["punch_zoom"] != cuts[1]["punch_zoom"]
