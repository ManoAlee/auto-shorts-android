"""Sunlit Light Studio Web App (/frontend-a11y WCAG 2.1 AA + /frontend-design) for Termux & Desktop."""

import argparse
import html
import ipaddress
import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

from .anime_trends import get_releasing_anime_radar
from .config import LOUDNORM_FILTER, METADATA_SCRUB, NICHES, PLATFORMS, load_dotenv_file
from .evolution import EvolutionStore
from .gameplay import discover_dynamic_visual_queries, ensure_gameplay_library, fetch_gameplay_clip, list_gameplay_clips
from .horizon_radar import _ptbr_headline, build_horizon_spoken_script, fetch_horizon_trends
from .narrator import (
    DEFAULT_STYLE_KEY,
    VOICE_STYLES,
    active_tts_engine_label,
    build_narrated_short,
    list_clean_backgrounds,
    preview_voice,
)
from .pipeline import run_autopilot, run_pipeline
from .publisher import (
    get_youtube_channel_summary,
    optimize_existing_publish_pack,
    publish_pack_to_instagram_reels,
    publish_pack_to_youtube,
)
from .re_engine import (
    analyze_kinetic_pacing,
    get_synapse_overview,
    inspect_youtube_innertube,
    rea_trace_system,
    record_synapse_stage,
    score_short_opus_runbook,
)
from .offline_llm import (
    answer_studio_question_offline,
    benchmark_local_llm,
    detect_android_llm_capabilities,
)
from .team import build_persona_script_brief, generate_channel_planner, is_llm_configured, list_channel_personas
from .validator import audit_short_end_to_end, validate_generated_short
from .world_news import fetch_world_news_headlines, produce_world_news_short
from .yt_algorithm import rank_feed_for_channel, score_short_for_youtube_algorithm


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_MAX_POST_BYTES = 1_048_576


def _safe_child_path(base_dir: Path, raw_name: str) -> Path | None:
    raw = str(raw_name or "").strip()
    if not raw or "/" in raw or "\\" in raw or ".." in raw or "\x00" in raw:
        return None
    if not _SAFE_NAME_RE.match(raw):
        return None
    root = base_dir.resolve()
    cand = root / raw
    if cand.is_symlink():
        return None
    resolved = cand.resolve()
    if resolved.parent != root:
        return None
    return resolved


def _is_safe_public_http_url(url: str) -> bool:
    u = (url or "").strip()
    if not u or u.startswith("-"):
        return False
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


_JOB_LOCK = threading.RLock()
_JOB_STATE: Dict = {
    "running": False,
    "last_status": "Pronto para operar",
    "last_error": "",
    "last_result": None,
    "queued": 0,
    "stage_index": 0,
    "stage_total": 5,
    "stage_label": "",
    "progress_pct": 0,
    "started_at": 0.0,
    "elapsed_sec": 0.0,
}
_JOB_QUEUE: "queue.Queue[tuple[str, object]]" = queue.Queue()
_QUEUE_WORKER_STARTED = False
_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def _set_job_progress(stage_index: int, stage_total: int, stage_label: str, progress_pct: int) -> None:
    now = time.time()
    started = float(_JOB_STATE.get("started_at") or now)
    _JOB_STATE.update({
        "stage_index": int(stage_index),
        "stage_total": int(stage_total),
        "stage_label": str(stage_label),
        "progress_pct": max(0, min(100, int(progress_pct))),
        "last_status": str(stage_label),
        "elapsed_sec": round(max(0.0, now - started), 1),
    })


def _ensure_queue_worker() -> None:
    global _QUEUE_WORKER_STARTED
    if _QUEUE_WORKER_STARTED:
        return
    _QUEUE_WORKER_STARTED = True

    def _runner() -> None:
        while True:
            label, fn = _JOB_QUEUE.get()
            try:
                with _JOB_LOCK:
                    _JOB_STATE.update({
                        "running": True,
                        "last_error": "",
                        "last_status": label,
                        "stage_index": 1,
                        "stage_total": 5,
                        "stage_label": label,
                        "progress_pct": 12,
                        "started_at": time.time(),
                        "elapsed_sec": 0.0,
                        "queued": _JOB_QUEUE.qsize(),
                    })
                    try:
                        fn()
                        _JOB_STATE.update({"progress_pct": 100, "stage_index": 5})
                    except Exception as exc:
                        _JOB_STATE.update({"running": False, "last_status": "Falha no processamento", "last_error": str(exc)})
            finally:
                started = float(_JOB_STATE.get("started_at") or time.time())
                _JOB_STATE["elapsed_sec"] = round(max(0.0, time.time() - started), 1)
                _JOB_STATE["running"] = False
                _JOB_STATE["queued"] = _JOB_QUEUE.qsize()
                _JOB_QUEUE.task_done()

    threading.Thread(target=_runner, daemon=True).start()


def _enqueue_job(label: str, fn: object) -> int:
    _ensure_queue_worker()
    _JOB_QUEUE.put((label, fn))
    qsize = _JOB_QUEUE.qsize()
    _JOB_STATE["queued"] = qsize
    return qsize


