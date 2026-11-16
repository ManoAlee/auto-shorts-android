"""AutoShorts Procedural Music & Beat-Sync Engine.

Generates 100% royalty-free, algorithmic background music (Lofi, Synthwave,
Cinematic Tension, Hyper Trap) and calculates exact mathematical beat timestamps
for beat-synced video cuts, B-Roll switching, and dynamic punch-zooms.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import struct
from typing import Dict, List, Optional, Tuple
import wave

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# Musical Note Frequencies (A4 = 440 Hz)
NOTE_FREQS = {
    "C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31, "G2": 98.00, "A2": 110.00, "B2": 123.47,
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46, "G5": 783.99, "A5": 880.00, "B5": 987.77,
}


GENRE_PRESETS: Dict[str, Dict] = {
    "synthwave": {
        "bpm": 120.0,
        "root": "A2",
        "chords": [
            ["A2", "C3", "E3", "A3"],  # Am
            ["F2", "A2", "C3", "F3"],  # F
            ["C2", "E2", "G2", "C3"],  # C
            ["G2", "B2", "D3", "G3"],  # G
        ],
        "lead_arp": ["A4", "C5", "E5", "G4", "E5", "C5", "D5", "B4"],
        "bass_osc": "saw",
        "has_kick": True,
        "has_snare": True,
        "has_hihat": True,
    },
    "lofi": {
        "bpm": 84.0,
        "root": "D3",
        "chords": [
            ["D3", "F3", "A3", "C4"],  # Dm7
            ["G2", "B2", "D3", "F3"],  # G7
            ["C3", "E3", "G3", "B3"],  # Cmaj7
            ["A2", "C3", "E3", "G3"],  # Am7
        ],
        "lead_arp": ["E4", "F4", "A4", "C5", "A4", "F4"],
        "bass_osc": "sine",
        "has_kick": True,
        "has_snare": True,
        "has_hihat": True,
    },
    "cinematic_tension": {
        "bpm": 76.0,
        "root": "D2",
        "chords": [
            ["D2", "D3", "A3", "F3"],  # Dm drone
            ["A#1", "A#2", "F3", "D3"],  # Bb drone
            ["G1", "G2", "D3", "A#3"],  # Gm drone
            ["A1", "A2", "E3", "C#4"],  # A maj
        ],
        "lead_arp": ["D4", "F4", "A4", "D5"],
        "bass_osc": "sub_sine",
        "has_kick": True,
        "has_snare": False,
        "has_hihat": True,
    },
    "hyper_trap": {
        "bpm": 140.0,
        "root": "C2",
        "chords": [
            ["C2", "G2", "D#3"],
            ["G#1", "D#2", "C3"],
            ["A#1", "F2", "D3"],
            ["G1", "D2", "A#2"],
        ],
        "lead_arp": ["C5", "D#5", "G5", "F5"],
        "bass_osc": "saw",
        "has_kick": True,
        "has_snare": True,
        "has_hihat": True,
    },
}


def _synth_wave(
    freq: float,
    duration: float,
    sample_rate: int = 44100,
    wave_type: str = "sine",
    decay: float = 0.0,
) -> List[float]:
    """Synthesize a single audio wave with optional exponential envelope decay."""
    total_samples = int(duration * sample_rate)
    samples: List[float] = []
    two_pi_f = 2.0 * math.pi * freq

    for i in range(total_samples):
        t = float(i) / sample_rate
        if wave_type == "sine":
            val = math.sin(two_pi_f * t)
        elif wave_type == "saw":
            # Band-limited pseudo-saw
            val = 2.0 * (t * freq - math.floor(t * freq + 0.5))
        elif wave_type == "square":
            val = 1.0 if math.sin(two_pi_f * t) >= 0.0 else -1.0
        elif wave_type == "sub_sine":
            val = math.sin(two_pi_f * t) * 0.85 + math.sin(two_pi_f * 0.5 * t) * 0.35
        else:
            val = math.sin(two_pi_f * t)

        if decay > 0.0:
            env = math.exp(-decay * t)
            val *= env
        samples.append(val)
    return samples


def _make_drum_sound(
    drum_type: str,
    duration: float = 0.25,
    sample_rate: int = 44100,
) -> List[float]:
    """Generate synthesized drum hits (kick, snare, hi-hat) using pure code."""
    total_samples = int(duration * sample_rate)
    samples: List[float] = []

    if drum_type == "kick":
        # Pitch drop from 150Hz to 42Hz with exponential decay
        for i in range(total_samples):
            t = float(i) / sample_rate
            pitch = 45.0 + 105.0 * math.exp(-22.0 * t)
            phase = 2.0 * math.pi * pitch * t
            amp = math.exp(-12.0 * t)
            samples.append(math.sin(phase) * amp)

    elif drum_type == "snare":
        # Noise burst + body resonance
        import random

        for i in range(total_samples):
            t = float(i) / sample_rate
            noise = (random.random() * 2.0 - 1.0) * 0.7
            body = math.sin(2.0 * math.pi * 185.0 * t) * 0.35
            amp = math.exp(-18.0 * t)
            samples.append((noise + body) * amp)

    elif drum_type == "hihat":
        # High-passed short noise burst
        import random

        for i in range(total_samples):
            t = float(i) / sample_rate
            noise = random.random() * 2.0 - 1.0
            amp = math.exp(-48.0 * t)
            samples.append(noise * amp * 0.45)
    else:
        samples = [0.0] * total_samples

    return samples


def generate_procedural_soundtrack(
    genre: str = "synthwave",
    duration_sec: float = 45.0,
    out_wav_path: Optional[Path] = None,
    target_lufs: float = -22.0,
    sample_rate: int = 44100,
) -> Tuple[Path, Dict]:
    """Synthesize a complete multi-layered soundtrack and return its beat map."""
    preset = GENRE_PRESETS.get(genre, GENRE_PRESETS["synthwave"])
    bpm = float(preset["bpm"])
    sec_per_beat = 60.0 / bpm
    sec_per_bar = sec_per_beat * 4.0
    total_bars = math.ceil(duration_sec / sec_per_bar)
    total_samples = int(duration_sec * sample_rate)

    # Initialize audio buffer
    if HAS_NUMPY:
        audio = np.zeros(total_samples, dtype=np.float32)
    else:
        audio = [0.0] * total_samples

    # Compute exact beat timestamps
    beat_timestamps: List[float] = []
    downbeat_timestamps: List[float] = []
    drop_timestamps: List[float] = []

    curr_t = 0.0
    beat_idx = 0
    while curr_t < duration_sec:
        beat_timestamps.append(round(curr_t, 3))
        if beat_idx % 4 == 0:
            downbeat_timestamps.append(round(curr_t, 3))
        if beat_idx % 16 == 0 and curr_t > 0.1:
            drop_timestamps.append(round(curr_t, 3))
        curr_t += sec_per_beat
        beat_idx += 1

    # 1. Synthesize Chord Pads & Bassline
    chords = preset["chords"]
    bass_osc = preset["bass_osc"]
    for bar in range(total_bars):
        chord_notes = chords[bar % len(chords)]
        bar_start_t = bar * sec_per_bar
        if bar_start_t >= duration_sec:
            break

        # Render chord layer
        chord_dur = min(sec_per_bar, duration_sec - bar_start_t)
        for note_name in chord_notes:
            freq = NOTE_FREQS.get(note_name, 220.0)
            note_wave = _synth_wave(freq, chord_dur, sample_rate, wave_type="sine", decay=0.8)
            s_idx = int(bar_start_t * sample_rate)
            for k, val in enumerate(note_wave):
                if s_idx + k < total_samples:
                    audio[s_idx + k] += val * 0.14

        # Render Root Bass
        root_name = chord_notes[0]
        root_freq = NOTE_FREQS.get(root_name, 110.0)
        bass_wave = _synth_wave(root_freq, chord_dur, sample_rate, wave_type=bass_osc, decay=0.3)
        s_idx = int(bar_start_t * sample_rate)
        for k, val in enumerate(bass_wave):
            if s_idx + k < total_samples:
                audio[s_idx + k] += val * 0.22

    # 2. Synthesize Rhythmic Drums (Kick on 1 & 3, Snare on 2 & 4, Hi-Hats on 8ths)
    kick_samples = _make_drum_sound("kick", duration=0.28, sample_rate=sample_rate)
    snare_samples = _make_drum_sound("snare", duration=0.22, sample_rate=sample_rate)
    hihat_samples = _make_drum_sound("hihat", duration=0.08, sample_rate=sample_rate)

    for idx, b_time in enumerate(beat_timestamps):
        if b_time >= duration_sec:
            break
        s_idx = int(b_time * sample_rate)
        pos_in_bar = idx % 4

        # Kick
        if preset["has_kick"] and (pos_in_bar == 0 or pos_in_bar == 2):
            for k, val in enumerate(kick_samples):
                if s_idx + k < total_samples:
                    audio[s_idx + k] += val * 0.35

        # Snare
        if preset["has_snare"] and (pos_in_bar == 1 or pos_in_bar == 3):
            for k, val in enumerate(snare_samples):
                if s_idx + k < total_samples:
                    audio[s_idx + k] += val * 0.28

        # Hi-Hats
        if preset["has_hihat"]:
            for k, val in enumerate(hihat_samples):
                if s_idx + k < total_samples:
                    audio[s_idx + k] += val * 0.16
            # Off-beat hi-hat
            off_idx = s_idx + int((sec_per_beat * 0.5) * sample_rate)
            for k, val in enumerate(hihat_samples):
                if off_idx + k < total_samples:
                    audio[off_idx + k] += val * 0.12

    # 3. Master Volume & Envelope (Fade In 0.5s, Fade Out 1.2s)
    fade_in_samples = int(0.5 * sample_rate)
    fade_out_samples = int(1.2 * sample_rate)

    max_amp = max(abs(x) for x in audio) if not HAS_NUMPY else float(np.max(np.abs(audio)))
    norm_factor = 0.45 / max(0.001, max_amp)

    out_pcm = bytearray()
    for i in range(total_samples):
        val = audio[i] * norm_factor
        # Fade In
        if i < fade_in_samples:
            val *= float(i) / fade_in_samples
        # Fade Out
        elif i > total_samples - fade_out_samples:
            remain = total_samples - i
            val *= float(remain) / fade_out_samples

        clamped = max(-1.0, min(1.0, val))
        int_sample = int(clamped * 32767)
        # Stereo duplicate (L, R)
        out_pcm.extend(struct.pack("<hh", int_sample, int_sample))

    # 4. Save to WAV
    if out_wav_path is None:
        out_wav_path = Path("output") / f"procedural_{genre}_{int(duration_sec)}s.wav"
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(out_wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(out_pcm)

    metadata = {
        "genre": genre,
        "bpm": bpm,
        "sec_per_beat": round(sec_per_beat, 4),
        "sec_per_bar": round(sec_per_bar, 4),
        "duration_sec": duration_sec,
        "total_beats": len(beat_timestamps),
        "beat_timestamps": beat_timestamps,
        "downbeat_timestamps": downbeat_timestamps,
        "drop_timestamps": drop_timestamps,
    }
    return out_wav_path, metadata


def compute_beat_synced_video_cuts(
    total_duration: float,
    beat_metadata: Dict,
    min_cut_interval: float = 2.0,
    max_cut_interval: float = 4.5,
) -> List[Dict]:
    """Calculate video cut points and dynamic zoom pulses aligned with downbeats."""
    downbeats = beat_metadata.get("downbeat_timestamps", [])
    if not downbeats:
        sec_per_bar = float(beat_metadata.get("sec_per_bar", 2.0))
        downbeats = [i * sec_per_bar for i in range(int(total_duration / sec_per_bar) + 1)]

    cuts: List[Dict] = []
    last_cut = 0.0
    zoom_state = 1.0

    for db in downbeats:
        if db >= total_duration - 0.5:
            break
        interval = db - last_cut
        if interval >= min_cut_interval:
            # Alternate zoom punch between 1.00x and 1.14x for hypnotic visual rhythm
            zoom_state = 1.14 if zoom_state == 1.0 else 1.0
            cuts.append({
                "start": round(last_cut, 2),
                "end": round(db, 2),
                "duration": round(interval, 2),
                "punch_zoom": zoom_state,
                "is_downbeat": True,
            })
            last_cut = db

    if last_cut < total_duration:
        cuts.append({
            "start": round(last_cut, 2),
            "end": round(total_duration, 2),
            "duration": round(total_duration - last_cut, 2),
            "punch_zoom": 1.0,
            "is_downbeat": False,
        })

    return cuts
