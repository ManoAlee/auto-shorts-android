"""ComfyUI LAN GPU Client for Open-Source AI Video (Wan 2.2 / LTX-2 / HunyuanVideo).

Allows the Android Termux node to offload heavy AI cinema clip generation to a
Windows/Linux PC running ComfyUI on the local network (default port 8188),
with zero extra Python dependencies (pure stdlib urllib/json).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("ComfyUIClient")


def get_comfyui_url() -> str:
    """Return configured ComfyUI base URL (e.g. http://192.168.0.100:8188)."""
    return os.getenv("COMFYUI_URL", "").strip().rstrip("/")


def is_comfyui_reachable(timeout_sec: float = 2.0) -> bool:
    """Return True if ComfyUI is configured and responding on the LAN."""
    base = get_comfyui_url()
    if not base:
        return False
    try:
        req = urllib.request.Request(f"{base}/system_stats", headers={"User-Agent": "AutoShorts-Android/2.7"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.status == 200
    except Exception:
        return False


def build_wan22_text2video_workflow(
    prompt: str,
    negative_prompt: str = "blurry, low quality, watermark, text, distorted face, static",
    width: int = 480,
    height: int = 832,
    length_frames: int = 81,
    steps: int = 20,
    cfg: float = 5.0,
    seed: Optional[int] = None,
    ckpt_name: Optional[str] = None,
) -> Dict:
    """Build a standard ComfyUI API prompt graph for Wan 2.2 / Wan 2.1 vertical 9:16 video."""
    model_name = ckpt_name or os.getenv("COMFYUI_WAN_CKPT", "wan2.2_ti2v_5B_fp16.safetensors")
    vae_name = os.getenv("COMFYUI_WAN_VAE", "wan2.2_vae.safetensors")
    clip_name = os.getenv("COMFYUI_WAN_CLIP", "umt5_xxl_fp8_e4m3fn_scaled.safetensors")
    used_seed = int(seed if seed is not None else (int(time.time() * 1000) % 2_147_483_647))

    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": model_name, "weight_dtype": "fp8_e4m3fn"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "wan"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt[:900], "clip": ["2", 0]},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt[:400], "clip": ["2", 0]},
        },
        "6": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {"width": width, "height": height, "length": length_frames, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": used_seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["3", 0]},
        },
        "9": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "frame_rate": 16,
                "loop_count": 0,
                "filename_prefix": "autoshorts_wan",
                "format": "video/h264-mp4",
                "save_output": True,
                "images": ["8", 0],
            },
        },
    }


def queue_comfyui_workflow(workflow: Dict, timeout_sec: int = 300) -> Optional[Path]:
    """Submit a workflow to ComfyUI /prompt, poll /history/{id}, and return output metadata."""
    base = get_comfyui_url()
    if not base:
        raise RuntimeError("COMFYUI_URL nao configurado no .env")

    client_id = uuid.uuid4().hex[:12]
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/prompt",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AutoShorts-Android/2.7"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        queued = json.loads(resp.read().decode("utf-8"))
    prompt_id = str(queued.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI nao retornou prompt_id: {queued}")

    deadline = time.time() + max(20, timeout_sec)
    while time.time() < deadline:
        time.sleep(3.0)
        h_req = urllib.request.Request(f"{base}/history/{prompt_id}", headers={"User-Agent": "AutoShorts-Android/2.7"})
        with urllib.request.urlopen(h_req, timeout=15) as h_resp:
            history = json.loads(h_resp.read().decode("utf-8"))
        entry = history.get(prompt_id)
        if not entry:
            continue
        outputs = entry.get("outputs") or {}
        for node_out in outputs.values():
            for key in ("gifs", "videos", "images"):
                items = node_out.get(key) or []
                for item in items:
                    fname = item.get("filename")
                    if fname and str(fname).lower().endswith((".mp4", ".webm", ".gif")):
                        return item  # type: ignore[return-value]
        if (entry.get("status") or {}).get("status_str") == "error":
            raise RuntimeError(f"ComfyUI falhou na execucao do prompt {prompt_id}")
    raise TimeoutError(f"ComfyUI excedeu {timeout_sec}s aguardando {prompt_id}")


def generate_comfyui_video(
    prompt: str,
    out_path: str | Path,
    duration_sec: int = 5,
    timeout_sec: int = 300,
) -> Path:
    """Generate a vertical 9:16 AI video clip on LAN ComfyUI (Wan 2.2) and download it."""
    base = get_comfyui_url()
    if not base:
        raise RuntimeError("COMFYUI_URL nao configurado")
    frames = max(33, min(121, int(duration_sec) * 16 + 1))
    wf = build_wan22_text2video_workflow(prompt=prompt, length_frames=frames)
    meta = queue_comfyui_workflow(wf, timeout_sec=timeout_sec)
    if not isinstance(meta, dict) or not meta.get("filename"):
        raise RuntimeError("ComfyUI concluiu sem gerar arquivo de video")

    qs = urllib.parse.urlencode({
        "filename": meta["filename"],
        "subfolder": meta.get("subfolder", ""),
        "type": meta.get("type", "output"),
    })
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(f"{base}/view?{qs}", headers={"User-Agent": "AutoShorts-Android/2.7"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        out_file.write_bytes(resp.read())
    return out_file


def try_generate_ai_hook_clip(
    prompt: str,
    work_dir: Path,
    duration_sec: int = 5,
) -> Optional[Path]:
    """Cascade: LAN ComfyUI (Wan 2.2/LTX-2, free) -> Higgsfield Cloud -> None (local B-Roll)."""
    out_mp4 = Path(work_dir) / "ai_hook_broll.mp4"
    if is_comfyui_reachable():
        try:
            logger.info("Gerando gancho AI via ComfyUI LAN (%s)...", get_comfyui_url())
            return generate_comfyui_video(prompt=prompt, out_path=out_mp4, duration_sec=duration_sec)
        except Exception as exc:
            logger.warning("ComfyUI fallback: %s", exc)

    from .higgsfield import try_generate_hook_broll
    return try_generate_hook_broll(prompt=prompt, work_dir=work_dir, duration_sec=duration_sec)