def _load_frontend_bundle() -> str:
    tokens_css = (_FRONTEND_DIR / "tokens.css").read_text(encoding="utf-8")
    studio_css = (_FRONTEND_DIR / "studio.css").read_text(encoding="utf-8")
    studio_js = (_FRONTEND_DIR / "studio.js").read_text(encoding="utf-8")
    shell_html = (_FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    return (
        shell_html
        .replace("__INLINE_CSS__", tokens_css + "\n" + studio_css)
        .replace("__INLINE_JS__", studio_js)
    )


def render_dashboard_html(out_dir: str | Path = "output") -> str:
    niche_opts = ['<option value="all">Todos os nichos (rotacao automatica)</option>']
    for key, profile in NICHES.items():
        selected = ' selected' if key == "podcast" else ""
        niche_opts.append(f'<option value="{html.escape(key)}"{selected}>{html.escape(profile.label)}</option>')

    plat_opts = []
    for key, preset in PLATFORMS.items():
        selected = ' selected' if key == "youtube_shorts" else ""
        plat_opts.append(f'<option value="{html.escape(key)}"{selected}>{html.escape(key)} ({html.escape(preset.sweet_spot)})</option>')

    voice_opts = []
    for k, v in VOICE_STYLES.items():
        selected = ' selected' if k == DEFAULT_STYLE_KEY else ""
        voice_opts.append(f'<option value="{html.escape(k)}"{selected}>{html.escape(v.label)}</option>')

    bg_opts = [
        f'<option value="{html.escape(bg)}"></option>'
        for bg in list_clean_backgrounds(Path(out_dir))
    ]
    return (
        _load_frontend_bundle()
        .replace("__NICHE_OPTIONS__", "".join(niche_opts))
        .replace("__NICHE_SIMPLE_OPTIONS__", "".join(niche_opts[1:]))
        .replace("__PLATFORM_OPTIONS__", "".join(plat_opts))
        .replace("__VOICE_OPTIONS__", "".join(voice_opts))
        .replace("__BG_OPTIONS__", "".join(bg_opts))
        .replace("__TTS_ENGINE__", html.escape(active_tts_engine_label()))
    )


def list_generated_videos(out_dir: Path) -> List[Dict]:
    if not out_dir.exists():
        return []
    items: List[Dict] = []
    for mp4 in sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        if mp4.stat().st_size < 50000:
            continue
        pack_file = mp4.with_suffix(".publish.json")
        pack = {}
        if pack_file.is_file():
            try:
                pack = json.loads(pack_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pack = {}
        thumb_16 = mp4.with_name(f"{mp4.stem}_thumb_16x9.jpg")
        validation = pack.get("validation")
        algo = pack.get("algorithm") or score_short_for_youtube_algorithm(pack, validation, mp4.name)
        items.append({
            "filename": mp4.name,
            "size_mb": round(mp4.stat().st_size / (1024 * 1024), 2),
            "title": pack.get("title", mp4.name),
            "hook_title": pack.get("hook_title", ""),
            "hashtags": pack.get("hashtags", []),
            "caption": pack.get("caption", ""),
            "thumb_16x9": thumb_16.name if thumb_16.is_file() else None,
            "validation": validation,
            "visual_audit": pack.get("visual_audit"),
            "background_style": pack.get("background_style", ""),
            "queued_for_auto_publish": bool(pack.get("queued_for_auto_publish", False)),
            "delivery_status": pack.get("delivery_status", ""),
            "algorithm": algo,
            "opus_scorecard": score_short_opus_runbook(pack, validation=validation),
            "youtube": pack.get("youtube"),
        })
    return rank_feed_for_channel(items)


def _probe_local_llm() -> Dict:
    base = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1").strip().rstrip("/")
    if not base.startswith("http"):
        return {"online": False, "model": ""}
    try:
        with urllib.request.urlopen(f"{base}/models", timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("data") or []
        name = str(models[0].get("id") if models else "llama-local")
        return {"online": True, "model": name, "url": base}
    except Exception:
        return {"online": False, "model": "", "url": base}


def _scheduler_path(out_dir: Path) -> Path:
    return out_dir / "scheduler.json"


def _load_scheduler_cfg(out_dir: Path) -> Dict:
    default = {
        "enabled": os.getenv("AUTO_PILOT_ENABLED", "1") != "0",
        "interval_hours": 4,
        "niche": "all",
        "platform": "youtube_shorts",
        "auto_publish": True,
        "runs_completed": 0,
        "last_run_at": "",
        "next_run_ts": time.time() + 14400,
    }
    p = _scheduler_path(out_dir)
    if p.is_file():
        try:
            saved = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                default.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
    return default


def _save_scheduler_cfg(out_dir: Path, cfg: Dict) -> Dict:
    _scheduler_path(out_dir).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


_AUTO_NICHE_ROTATION = (
    "noticias_mundiais",
    "entretenimento_animes",
    "ia_tech",
    "financas",
    "podcast",
    "desenvolvimento_pessoal",
    "saude_fitness",
    "concursos",
)


def _run_autonomous_cycle_core(out_dir: Path, cfg: Dict) -> None:
    raw_niche = str(cfg.get("niche") or "all")
    active_niche = (
        _AUTO_NICHE_ROTATION[int(cfg.get("runs_completed", 0)) % len(_AUTO_NICHE_ROTATION)]
        if raw_niche == "all"
        else raw_niche
    )
    _JOB_STATE.update({
        "running": True, "last_error": "", "started_at": time.time(),
        "stage_index": 1, "stage_total": 5, "progress_pct": 15,
        "stage_label": f"1/5 Piloto ({active_niche}) coletando fonte...",
        "last_status": f"Piloto automatico ({active_niche}) em execucao...",
    })
    try:
        if active_niche == "noticias_mundiais":
            _set_job_progress(2, 5, f"2/5 Traduzindo noticia {active_niche} + Voz Kokoro...", 42)
            res = produce_world_news_short(
                out_dir=out_dir,
                topic="world",
                auto_publish=bool(cfg.get("auto_publish", True)),
                use_llm=is_llm_configured(),
            )
        else:
            _set_job_progress(3, 5, f"3/5 Renderizando corte 9:16 + Karaokê ({active_niche})...", 58)
            res = run_autopilot(
                out_dir=out_dir,
                platform=cfg.get("platform", "youtube_shorts"),
                niche=active_niche,
                num_clips=1,
                layout="blur_bg",
                use_llm=is_llm_configured(),
                auto_layout=True,
                auto_publish=bool(cfg.get("auto_publish", True)),
            )
        _set_job_progress(5, 5, f"5/5 Ciclo ({active_niche}) validado na fila!", 100)
        cfg["runs_completed"] = int(cfg.get("runs_completed", 0)) + 1
        cfg["last_run_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        cfg["next_run_ts"] = time.time() + max(1, int(cfg.get("interval_hours", 4))) * 3600
        _save_scheduler_cfg(out_dir, cfg)
        dstatus = str(res.get("delivery_status") or "")
        done_msg = (
            f"Ciclo ({active_niche}) salvo na fila (cota YouTube)!"
            if "queued_quota_limit" in dstatus
            else f"Ciclo automatico concluido ({active_niche}) e publicado!"
        )
        _JOB_STATE.update({"running": False, "last_status": done_msg, "last_result": res})
    except Exception as exc:
        _JOB_STATE.update({"running": False, "last_status": "Falha no piloto automatico", "last_error": str(exc)})


def _flush_pending_publishes(out_dir: Path) -> bool:
    """Retry uploading validated local Shorts waiting without a YouTube video_id.

    Returns True if a queued upload succeeded, False otherwise.
    """
    if not (os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and os.getenv("YT_REFRESH_TOKEN")):
        return False
    if not out_dir.exists():
        return False
    for mp4 in sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime):
        pack_file = mp4.with_suffix(".publish.json")
        if not pack_file.is_file():
            continue
        try:
            pack = json.loads(pack_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        yt = pack.get("youtube") or {}
        if isinstance(yt, dict) and yt.get("video_id"):
            continue
        val = pack.get("validation") or {}
        if not val.get("valid"):
            continue
        vis = pack.get("visual_audit")
        if not isinstance(vis, dict):
            ass_cand = mp4.parent / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass"
            vis = audit_short_end_to_end(mp4, pack=pack, ass_path=ass_cand if ass_cand.is_file() else None, vision_check=False)
            pack["visual_audit"] = vis
            pack["queued_for_auto_publish"] = bool(vis.get("approved"))
            pack_file.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        if not vis.get("approved") or pack.get("queued_for_auto_publish") is False:
            continue
        try:
            res = publish_pack_to_youtube(mp4)
            _JOB_STATE["last_status"] = f"Fila automatica publicada no YouTube: {res.get('video_id')}"
            return True
        except Exception as exc:
            if "uploadLimitExceeded" in str(exc):
                return False
    return False


def _trigger_autonomous_cycle(out_dir: Path, cfg: Dict) -> None:
    if _JOB_STATE["running"]:
        return
    with _JOB_LOCK:
        _run_autonomous_cycle_core(out_dir, cfg)


def _has_internet(timeout: float = 2.5) -> bool:
    for target in (("1.1.1.1", 443), ("www.youtube.com", 443)):
        try:
            with socket.create_connection(target, timeout=timeout):
                return True
        except OSError:
            continue
    return False


_TUNNEL_STATE: Dict = {"url": "", "token": "", "proc": None}


def _get_local_ip() -> str:
    """Return active Wi-Fi/LAN IPv4 address without netlink permission errors on Android."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.0)
            s.connect(("1.1.1.1", 80))
            return str(s.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def _notify_android_ip(ip: str, port: int = 8787) -> None:
    """Update persistent Android notification with current LAN URL when network changes."""
    notif_bin = shutil.which("termux-notification")
    if not notif_bin:
        return
    url = f"http://{ip}:{port}/"
    t_url = _TUNNEL_STATE.get("url") or ""
    body = f"Acesse: {url}" + (f" | Link externo ativo" if t_url else "")
    try:
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "posix":
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            [notif_bin, "--id", "autoshorts", "--title", "AutoShorts Pro Ativo", "--content", body, "--ongoing"],
            **kwargs,
        )
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    proc.kill()
            else:
                proc.kill()
    except Exception:
        pass


def _start_cloudflare_tunnel(port: int = 8787) -> Dict:
    """Start an on-demand trycloudflare.com HTTPS tunnel gated by a per-session secret token."""
    cf_bin = shutil.which("cloudflared")
    if not cf_bin:
        return {"url": "", "message": "cloudflared nao instalado (instale com: pkg install -y cloudflared)"}
    if _TUNNEL_STATE.get("url") and _TUNNEL_STATE.get("proc") and _TUNNEL_STATE["proc"].poll() is None:
        tok = _TUNNEL_STATE["token"]
        return {"url": f"{_TUNNEL_STATE['url']}/?token={tok}", "token": tok}

    tok = secrets.token_urlsafe(12)
    log_path = Path.home() / "auto-shorts-android" / "output" / "cloudflared.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [cf_bin, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    _TUNNEL_STATE.update({"proc": proc, "token": tok, "url": ""})
    deadline = time.time() + 14.0
    found_url = ""
    while time.time() < deadline and proc.poll() is None and proc.stdout is not None:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            found_url = m.group(0)
            break
    if found_url:
        _TUNNEL_STATE["url"] = found_url
        return {"url": f"{found_url}/?token={tok}", "token": tok}
    return {"url": "", "message": "Tunel iniciando — tente novamente em 5s."}


def _autonomous_loop(out_dir: Path) -> None:
    last_flush_ts = 0.0
    last_ip = ""
    while True:
        time.sleep(20)
        try:
            cur_ip = _get_local_ip()
            if cur_ip and cur_ip != last_ip:
                last_ip = cur_ip
                _notify_android_ip(cur_ip, 8787)
            cfg = _load_scheduler_cfg(out_dir)
            if not cfg.get("enabled") or _JOB_STATE["running"]:
                continue
            now = time.time()
            if cfg.get("auto_publish", True) and (now - last_flush_ts) >= 1800 and _has_internet():
                last_flush_ts = now
                if _JOB_LOCK.acquire(blocking=False):
                    try:
                        _flush_pending_publishes(out_dir)
                    finally:
                        _JOB_LOCK.release()
            if now < float(cfg.get("next_run_ts", 0)):
                continue
            if not _has_internet():
                _JOB_STATE.update({"last_status": "Aguardando rede Wi-Fi/internet para postar automaticamente..."})
                continue
            _trigger_autonomous_cycle(out_dir, cfg)
        except Exception:
            pass


def build_system_diagnostics(out_dir: Path) -> Dict:
    usage = shutil.disk_usage(str(out_dir if out_dir.exists() else Path(".")))
    c_bin = out_dir.parent / "bin" / "media_audit"
    llm_info = _probe_local_llm()
    gguf_dir = Path.home() / "models" / "llm"
    gguf_files = sorted(gguf_dir.glob("*.gguf")) if gguf_dir.is_dir() else []
    llm_info["model_file"] = gguf_files[0].name.split("-instruct")[0] if gguf_files else ""
    cur_ip = _get_local_ip()
    boot_script = Path.home() / ".termux" / "boot" / "start-autoshorts.sh"
    return {
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "lan_url": f"http://{cur_ip}:8787/",
        "tools": {
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "whisper": shutil.which("whisper-cli") is not None,
            "yt_dlp": shutil.which("yt-dlp") is not None,
            "media_audit_c": c_bin.is_file(),
            "llama_offline": llm_info["online"] or bool(gguf_files),
            "cloudflared": shutil.which("cloudflared") is not None,
            "boot_ready": boot_script.is_file(),
        },
        "keys": {
            "youtube": bool(os.getenv("YT_REFRESH_TOKEN", "").strip()),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
            "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "huggingface": bool(os.getenv("HF_TOKEN", "").strip()),
            "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY", "").strip()),
            "openai": bool(os.getenv("OPENAI_API_KEY", "").strip() and os.getenv("OPENAI_API_KEY", "").strip().lower() != "local"),
        },
        "tts_engine": active_tts_engine_label(),
        "local_llm": llm_info,
        "offline_ai": detect_android_llm_capabilities(),
    }


class _StudioHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_handler(out_dir: Path):
    class AppHandler(BaseHTTPRequestHandler):
        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def _safe_write(self, data: bytes) -> None:
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def _send_json(self, code: int, payload: Dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self._safe_write(raw)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def _send_error(self, code: int, error_code: str, message: str) -> None:
            self._send_json(code, {"error": {"code": error_code, "message": message}, "message": message})

        def _check_tunnel_auth(self, parsed_url) -> Optional[str]:
            """Require secret session token when accessed via public trycloudflare.com tunnel."""
            host = str(self.headers.get("Host") or "").lower().split(":", 1)[0]
            if not host.endswith(".trycloudflare.com"):
                return None
            secret = str(_TUNNEL_STATE.get("token") or "")
            if not secret:
                return None
            qs = urllib.parse.parse_qs(parsed_url.query)
            q_tok = (qs.get("token") or [""])[0]
            if secrets.compare_digest(q_tok, secret):
                return secret
            cookie_hdr = str(self.headers.get("Cookie") or "")
            for part in cookie_hdr.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    if k == "studio_tok" and secrets.compare_digest(v.strip(), secret):
                        return None
            return "DENY"

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            auth_res = self._check_tunnel_auth(parsed)
            if auth_res == "DENY":
                self._send_json(403, {"message": "Acesso externo exige token valido do tunel."})
                return
            if parsed.path == "/":
                body = render_dashboard_html(out_dir=out_dir).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                if auth_res:
                    self.send_header("Set-Cookie", f"studio_tok={auth_res}; Path=/; HttpOnly; SameSite=Lax")
                self.end_headers()
                self._safe_write(body)
                return

            if parsed.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            if parsed.path == "/icon.svg":
                svg = (
                    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'>"
                    "<rect width='192' height='192' rx='40' fill='#CC0000'/>"
                    "<polygon points='76,54 144,96 76,138' fill='#FFFFFF'/>"
                    "</svg>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg)))
                self.end_headers()
                self._safe_write(svg)
                return

            if parsed.path == "/manifest.webmanifest":
                manifest = {
                    "name": "YouTube Studio — AutoShorts Mobile",
                    "short_name": "AutoShorts",
                    "start_url": "/",
                    "display": "standalone",
                    "background_color": "#F9F9F9",
                    "theme_color": "#CC0000",
                    "icons": [
                        {"src": "/icon.svg", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"},
                        {"src": "/icon.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"},
                    ],
                }
                self._send_json(200, manifest)
                return

            if parsed.path == "/api/channel":
                vlist = list_generated_videos(out_dir)
                approved_n = sum(1 for x in vlist if (x.get("visual_audit") or {}).get("approved") or (x.get("validation") or {}).get("valid"))
                queued_n = sum(1 for x in vlist if x.get("queued_for_auto_publish"))
                rejected_n = sum(1 for x in vlist if (x.get("visual_audit") or {}).get("decision") == "REJECT")
                evo_rows = []
                try:
                    evo_rows = EvolutionStore(out_dir / "shorts_evolution.db").list_background_evolution()
                except Exception:
                    evo_rows = []
                self._send_json(200, {
                    "channel": get_youtube_channel_summary(),
                    "tts_engine": active_tts_engine_label(),
                    "local_videos": len(vlist),
                    "video_stats": {"total": len(vlist), "approved": approved_n, "queued": queued_n, "rejected": rejected_n},
                    "local_llm": _probe_local_llm(),
                    "keys": {
                        "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
                        "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
                        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
                    },
                    "gameplay_count": len(list_gameplay_clips(out_dir)),
                    "background_evolution": evo_rows,
                })
                return

            if parsed.path == "/api/scheduler":
                self._send_json(200, _load_scheduler_cfg(out_dir))
                return

            if parsed.path == "/api/system":
                self._send_json(200, build_system_diagnostics(out_dir))
                return

            if parsed.path == "/v1/models":
                caps = detect_android_llm_capabilities()
                self._send_json(200, {
                    "object": "list",
                    "data": [{
                        "id": caps["active_model"],
                        "object": "model",
                        "owned_by": "autoshorts-android",
                        "arch": caps["arch"],
                        "isa_features": caps["isa_features"],
                    }],
                })
                return

            if parsed.path == "/api/status":
                st = dict(_JOB_STATE)
                if st.get("running") and st.get("started_at"):
                    st["elapsed_sec"] = round(max(0.0, time.time() - float(st["started_at"])), 1)
                self._send_json(200, st)
                return

            if parsed.path == "/api/videos":
                qs = urllib.parse.parse_qs(parsed.query)
                status_flt = (qs.get("status") or ["all"])[0].strip().lower()
                q_flt = (qs.get("q") or [""])[0].strip().lower()
                try:
                    offset = max(0, int((qs.get("offset") or ["0"])[0]))
                    limit = max(1, min(100, int((qs.get("limit") or ["100"])[0])))
                except ValueError:
                    offset, limit = 0, 100
                all_vids = list_generated_videos(out_dir)
                filtered_vids = []
                for v in all_vids:
                    if q_flt and q_flt not in f"{v.get('title', '')} {v.get('caption', '')} {v.get('filename', '')}".lower():
                        continue
                    vis_ok = bool((v.get("visual_audit") or {}).get("approved") if v.get("visual_audit") else (v.get("validation") or {}).get("valid"))
                    is_pub = bool((v.get("youtube") or {}).get("video_id") or (v.get("youtube") or {}).get("url"))
                    if status_flt == "approved" and not vis_ok:
                        continue
                    if status_flt == "queued" and not v.get("queued_for_auto_publish"):
                        continue
                    if status_flt == "published" and not is_pub:
                        continue
                    if status_flt == "rejected" and vis_ok:
                        continue
                    filtered_vids.append(v)
                self._send_json(200, {
                    "videos": filtered_vids[offset:offset + limit],
                    "total": len(filtered_vids),
                    "limit": limit,
                    "offset": offset,
                })
                return

            if parsed.path == "/api/gameplay":
                clips = [p.name for p in list_gameplay_clips(out_dir)]
                self._send_json(200, {"count": len(clips), "clips": clips})
                return

            if parsed.path == "/api/horizon":
                qs = urllib.parse.parse_qs(parsed.query)
                topic = (qs.get("topic") or ["todos"])[0]
                try:
                    payload = fetch_horizon_trends(horizon=topic, limit=30, include_live_youtube=True)
                except Exception as exc:
                    payload = {"horizon": topic, "items": [], "error": str(exc)}
                self._send_json(200, payload)
                return

            if parsed.path == "/api/tunnel":
                tok = _TUNNEL_STATE.get("token") or ""
                url = _TUNNEL_STATE.get("url") or ""
                self._send_json(200, {"url": f"{url}/?token={tok}" if url and tok else ""})
                return

            if parsed.path == "/api/anime/trending":
                qs = urllib.parse.parse_qs(parsed.query)
                cat = (qs.get("category") or ["all"])[0]
                try:
                    animes = get_releasing_anime_radar(limit=24, category=cat)
                except Exception:
                    animes = []
                self._send_json(200, {"anime": animes, "category": cat})
                return

            if parsed.path == "/api/synapse/status":
                self._send_json(200, get_synapse_overview(out_dir))
                return

            if parsed.path == "/api/synapse/trace":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0]
                self._send_json(200, rea_trace_system(q))
                return

            if parsed.path == "/api/world-news":
                try:
                    headlines = fetch_world_news_headlines(topic="world", limit=12)
                    for h in headlines:
                        if str(h.get("lang") or "") != "pt":
                            h["title"] = _ptbr_headline(str(h.get("title") or ""), str(h.get("lang") or "en"))
                            h["summary"] = _ptbr_headline(str(h.get("summary") or "")[:180], str(h.get("lang") or "en"))
                            h["lang"] = "pt"
                except Exception:
                    headlines = []
                self._send_json(200, {"headlines": headlines})
                return

            if parsed.path == "/api/team/personas":
                self._send_json(200, {"personas": list_channel_personas()})
                return

            if parsed.path == "/api/team/planner":
                self._send_json(200, generate_channel_planner(days=7, include_live_anime=True))
                return

            if parsed.path.startswith("/media-preview/"):
                fname = urllib.parse.unquote(parsed.path[len("/media-preview/"):])
                preview_dir = out_dir / "_preview"
                safe_target = _safe_child_path(preview_dir, fname)
                if not safe_target or not safe_target.is_file():
                    self.send_error(404, "Preview nao encontrado")
                    return
                ctype, _ = mimetypes.guess_type(str(safe_target))
                data = safe_target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype or "audio/mpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self._safe_write(data)
                return

            if parsed.path.startswith("/media/"):
                fname = urllib.parse.unquote(parsed.path[len("/media/"):])
                safe_target = _safe_child_path(out_dir, fname)
                if not safe_target or not safe_target.is_file():
                    self.send_error(404, "Arquivo nao encontrado")
                    return
                ctype, _ = mimetypes.guess_type(str(safe_target))
                data = safe_target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self._safe_write(data)
                return

            self.send_error(404, "Not found")

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                self._send_json(400, {"message": "Content-Length invalido"})
                return
            if length < 0 or length > _MAX_POST_BYTES:
                self._send_json(413, {"message": "Payload excede limite de 1 MB"})
                return
            try:
                raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                body = json.loads(raw_body or "{}")
                if not isinstance(body, dict):
                    raise ValueError("JSON raiz deve ser um objeto")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                self._send_json(400, {"message": "JSON invalido na requisicao"})
                return
            parsed = urllib.parse.urlparse(self.path)
            if self._check_tunnel_auth(parsed) == "DENY":
                self._send_json(403, {"message": "Acesso externo exige token valido do tunel."})
                return

            if parsed.path == "/api/tunnel":
                self._send_json(200, _start_cloudflare_tunnel(8787))
                return

            if parsed.path == "/api/world-news":
                def news_worker():
                    _set_job_progress(2, 5, "2/5 Traduzindo jornais mundiais e gerando voz Kokoro...", 38)
                    res = produce_world_news_short(
                        out_dir=out_dir,
                        topic=str(body.get("topic") or "world"),
                        bg_video=str(body.get("bg_video") or "auto"),
                        auto_publish=bool(body.get("auto_publish", False)),
                        use_llm=is_llm_configured(),
                    )
                    _set_job_progress(5, 5, "5/5 Auditoria & Fila concluidas!", 100)
                    ds = str(res.get("delivery_status") or "")
                    msg = (
                        "Short de noticias mundiais validado em output/ (YouTube atingiu limite diario; salvo na fila!)."
                        if "queued_quota_limit" in ds
                        else "Short de noticias mundiais pronto e validado!"
                    )
                    _JOB_STATE.update({"last_status": msg, "last_result": res})

                pos = _enqueue_job("Traduzindo jornais mundiais e gerando video em PT-BR...", news_worker)
                self._send_json(202, {"message": f"Noticia mundial adicionada (fila: {pos})!", "queued": pos})
                return

            if parsed.path == "/api/team/brief":
                brief = build_persona_script_brief(
                    topic=str(body.get("topic") or "Tendencia de hoje"),
                    niche=str(body.get("niche") or "podcast"),
                    platform=str(body.get("platform") or "youtube_shorts"),
                )
                self._send_json(200, brief)
                return

            if parsed.path == "/api/voice-preview":
                try:
                    info = preview_voice(
                        script_text=body.get("script") or "Teste de voz em portugues brasileiro.",
                        out_dir=out_dir,
                        style_key=body.get("style", DEFAULT_STYLE_KEY),
                        humanize=bool(body.get("humanize", True)),
                    )
                    self._send_json(200, info)
                except Exception as exc:
                    self._send_json(500, {"message": str(exc)})
                return

            if parsed.path == "/api/validate":
                target = _safe_child_path(out_dir, str(body.get("filename") or ""))
                if not target or not target.is_file():
                    self._send_error(404, "VIDEO_NOT_FOUND", "Arquivo MP4 nao encontrado")
                    return
                ass_cand = next(
                    (c for c in (out_dir / f"_narrate_{target.stem}" / f"{target.stem}.ass", target.with_suffix(".ass"), target.with_suffix(".srt")) if c.is_file()),
                    None,
                )
                pack = optimize_existing_publish_pack(target, ass_path=ass_cand)
                self._send_json(200, {**(pack.get("validation") or {}), "opus_scorecard": pack.get("opus_scorecard"), "visual_audit": pack.get("visual_audit")})
                return

            if parsed.path == "/api/auto-validate-all":
                try_pub = bool(body.get("auto_publish", True))
                quota_hit = False
                approved = rejected = published = queued = duplicates_skipped = 0
                seen_titles: Dict[str, str] = {}
                results: List[Dict] = []
                if out_dir.exists():
                    for mp4 in sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
                        if mp4.stat().st_size < 50000:
                            continue
                        ass_cand = next(
                            (c for c in (out_dir / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass", mp4.with_suffix(".ass"), mp4.with_suffix(".srt")) if c.is_file()),
                            None,
                        )
                        pack = optimize_existing_publish_pack(mp4, ass_path=ass_cand)
                        audit = pack.get("visual_audit") or audit_short_end_to_end(mp4, pack=pack, ass_path=ass_cand, vision_check=True)
                        ok = bool(audit.get("approved"))
                        norm_title = re.sub(r"\s+", " ", str(pack.get("title") or "").strip().lower())
                        already_yt = bool((pack.get("youtube") or {}).get("video_id"))
                        is_dup = bool(norm_title and norm_title in seen_titles and not already_yt)
                        if norm_title and norm_title not in seen_titles:
                            seen_titles[norm_title] = mp4.name
                        if is_dup and ok:
                            duplicates_skipped += 1
                            pack["queued_for_auto_publish"] = False
                            pack["duplicate_of"] = seen_titles[norm_title]
                            pack["delivery_status"] = f"duplicate_of:{seen_titles[norm_title]}"
                            mp4.with_suffix(".publish.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
                            status = f"duplicate:{seen_titles[norm_title]}"
                        else:
                            status = "published" if already_yt else ("approved_queued" if ok else "rejected")
                            if ok:
                                approved += 1
                                if not already_yt and try_pub and not quota_hit:
                                    try:
                                        yt_res = publish_pack_to_youtube(mp4)
                                        published += 1
                                        status = f"published:{yt_res.get('video_id')}"
                                    except Exception as exc:
                                        if "uploadLimitExceeded" in str(exc):
                                            quota_hit = True
                                            queued += 1
                                            status = "queued_quota_limit"
                                        else:
                                            queued += 1
                                            status = "approved_queued"
                                elif not already_yt:
                                    queued += 1
                            else:
                                rejected += 1
                        results.append({
                            "filename": mp4.name,
                            "approved": ok,
                            "duplicate_of": pack.get("duplicate_of"),
                            "decision": audit.get("decision"),
                            "score": audit.get("quality_score"),
                            "opus_score": (pack.get("opus_scorecard") or {}).get("opus_score"),
                            "status": status,
                            "verdict": (audit.get("visual") or {}).get("vision_verdict", ""),
                            "reject_reasons": audit.get("reject_reasons", []),
                        })
                self._send_json(200, {
                    "approved": approved, "rejected": rejected, "published": published,
                    "queued": queued, "duplicates_skipped": duplicates_skipped, "results": results,
                })
                return

            if parsed.path == "/api/synapse/innertube":
                t0 = time.monotonic()
                res = inspect_youtube_innertube(str(body.get("url") or ""))
                record_synapse_stage(out_dir, "innertube_inspect", (time.monotonic() - t0) * 1000.0, ok=bool(res.get("ok")))
                self._send_json(200 if res.get("ok") else 400, res)
                return

            if parsed.path == "/api/synapse/pacing":
                self._send_json(200, analyze_kinetic_pacing(str(body.get("text") or ""), float(body.get("duration_sec") or 38.0)))
                return

            if parsed.path == "/api/synapse/scorecard":
                self._send_json(200, score_short_opus_runbook(body, duration=float(body.get("duration") or 0.0)))
                return

            if parsed.path == "/api/publish-instagram":
                target = _safe_child_path(out_dir, str(body.get("filename") or ""))
                if not target or not target.is_file():
                    self._send_json(404, {"message": "Arquivo MP4 nao encontrado"})
                    return
                try:
                    self._send_json(200, publish_pack_to_instagram_reels(target))
                except Exception as exc:
                    self._send_json(500, {"message": str(exc)})
                return

            if parsed.path == "/api/optimize":
                count = 0
                if out_dir.exists():
                    for mp4 in sorted(out_dir.glob("*.mp4")):
                        if mp4.stat().st_size < 50000:
                            continue
                        ass_cand = next(
                            (c for c in (out_dir / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass", mp4.with_suffix(".ass"), mp4.with_suffix(".srt")) if c.is_file()),
                            None,
                        )
                        try:
                            optimize_existing_publish_pack(mp4, ass_path=ass_cand)
                            count += 1
                        except Exception:
                            continue
                self._send_json(200, {"optimized_count": count})
                return

            if parsed.path == "/api/ai/benchmark":
                self._send_json(200, benchmark_local_llm())
                return

            if parsed.path == "/api/ai/chat":
                prompt = str(body.get("prompt") or body.get("message") or "").strip()
                if not prompt:
                    self._send_error(400, "MISSING_PROMPT", "Informe um texto para o assistente offline.")
                    return
                self._send_json(200, answer_studio_question_offline(prompt, out_dir))
                return

            if parsed.path == "/v1/chat/completions":
                msgs = body.get("messages") or []
                user_msg = next((str(m.get("content") or "") for m in reversed(msgs) if isinstance(m, dict) and m.get("role") == "user"), "")
                res = answer_studio_question_offline(user_msg, out_dir)
                self._send_json(200, {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "model": res.get("backend", "bm25-offline"),
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": res.get("answer", "")}, "finish_reason": "stop"}],
                    "sources": res.get("sources", []),
                })
                return

            if parsed.path == "/api/publish":
                target = _safe_child_path(out_dir, str(body.get("filename") or ""))
                if not target or not target.is_file():
                    self._send_json(404, {"message": "Arquivo MP4 nao encontrado"})
                    return
                try:
                    res = publish_pack_to_youtube(target, playlist_name=body.get("playlist"))
                    self._send_json(200, res)
                except Exception as exc:
                    msg = str(exc)
                    if "uploadLimitExceeded" in msg:
                        pack_file = target.with_suffix(".publish.json")
                        if pack_file.is_file():
                            try:
                                saved = json.loads(pack_file.read_text(encoding="utf-8"))
                                saved["queued_for_auto_publish"] = True
                                saved["delivery_status"] = "queued_quota_limit"
                                pack_file.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
                            except (OSError, json.JSONDecodeError):
                                pass
                        self._send_json(202, {
                            "queued": True,
                            "reason": "uploadLimitExceeded",
                            "message": "Limite diario de uploads do YouTube atingido hoje. Video mantido na fila para postar sozinho assim que a cota liberar!",
                        })
                        return
                    self._send_json(400, {"message": msg})
                return

            if parsed.path == "/api/trim":
                target = _safe_child_path(out_dir, str(body.get("filename") or ""))
                if not target or not target.is_file():
                    self._send_json(404, {"message": "Arquivo MP4 nao encontrado em output/"})
                    return
                start = max(0.0, float(body.get("start", 0.0)))
                end = max(start + 2.0, float(body.get("end", start + 30.0)))
                out_trim = out_dir / f"{target.stem}_cut.mp4"
                cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(target)]
                if bool(body.get("normalize", True)):
                    cmd.extend(["-c:v", "copy", "-af", LOUDNORM_FILTER, "-c:a", "aac", "-b:a", "192k", *METADATA_SCRUB, str(out_trim)])
                else:
                    cmd.extend(["-c", "copy", *METADATA_SCRUB, str(out_trim)])
                try:
                    subprocess.run(cmd, check=True)
                    val = validate_generated_short(out_trim)
                    self._send_json(200, {"output": out_trim.name, "validation": val})
                except Exception as exc:
                    self._send_json(500, {"message": str(exc)})
                return

            if parsed.path == "/api/scheduler":
                cfg = _load_scheduler_cfg(out_dir)
                if "enabled" in body:
                    cfg["enabled"] = bool(body["enabled"])
                if "interval_hours" in body:
                    cfg["interval_hours"] = max(1, int(body["interval_hours"]))
                if body.get("niche"):
                    cfg["niche"] = str(body["niche"])
                if "auto_publish" in body:
                    cfg["auto_publish"] = bool(body["auto_publish"])
                _save_scheduler_cfg(out_dir, cfg)
                if body.get("run_now"):
                    pos = _enqueue_job("Ciclo automatico multi-nicho em execucao...", lambda: _run_autonomous_cycle_core(out_dir, cfg))
                    self._send_json(202, {"message": f"Ciclo automatico agendado (fila: {pos})!", "scheduler": cfg})
                    return
                self._send_json(200, cfg)
                return

            if parsed.path == "/api/delete":
                target = _safe_child_path(out_dir, str(body.get("filename") or ""))
                if not target or not target.is_file():
                    self._send_json(404, {"message": "Arquivo nao encontrado"})
                    return
                fname = target.name
                for sidecar in (
                    target,
                    target.with_suffix(".publish.json"),
                    target.with_name(f"{target.stem}_thumb_16x9.jpg"),
                    target.with_name(f"{target.stem}_cover_9x16.jpg"),
                ):
                    if sidecar.is_file():
                        sidecar.unlink(missing_ok=True)
                self._send_json(200, {"deleted": fname})
                return

            if parsed.path == "/api/run":
                src_check = str(body.get("source") or "").strip()
                if src_check and not _is_safe_public_http_url(src_check):
                    self._send_json(400, {"message": "URL de origem invalida ou bloqueada por seguranca (use https://)."})
                    return

                def worker():
                    src = body.get("source", "").strip()
                    auto_pub = bool(body.get("auto_publish", True))
                    _set_job_progress(1, 5, "1/5 Baixando fonte & heatmaps InnerTube...", 22)
                    if src:
                        _set_job_progress(3, 5, "3/5 Extraindo trechos, legenda dinamica e FFmpeg...", 55)
                        res = run_pipeline(
                            source=src,
                            out_dir=out_dir,
                            platform=body.get("platform", "youtube_shorts"),
                            niche=body.get("niche", "podcast"),
                            num_clips=int(body.get("clips", 1)),
                            layout=body.get("layout", "blur_bg"),
                            use_llm=is_llm_configured(),
                            auto_layout=True,
                            playlist_name=body.get("playlist") or None,
                            auto_publish=auto_pub,
                        )
                    else:
                        _set_job_progress(3, 5, "3/5 Descobrindo video viral + Renderizando cortes...", 55)
                        res = run_autopilot(
                            out_dir=out_dir,
                            platform=body.get("platform", "youtube_shorts"),
                            niche=body.get("niche", "podcast"),
                            query=body.get("query") or None,
                            num_clips=int(body.get("clips", 1)),
                            layout=body.get("layout", "blur_bg"),
                            use_llm=is_llm_configured(),
                            auto_layout=True,
                            playlist_name=body.get("playlist") or None,
                            auto_publish=auto_pub,
                        )
                    _set_job_progress(5, 5, "5/5 Concluido e validado na fila!", 100)
                    _JOB_STATE.update({"last_status": "Concluido e validado!", "last_result": res})

                pos = _enqueue_job("Processando, validando e publicando cortes...", worker)
                self._send_json(202, {"message": f"Motor iniciado na fila ({pos})!"})
                return

            if parsed.path == "/api/gameplay/sync":
                niche = str(body.get("niche") or "geral").strip().lower()
                topic = str(body.get("topic") or "").strip()
                style = str(body.get("style") or "").strip().lower()
                def gp_worker():
                    dl_style, dl_q = (style, None) if style else discover_dynamic_visual_queries(niche=niche, topic=topic)
                    p = fetch_gameplay_clip(out_dir, style=dl_style, custom_queries=dl_q)
                    msg = f"Novo fundo evolutivo salvo ({dl_style}): {p.name}" if p else "Nenhum novo fundo encontrado agora."
                    _JOB_STATE.update({"last_status": msg})
                pos = _enqueue_job("Descobrindo e baixando novo fundo adaptativo sem copyright...", gp_worker)
                self._send_json(202, {"message": f"Download adaptativo de fundo iniciado na fila ({pos})!"})
                return

            if parsed.path == "/api/narrate":
                def voice_worker():
                    _set_job_progress(1, 5, "1/5 Escrevendo roteiro & gancho IA...", 18)
                    idx = 1
                    while (out_dir / f"narrated_{idx:02d}.mp4").exists():
                        idx += 1
                    out_mp4 = out_dir / f"narrated_{idx:02d}.mp4"
                    h_item = body.get("horizon_item")
                    if isinstance(h_item, dict):
                        spoken_script = build_horizon_spoken_script(h_item, use_llm=is_llm_configured())
                    else:
                        spoken_script = str(body.get("script") or "").strip()
                    _set_job_progress(3, 5, "3/5 Voz Kokoro PT-BR + Multi-Cena B-Roll + Sidechain...", 60)
                    res = build_narrated_short(
                        bg_video=body.get("bg_video", "gameplay"),
                        script_text=spoken_script,
                        out_mp4=out_mp4,
                        hook_title=str(body.get("hook_title") or body.get("hook") or ""),
                        style_key=body.get("style", DEFAULT_STYLE_KEY),
                        layout=str(body.get("layout") or "center_crop"),
                        humanize=bool(body.get("humanize", True)),
                        niche=str(body.get("niche") or "podcast"),
                    )
                    _set_job_progress(4, 5, "4/5 Validando midia, visao 5-frames & Opus Scorecard...", 85)
                    ass_cand = out_dir / f"_narrate_{out_mp4.stem}" / f"{out_mp4.stem}.ass"
                    optimize_existing_publish_pack(out_mp4, ass_path=ass_cand if ass_cand.is_file() else None)
                    if bool(body.get("auto_publish", False)) and res.get("validation", {}).get("valid"):
                        try:
                            pub = publish_pack_to_youtube(out_mp4, playlist_name=body.get("playlist"))
                            res["youtube"] = pub
                        except Exception as exc:
                            res["publish_error"] = str(exc)
                    _set_job_progress(5, 5, f"5/5 Short validado: {out_mp4.name}", 100)
                    _JOB_STATE.update({"last_status": f"Short validado: {out_mp4.name}", "last_result": res})

                pos = _enqueue_job("Gerando video, legendas e validando midia...", voice_worker)
                self._send_json(202, {"message": f"Geracao adicionada na fila ({pos})!"})
                return

            self.send_error(404, "Not found")

        def log_message(self, format, *args):
            return

    return AppHandler


def _prewarm_radar_cache() -> None:
    """Warm horizon & anime caches on boot so first UI load is instant (<20ms)."""
    try:
        fetch_horizon_trends(horizon="todos", limit=30, include_live_youtube=True)
    except Exception:
        pass


def serve_webapp(host: str = "0.0.0.0", port: int = 8787, out_dir: str | Path = "output") -> None:
    load_dotenv_file(Path(__file__).resolve().parents[2] / ".env")
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    _save_scheduler_cfg(out_path, _load_scheduler_cfg(out_path))
    threading.Thread(target=_autonomous_loop, args=(out_path,), daemon=True).start()
    threading.Thread(target=_prewarm_radar_cache, daemon=True).start()
    server = _StudioHTTPServer((host, port), make_handler(out_path))
    print(f"AutoShorts Studio rodando em http://{host}:{port} (abra http://127.0.0.1:{port} no celular)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start AutoShorts Light Studio web app")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--out", default="output")
    args = parser.parse_args()
    serve_webapp(host=args.host, port=args.port, out_dir=args.out)
