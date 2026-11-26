"""Reanimate Motion Engine — ARM64-native Python port of NiazMorshed2007/reanimate.

Provides:
1. Exact cubic-bezier solver & RMSE curve fitting (from reanimate/scripts/easing.ts).
2. Eased FFmpeg pattern-interrupt filter expressions (easeOutExpo / easeOutBack / material).
3. Frame-to-frame activity curve & frozen-frame detection via FFmpeg rawvideo pipe
   (from reanimate/scripts/compare.ts), running in <1s on Android Termux without Bun/Playwright.
4. Reference-vs-clone motion timing comparison for viral reverse-engineering.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple


def _bezier(x1: float, y1: float, x2: float, y2: float) -> Callable[[float], float]:
    """Solve cubic-bezier(x1, y1, x2, y2) at time t via bisection (port of reanimate/easing.ts)."""
    def _eval(t: float) -> float:
        if t <= 0.0:
            return 0.0
        if t >= 1.0:
            return 1.0
        lo, hi, u = 0.0, 1.0, t
        for _ in range(28):
            u = 0.5 * (lo + hi)
            x = 3.0 * ((1.0 - u) ** 2) * u * x1 + 3.0 * (1.0 - u) * (u ** 2) * x2 + (u ** 3)
            if x < t:
                lo = u
            else:
                hi = u
        return 3.0 * ((1.0 - u) ** 2) * u * y1 + 3.0 * (1.0 - u) * (u ** 2) * y2 + (u ** 3)
    return _eval


EASINGS: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease": _bezier(0.25, 0.1, 0.25, 1.0),
    "ease-in": _bezier(0.42, 0.0, 1.0, 1.0),
    "ease-out": _bezier(0.0, 0.0, 0.58, 1.0),
    "ease-in-out": _bezier(0.42, 0.0, 0.58, 1.0),
    "materialStandard": _bezier(0.4, 0.0, 0.2, 1.0),
    "materialEmphasized": _bezier(0.2, 0.0, 0.0, 1.0),
    "easeOutExpo": _bezier(0.16, 1.0, 0.3, 1.0),
    "easeOutQuint": _bezier(0.22, 1.0, 0.36, 1.0),
    "easeOutCubic": _bezier(0.33, 1.0, 0.68, 1.0),
    "easeOutQuart": _bezier(0.25, 1.0, 0.5, 1.0),
    "easeInOutCubic": _bezier(0.65, 0.0, 0.35, 1.0),
    "easeOutBack": _bezier(0.34, 1.56, 0.64, 1.0),
    "easeInOutBack": _bezier(0.68, -0.6, 0.32, 1.6),
    "power3InOut": _bezier(0.77, 0.0, 0.175, 1.0),
}


def fit_motion_curve(series: Sequence[Tuple[float, float]]) -> Dict:
    """Fit a [t_ms, value] motion series to named easings, reporting delay, duration, overshoot, and RMSE."""
    pts = [(float(t), float(v)) for t, v in series]
    if len(pts) < 4:
        return {"ok": False, "error": "not_enough_samples"}

    t0 = pts[0][0]
    start = pts[0][1]
    end = pts[-1][1]
    val_range = end - start
    eps = max(abs(val_range) * 0.01, 0.002)

    first_change = next((i for i, (_, v) in enumerate(pts) if abs(v - start) > eps), 1)
    first_change = max(1, first_change)
    last_change = len(pts) - 1
    for i in range(len(pts) - 1, 0, -1):
        if abs(pts[i][1] - end) > eps:
            last_change = min(len(pts) - 1, i + 1)
            break

    delay_ms = round(pts[first_change - 1][0] - t0, 2)
    dur_ms = round(pts[last_change][0] - pts[first_change - 1][0], 2)

    if val_range == 0:
        overshoot = 0.0
    else:
        sign = 1.0 if val_range > 0 else -1.0
        max_disp = max((v - start) * sign for _, v in pts)
        overshoot = round(max(0.0, (max_disp - abs(val_range)) / abs(val_range)), 4)

    fits: List[Dict] = []
    if abs(val_range) > 0 and dur_ms > 0:
        base_t = pts[first_change - 1][0]
        raw = [(t - base_t, (v - start) / val_range) for t, v in pts[first_change - 1:]]
        for name, fn in EASINGS.items():
            best_rmse = float("inf")
            best_dur = dur_ms
            for step in range(21):
                d = dur_ms * (1.0 + step * 0.05)
                sq_err = 0.0
                for t_rel, y_norm in raw:
                    u = min(1.0, max(0.0, t_rel / d))
                    err = fn(u) - y_norm
                    sq_err += err * err
                rmse = math.sqrt(sq_err / len(raw))
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_dur = d
            fits.append({"name": name, "rmse": round(best_rmse, 5), "duration_ms": round(best_dur, 1)})
        fits.sort(key=lambda r: r["rmse"])

    return {
        "ok": True,
        "start": start,
        "end": end,
        "delay_ms": delay_ms,
        "duration_ms": dur_ms,
        "overshoot": overshoot,
        "spring_like": overshoot > 0.03,
        "best_easing": fits[0] if fits else None,
        "top_fits": fits[:4],
    }


def build_reanimate_motion_filter(
    width: int,
    height: int,
    zoom: float = 1.06,
    interval_sec: float = 3.2,
    curve: str = "easeOutExpo",
) -> str:
    """Build a zero-overhead FFmpeg scale+crop filter using reanimate easing dynamics.

    Unlike flat sinusoidal zoom, easeOutExpo / easeOutBack snaps rapidly at each beat
    boundary and settles smoothly, creating authentic editorial punch-in retention.
    """
    if zoom <= 1.0:
        return ""
    amp = max(0.005, zoom - 1.0)
    period = max(1.5, float(interval_sec))
    phase = f"(mod(t,{period:.2f})/{period:.2f})"
    if curve == "easeOutBack":
        # Fast snap with subtle overshoot settle
        envelope = f"(1-pow(1-{phase},3)*(1+0.35*sin(PI*{phase})))"
    elif curve == "linear":
        envelope = f"(1-abs(2*{phase}-1))"
    else:
        # easeOutExpo-inspired beat pulse: sharp attack in first 25%, smooth hold/release
        envelope = f"(exp(-4.5*{phase})*(1-exp(-18*{phase})))"

    scale_expr = f"(1+{amp:.4f}*{envelope})"
    return (
        f"scale='trunc((iw*{scale_expr})/2)*2':"
        f"'trunc((ih*{scale_expr})/2)*2':eval=frame,"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
    )


def _extract_gray_frames(video_path: Path, fps: int = 4, w: int = 96, h: int = 170, max_frames: int = 48) -> List[bytes]:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin or not video_path.is_file():
        return []
    frame_size = w * h
    cmd = [
        ffmpeg_bin,
        "-v", "error",
        "-i", str(video_path),
        "-vf", f"fps={max(1, fps)},scale={w}:{h}",
        "-frames:v", str(max(2, max_frames)),
        "-f", "rawvideo",
        "-pix_fmt", "gray",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False, timeout=25)
    if proc.returncode != 0 or len(proc.stdout) < frame_size * 2:
        return []
    raw = proc.stdout
    count = min(max_frames, len(raw) // frame_size)
    return [raw[i * frame_size : (i + 1) * frame_size] for i in range(count)]


def _frame_diff_ratio(a: bytes, b: bytes, threshold: int = 18) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    changed = sum(1 for x, y in zip(a, b) if abs(x - y) > threshold)
    return changed / n


def compute_video_activity_curve(
    video_path: str | Path,
    fps: int = 4,
    max_frames: int = 48,
    pixel_diff_threshold: int = 18,
) -> Dict:
    """Measure frame-to-frame visual motion activity (port of reanimate/scripts/compare.ts)."""
    p = Path(video_path)
    frames = _extract_gray_frames(p, fps=fps, max_frames=max_frames)
    if len(frames) < 2:
        return {
            "ok": False,
            "frames": len(frames),
            "activity": [],
            "mean_activity": 0.0,
            "frozen_ratio": 1.0,
            "beat_peaks": 0,
            "motion_score": 0,
        }

    act: List[float] = [0.0]
    for i in range(1, len(frames)):
        act.append(round(_frame_diff_ratio(frames[i - 1], frames[i], threshold=pixel_diff_threshold), 4))

    deltas = act[1:]
    mean_act = sum(deltas) / len(deltas)
    frozen_cnt = sum(1 for v in deltas if v < 0.008)
    frozen_ratio = frozen_cnt / len(deltas)
    peaks = sum(
        1
        for i in range(1, len(act) - 1)
        if act[i] >= 0.05 and act[i] >= act[i - 1] and act[i] >= act[i + 1]
    )

    # Score: healthy Shorts have mean_activity in 0.03..0.35, low frozen_ratio, and regular beat peaks
    score = 100.0
    if frozen_ratio > 0.35:
        score -= (frozen_ratio - 0.35) * 85.0
    if mean_act < 0.015:
        score -= 25.0
    if peaks == 0 and len(frames) >= 12:
        score -= 15.0
    motion_score = int(max(0, min(100, round(score))))

    return {
        "ok": True,
        "fps": fps,
        "frames": len(frames),
        "activity": act,
        "mean_activity": round(mean_act, 4),
        "frozen_ratio": round(frozen_ratio, 4),
        "beat_peaks": peaks,
        "motion_score": motion_score,
    }


def compare_motion_videos(
    ref_video: str | Path,
    clone_video: str | Path,
    fps: int = 4,
    max_frames: int = 40,
    max_shift: int = 6,
) -> Dict:
    """Compare two videos by activity curve timing alignment (port of reanimate/compare.ts)."""
    ref_res = compute_video_activity_curve(ref_video, fps=fps, max_frames=max_frames)
    clone_res = compute_video_activity_curve(clone_video, fps=fps, max_frames=max_frames)
    if not ref_res.get("ok") or not clone_res.get("ok"):
        return {"ok": False, "error": "failed_to_extract_frames", "ref": ref_res, "clone": clone_res}

    ra = ref_res["activity"]
    ca = clone_res["activity"]
    best_offset = 0
    best_mae = float("inf")
    for off in range(-max_shift, max_shift + 1):
        diffs: List[float] = []
        for i in range(len(ra)):
            j = i + off
            if 0 <= j < len(ca):
                diffs.append(abs(ra[i] - ca[j]))
        if len(diffs) >= 4:
            mae = sum(diffs) / len(diffs)
            if mae < best_mae:
                best_mae = mae
                best_offset = off

    timing_error_sec = round(abs(best_offset) / max(1, fps), 3)
    return {
        "ok": True,
        "best_frame_offset": best_offset,
        "timing_error_sec": timing_error_sec,
        "mean_activity_diff": round(best_mae, 4),
        "passed": best_mae <= 0.08 and timing_error_sec <= 0.25,
        "ref_motion_score": ref_res["motion_score"],
        "clone_motion_score": clone_res["motion_score"],
    }
