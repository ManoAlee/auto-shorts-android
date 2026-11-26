"""Tests for NiazMorshed2007/reanimate ARM64-native motion integration."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_fit_motion_curve_detects_ease_out_expo_and_overshoot() -> None:
    from auto_shorts.reanimate_motion import EASINGS, fit_motion_curve

    fn = EASINGS["easeOutExpo"]
    series = [(i * 50.0, 100.0 * fn(i / 10.0)) for i in range(11)]
    res = fit_motion_curve(series)
    assert res["ok"] is True
    assert res["best_easing"]["name"] == "easeOutExpo"
    assert res["best_easing"]["rmse"] < 0.01
    assert res["spring_like"] is False

    back = EASINGS["easeOutBack"]
    series_back = [(i * 50.0, 100.0 * back(i / 10.0)) for i in range(11)]
    res_back = fit_motion_curve(series_back)
    assert res_back["ok"] is True
    assert res_back["spring_like"] is True
    assert res_back["overshoot"] > 0.05


def test_build_reanimate_motion_filter_valid_expressions() -> None:
    from auto_shorts.reanimate_motion import build_reanimate_motion_filter
    from auto_shorts.retention import build_pattern_interrupt_filter

    expr = build_pattern_interrupt_filter(1080, 1920, zoom=1.06, interval_sec=3.2)
    assert "scale=" in expr and "crop=1080:1920" in expr and "exp(" in expr
    assert "mod(" not in expr
    assert build_reanimate_motion_filter(1080, 1920, zoom=1.0) == ""

    if shutil.which("ffmpeg"):
        for curve in ("easeOutExpo", "easeOutBack", "linear"):
            vf = build_pattern_interrupt_filter(360, 640, zoom=1.06, interval_sec=3.2, curve=curve)
            proc = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=0.4", "-vf", vf, "-f", "null", "-"],
                capture_output=True, text=True, check=False,
            )
            assert proc.returncode == 0, f"FFmpeg rejected {curve} filter: {proc.stderr}"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_compute_activity_curve_and_compare_real_ffmpeg(tmp_path: Path) -> None:
    from auto_shorts.reanimate_motion import compare_motion_videos, compute_video_activity_curve

    static_mp4 = tmp_path / "static.mp4"
    dynamic_mp4 = tmp_path / "dynamic.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=128x224:d=2.0", "-r", "10", str(static_mp4)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=128x224:d=2.0", "-r", "10", str(dynamic_mp4)],
        check=True,
    )

    st = compute_video_activity_curve(static_mp4, fps=4, max_frames=12)
    dy = compute_video_activity_curve(dynamic_mp4, fps=4, max_frames=12)
    assert st["ok"] is True and st["frozen_ratio"] > 0.9 and st["mean_activity"] < 0.01
    assert dy["ok"] is True and dy["frozen_ratio"] < 0.2 and dy["mean_activity"] > 0.1
    assert dy["motion_score"] > st["motion_score"]

    cmp_same = compare_motion_videos(dynamic_mp4, dynamic_mp4, fps=4, max_frames=12)
    assert cmp_same["ok"] is True and cmp_same["passed"] is True
    assert cmp_same["mean_activity_diff"] == 0.0
