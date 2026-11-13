"""Higgsfield AI Cloud Cinema integration (Image & Video B-Roll generator, zero heavy deps)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("HiggsfieldAI")

HIGGSFIELD_API_BASE = os.getenv("HIGGSFIELD_API_BASE", "https://platform.higgsfield.ai/v1").strip().rstrip("/")


def get_higgsfield_api_key() -> str:
    """Return configured Higgsfield API key from environment."""
    return (
        os.getenv("HIGGSFIELD_API_KEY", "").strip()
        or os.getenv("HIGGSFIELD_KEY", "").strip()
    )


def is_higgsfield_configured() -> bool:
    """Return True when a Higgsfield API key is configured."""
    return bool(get_higgsfield_api_key())


def _api_request(
    endpoint: str,
    payload: Optional[Dict] = None,
    method: str = "POST",
    timeout: int = 30,
) -> Dict:
    api_key = get_higgsfield_api_key()
    if not api_key:
        raise RuntimeError("HIGGSFIELD_API_KEY nao configurada no .env")

    url = f"{HIGGSFIELD_API_BASE}/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AutoShorts-Android/2.7",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _poll_job_result(job_id: str, timeout_sec: int = 180, poll_interval: float = 4.0) -> Dict:
    deadline = time.time() + max(10, timeout_sec)
    while time.time() < deadline:
        status_obj = _api_request(f"jobs/{job_id}", payload=None, method="GET", timeout=20)
        st = str(status_obj.get("status") or "").lower()
        if st in {"completed", "succeeded", "done"}:
            return status_obj
        if st in {"failed", "error", "cancelled", "canceled"}:
            raise RuntimeError(f"Higgsfield job {job_id} falhou: {status_obj.get('error') or st}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Higgsfield job {job_id} excedeu {timeout_sec}s")


def _download_asset(url: str, out_path: Path, timeout: int = 45) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "AutoShorts-Android/2.7"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def generate_higgsfield_image(
    prompt: str,
    out_path: str | Path,
    aspect_ratio: str = "9:16",
    model: str = "soul-cinema",
    timeout_sec: int = 90,
) -> Path:
    """Generate a high-impact vertical cover/keyframe using Higgsfield Soul Cinema (~$0.003/img)."""
    res = _api_request(
        "images/generations",
        payload={
            "model": os.getenv("HIGGSFIELD_IMAGE_MODEL", model),
            "prompt": prompt[:900],
            "aspect_ratio": aspect_ratio,
        },
        method="POST",
        timeout=30,
    )
    asset_url = res.get("url") or (res.get("data") or [{}])[0].get("url")
    if not asset_url and res.get("job_id"):
        done = _poll_job_result(str(res["job_id"]), timeout_sec=timeout_sec)
        asset_url = done.get("url") or (done.get("outputs") or [{}])[0].get("url")
    if not asset_url:
        raise RuntimeError(f"Higgsfield nao retornou URL de imagem: {res}")
    return _download_asset(str(asset_url), Path(out_path))


def generate_higgsfield_video(
    prompt: str,
    out_path: str | Path,
    duration_sec: int = 5,
    aspect_ratio: str = "9:16",
    model: str = "genjutsu-light",
    image_url: Optional[str] = None,
    timeout_sec: int = 180,
) -> Path:
    """Generate a 5s cinematic hook/B-Roll clip via Higgsfield Text-to-Video or Image-to-Video."""
    payload: Dict = {
        "model": os.getenv("HIGGSFIELD_VIDEO_MODEL", model),
        "prompt": prompt[:900],
        "duration": max(3, min(10, int(duration_sec))),
        "aspect_ratio": aspect_ratio,
    }
    if image_url:
        payload["image_url"] = image_url

    res = _api_request("videos/generations", payload=payload, method="POST", timeout=30)
    asset_url = res.get("url") or (res.get("data") or [{}])[0].get("url")
    if not asset_url and res.get("job_id"):
        done = _poll_job_result(str(res["job_id"]), timeout_sec=timeout_sec)
        asset_url = done.get("url") or (done.get("outputs") or [{}])[0].get("url")
    if not asset_url:
        raise RuntimeError(f"Higgsfield nao retornou URL de video: {res}")
    return _download_asset(str(asset_url), Path(out_path))


def try_generate_hook_broll(
    prompt: str,
    work_dir: Path,
    duration_sec: int = 5,
) -> Optional[Path]:
    """Fail-safe helper: generate a 5s Higgsfield hook clip if configured, else return None."""
    if not is_higgsfield_configured():
        return None
    try:
        out_mp4 = Path(work_dir) / "higgsfield_hook.mp4"
        return generate_higgsfield_video(
            prompt=prompt,
            out_path=out_mp4,
            duration_sec=duration_sec,
            aspect_ratio="9:16",
        )
    except Exception as exc:
        logger.warning("Higgsfield hook B-Roll fallback (usando B-Roll local): %s", exc)
        return None
