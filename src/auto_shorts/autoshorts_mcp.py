"""Adaptive Offline-First MCP Server & Multi-Mode Code Mode Engine for AutoShorts Studio.

Implements:
1. Full MCP JSON-RPC 2.0 (tools, resources, prompts) over stdio & Streamable HTTP (/mcp).
2. Progressive BM25/keyword tool discovery (mcp_discover_tools) to minimize token bloat.
3. AST-sandboxed Python Code Mode (mcp_execute_codemode) — 100% offline, zero Node.js dependency.
4. Declarative DAG Pipeline Code Mode (mcp_run_pipeline_dag) with $steps.<id>.<key> interpolation.
5. Faro Protocol dynamic tool reification (mcp_reify_tool) persisted to output/mcp_reified_tools.json.
6. Mahoraga Adaptive Telemetry (mcp_ecosystem_telemetry) with p50/p95 latency & offline routing hints.
"""

from __future__ import annotations

import ast
import contextlib
import datetime as _dt
import io
import json
import math
import os
import platform
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import load_dotenv_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv_file(PROJECT_ROOT / ".env")

_TELEMETRY_LOCK = threading.Lock()
_REIFY_LOCK = threading.Lock()

_FORBIDDEN_AST_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
})
_FORBIDDEN_AST_ATTRS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__mro__", "__globals__",
    "__code__", "__closure__", "__builtins__", "__import__", "popen",
})
_ALLOWED_IMPORTS = frozenset({"json", "math", "re", "time", "datetime"})


def _default_out_dir() -> Path:
    out = PROJECT_ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _telemetry_path(out_dir: Optional[Path] = None) -> Path:
    return (out_dir or _default_out_dir()) / "mcp_telemetry.json"


def _reified_path(out_dir: Optional[Path] = None) -> Path:
    return (out_dir or _default_out_dir()) / "mcp_reified_tools.json"


def _load_json_safe(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json_safe(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _record_telemetry(tool_name: str, ok: bool, duration_ms: float, error: str = "", out_dir: Optional[Path] = None) -> None:
    path = _telemetry_path(out_dir)
    with _TELEMETRY_LOCK:
        state = _load_json_safe(path, {"tools": {}, "updated_at": 0})
        tools = state.setdefault("tools", {})
        entry = tools.setdefault(tool_name, {
            "calls": 0, "errors": 0, "latencies_ms": [], "last_error": "", "last_ts": 0.0,
        })
        entry["calls"] += 1
        if not ok:
            entry["errors"] += 1
            entry["last_error"] = error[:240]
        lats = entry.setdefault("latencies_ms", [])
        lats.append(round(duration_ms, 2))
        if len(lats) > 50:
            del lats[:-50]
        entry["last_ts"] = round(time.time(), 3)
        state["updated_at"] = round(time.time(), 3)
        try:
            _save_json_safe(path, state)
        except OSError:
            pass


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(math.ceil((pct / 100.0) * len(s))) - 1))
    return round(s[idx], 2)


# ---------------------------------------------------------------------------
# Internal Offline-First Tool Implementations
# ---------------------------------------------------------------------------

def _tool_system_health(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .smart_autopublish import is_wifi_connected
    od = out_dir or _default_out_dir()
    usage = shutil.disk_usage(od)
    on_termux = os.path.isdir("/data/data/com.termux")
    c11_audit = PROJECT_ROOT / "native-c" / "media_audit"
    tunnel_file = od / "tunnel_url.txt"
    tunnel_url = tunnel_file.read_text(encoding="utf-8").strip() if tunnel_file.is_file() else ""
    return {
        "ok": True,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "on_termux": on_termux,
        "wifi_only_env": os.getenv("WIFI_ONLY", "").strip(),
        "wifi_connected": is_wifi_connected(),
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "tools_bin": {
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")),
            "yt_dlp": bool(shutil.which("yt-dlp")),
            "media_audit_c11": c11_audit.is_file(),
        },
        "tunnel_url": tunnel_url,
        "remote_url": os.getenv("AUTOSHORT_REMOTE_URL", "").strip(),
        "routing_mode": "offline_local" if not os.getenv("AUTOSHORT_REMOTE_URL", "").strip() else "hybrid_remote",
    }


def _tool_vault_list(status: str = "all", limit: int = 30, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    od = out_dir or _default_out_dir()
    mp4s = sorted(od.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    items: List[Dict[str, Any]] = []
    for p in mp4s:
        meta_path = p.with_suffix(".json")
        meta = _load_json_safe(meta_path, {})
        ig_pub = bool(meta.get("instagram_media_id") or meta.get("ig_published_at"))
        yt_pub = bool(meta.get("youtube_video_id"))
        tt_pub = bool(meta.get("tiktok_publish_id"))
        if status == "ig_pending" and ig_pub:
            continue
        if status == "ig_published" and not ig_pub:
            continue
        if status == "yt_published" and not yt_pub:
            continue
        items.append({
            "filename": p.name,
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "title": meta.get("title") or p.stem,
            "niche": meta.get("niche") or "auto",
            "opus_score": meta.get("opus_score"),
            "instagram_published": ig_pub,
            "youtube_published": yt_pub,
            "tiktok_published": tt_pub,
        })
        if len(items) >= max(1, min(int(limit), 200)):
            break
    return {"total_mp4": len(mp4s), "returned": len(items), "items": items}


def _tool_vault_audit(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .publisher import audit_published_vault
    return audit_published_vault(out_dir or _default_out_dir())


def _tool_vault_validate(filename: str, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .validator import validate_generated_short
    od = out_dir or _default_out_dir()
    target = od / Path(filename).name
    if not target.is_file():
        return {"ok": False, "error": f"Arquivo nao encontrado: {target.name}"}
    return validate_generated_short(target)


def _tool_autopublish_plan(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .smart_autopublish import get_autopublish_plan
    from .publisher import _is_instagram_configured
    od = out_dir or _default_out_dir()
    yt_ready = bool(os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and os.getenv("YT_REFRESH_TOKEN"))
    tt_ready = bool(os.getenv("TIKTOK_ACCESS_TOKEN"))
    ig_ready = _is_instagram_configured()
    return get_autopublish_plan(od, youtube_ready=yt_ready, tiktok_ready=tt_ready, instagram_ready=ig_ready)


def _tool_autopublish_run(
    youtube: bool = False,
    tiktok: bool = False,
    instagram: bool = True,
    force: bool = False,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    from .smart_autopublish import run_smart_publish_cycle
    from .publisher import _is_instagram_configured
    od = out_dir or _default_out_dir()
    yt_ready = youtube and bool(os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and os.getenv("YT_REFRESH_TOKEN"))
    tt_ready = tiktok and bool(os.getenv("TIKTOK_ACCESS_TOKEN"))
    ig_ready = instagram and _is_instagram_configured()
    return run_smart_publish_cycle(od, youtube_ready=yt_ready, tiktok_ready=tt_ready, instagram_ready=ig_ready, force=force)


def _bm25_rank_docs(query: str, docs: List[Dict[str, str]], top_k: int = 10) -> List[Dict[str, Any]]:
    q_tokens = re.findall(r"[a-z0-9_]+", query.lower())
    if not q_tokens or not docs:
        return [{"id": d["id"], "score": 0.0} for d in docs[:top_k]]
    tokenized = [re.findall(r"[a-z0-9_]+", d.get("text", "").lower()) for d in docs]
    avgdl = sum(len(t) for t in tokenized) / max(1, len(tokenized))
    df: Dict[str, int] = {}
    for qt in set(q_tokens):
        df[qt] = sum(1 for toks in tokenized if qt in toks)
    k1, b = 1.5, 0.75
    n_docs = len(docs)
    scored: List[Tuple[float, str]] = []
    for doc, toks in zip(docs, tokenized):
        dl = len(toks)
        tf: Dict[str, int] = {}
        for tok in toks:
            tf[tok] = tf.get(tok, 0) + 1
        score = 0.0
        for qt in q_tokens:
            f = tf.get(qt, 0)
            if f <= 0:
                continue
            idf = math.log(1.0 + (n_docs - df[qt] + 0.5) / (df[qt] + 0.5))
            denom = f + k1 * (1.0 - b + b * (dl / max(1.0, avgdl)))
            score += idf * ((f * (k1 + 1.0)) / max(1e-9, denom))
        scored.append((round(score, 4), doc["id"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": doc_id, "score": sc} for sc, doc_id in scored[:top_k]]


def _tool_llm_hardware() -> Dict[str, Any]:
    from .offline_llm import detect_android_llm_capabilities
    return detect_android_llm_capabilities()


def _tool_bm25_search(query: str, limit: int = 5, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .offline_llm import bm25_search_shorts
    od = out_dir or _default_out_dir()
    hits = bm25_search_shorts(query, od, top_k=max(1, min(int(limit), 20)))
    return {"query": query, "hits": hits}


def _tool_hooks_sanitize(title: str, candidates: Optional[List[str]] = None, niche: str = "entretenimento_animes") -> Dict[str, Any]:
    from .highlights import _polish_hook_phrase, _pick_best_hook
    polished = _polish_hook_phrase(title)
    best = _pick_best_hook(title, candidates or [], niche=niche) if candidates else polished
    return {"input_title": title, "polished": polished, "best_hook": best, "niche": niche}


def _tool_mahoraga_state(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    from .mahoraga import MahoragaEngine
    od = out_dir or _default_out_dir()
    return MahoragaEngine(db_path=od / "shorts_evolution.db").get_status_summary()


def _build_internal_registry(out_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    from .youtube_studio_mcp import TOOL_REGISTRY as YT_TOOLS
    od = out_dir or _default_out_dir()

    reg: Dict[str, Dict[str, Any]] = {
        "system.health": {
            "category": "system",
            "offline": True,
            "description": "Check Termux/Windows OS, Wi-Fi-only guard, disk space, FFmpeg/C11 binaries, and tunnel status.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: _tool_system_health(od),
        },
        "system.wifi": {
            "category": "system",
            "offline": True,
            "description": "Verify whether Wi-Fi (wlan0/wlan1) is active under WIFI_ONLY=1.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: {"wifi_connected": _tool_system_health(od)["wifi_connected"], "wifi_only_env": os.getenv("WIFI_ONLY", "")},
        },
        "vault.list": {
            "category": "vault",
            "offline": True,
            "description": "List MP4 packs in output/ filtered by status (all, ig_pending, ig_published, yt_published).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "default": "all"},
                    "limit": {"type": "integer", "default": 30},
                },
            },
            "handler": lambda a: _tool_vault_list(str(a.get("status", "all")), int(a.get("limit", 30)), od),
        },
        "vault.audit": {
            "category": "vault",
            "offline": True,
            "description": "Audit published vault for duplicate thumbnail SHA-256 hashes and missing assets.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: _tool_vault_audit(od),
        },
        "vault.validate": {
            "category": "vault",
            "offline": True,
            "description": "Validate MP4 aspect ratio, audio LUFS, and subtitles for a file in output/.",
            "inputSchema": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]},
            "handler": lambda a: _tool_vault_validate(str(a["filename"]), od),
        },
        "autopublish.plan": {
            "category": "publish",
            "offline": True,
            "description": "Inspect autopublish candidate ranking, daily caps, cooldowns, and niche diversity.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: _tool_autopublish_plan(od),
        },
        "autopublish.run": {
            "category": "publish",
            "offline": False,
            "description": "Run serialized smart autopublish cycle (enforces WIFI_ONLY=1 and _AUTOPUBLISH_LOCK).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "youtube": {"type": "boolean", "default": False},
                    "tiktok": {"type": "boolean", "default": False},
                    "instagram": {"type": "boolean", "default": True},
                    "force": {"type": "boolean", "default": False},
                },
            },
            "handler": lambda a: _tool_autopublish_run(
                youtube=bool(a.get("youtube", False)),
                tiktok=bool(a.get("tiktok", False)),
                instagram=bool(a.get("instagram", True)),
                force=bool(a.get("force", False)),
                out_dir=od,
            ),
        },
        "llm.hardware": {
            "category": "ai",
            "offline": True,
            "description": "Probe ARM64/x86 CPU ISA features and RAM-tiered offline GGUF model recommendations.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: _tool_llm_hardware(),
        },
        "llm.bm25_search": {
            "category": "ai",
            "offline": True,
            "description": "Pure-Python BM25 local RAG search across rendered video metadata and project docs/.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
                "required": ["query"],
            },
            "handler": lambda a: _tool_bm25_search(str(a["query"]), int(a.get("limit", 5)), od),
        },
        "hooks.sanitize": {
            "category": "ai",
            "offline": True,
            "description": "Sanitize cover hook title, rejecting incoherent spoken fragments and scoring niche relevance.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "niche": {"type": "string", "default": "entretenimento_animes"},
                },
                "required": ["title"],
            },
            "handler": lambda a: _tool_hooks_sanitize(str(a["title"]), a.get("candidates"), str(a.get("niche", "entretenimento_animes"))),
        },
        "mahoraga.state": {
            "category": "adaptive",
            "offline": True,
            "description": "Read Mahoraga 8-spoke Dharma Wheel adaptation state and immunity counters.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": lambda a: _tool_mahoraga_state(od),
        },
    }

    for yt_name, yt_spec in YT_TOOLS.items():
        reg[yt_name] = {
            "category": "youtube_studio",
            "offline": yt_name in ("yt_team_personas_planner",),
            "description": yt_spec["description"],
            "inputSchema": yt_spec["inputSchema"],
            "handler": yt_spec["handler"],
        }

    # Load Faro-reified persistent tools
    reified = _load_json_safe(_reified_path(od), {})
    if isinstance(reified, dict):
        for rname, rspec in reified.items():
            if isinstance(rspec, dict) and rspec.get("code"):
                code_src = str(rspec["code"])
                reg[rname] = {
                    "category": "reified",
                    "offline": True,
                    "description": str(rspec.get("description") or f"Reified tool {rname}"),
                    "inputSchema": rspec.get("inputSchema") or {"type": "object", "properties": {}},
                    "handler": (lambda args, _c=code_src: execute_codemode(_c, args=args, out_dir=od)),
                }

    return reg


# ---------------------------------------------------------------------------
# AST-Sandboxed Python Code Mode (100% Offline)
# ---------------------------------------------------------------------------

def _validate_codemode_ast(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    raise ValueError(f"Import not allowed in offline sandbox: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod not in _ALLOWED_IMPORTS:
                raise ValueError(f"ImportFrom not allowed in offline sandbox: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_AST_CALLS:
                raise ValueError(f"Call not allowed in offline sandbox: {node.func.id}()")
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_AST_ATTRS:
                raise ValueError(f"Attribute access not allowed in offline sandbox: .{node.attr}")


class _ToolNamespace:
    """Allows both tools.call('vault.audit') and studio.vault.audit() ergonomics."""

    def __init__(self, registry: Dict[str, Dict[str, Any]], out_dir: Path, calls_log: List[Dict[str, Any]]):
        self._registry = registry
        self._out_dir = out_dir
        self._calls_log = calls_log

    def list(self) -> List[str]:
        return sorted(self._registry.keys())

    def call(self, name: str, **kwargs: Any) -> Any:
        spec = self._registry.get(name)
        if not spec:
            raise KeyError(f"Unknown internal tool: {name}")
        t0 = time.perf_counter()
        ok = True
        err = ""
        try:
            res = spec["handler"](kwargs)
            return res
        except Exception as exc:
            ok = False
            err = str(exc)
            raise
        finally:
            dur = (time.perf_counter() - t0) * 1000.0
            _record_telemetry(name, ok, dur, err, self._out_dir)
            self._calls_log.append({"tool": name, "ok": ok, "duration_ms": round(dur, 2)})


class _DomainProxy:
    def __init__(self, ns: _ToolNamespace, prefix: str):
        self._ns = ns
        self._prefix = prefix

    def __getattr__(self, item: str) -> Callable[..., Any]:
        tool_name = f"{self._prefix}.{item}"
        return lambda **kwargs: self._ns.call(tool_name, **kwargs)


class _StudioProxy:
    def __init__(self, ns: _ToolNamespace):
        self._ns = ns

    def __getattr__(self, domain: str) -> _DomainProxy:
        return _DomainProxy(self._ns, domain)


def execute_codemode(
    code: str,
    args: Optional[Dict[str, Any]] = None,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute AST-validated Python orchestration code 100% offline with bound studio/tools."""
    od = out_dir or _default_out_dir()
    _validate_codemode_ast(code)
    registry = _build_internal_registry(od)
    calls_log: List[Dict[str, Any]] = []
    ns = _ToolNamespace(registry, od, calls_log)
    studio = _StudioProxy(ns)

    safe_builtins = {
        "len": len, "min": min, "max": max, "sum": sum, "sorted": sorted,
        "enumerate": enumerate, "range": range, "zip": zip, "any": any, "all": all,
        "abs": abs, "round": round, "int": int, "float": float, "str": str,
        "bool": bool, "list": list, "dict": dict, "set": set, "tuple": tuple,
        "isinstance": isinstance, "print": print, "Exception": Exception,
    }
    env: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        "tools": ns,
        "studio": studio,
        "args": dict(args or {}),
        "json": json,
        "math": math,
        "re": re,
        "time": time,
        "datetime": _dt,
        "result": None,
    }
    buf = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<codemode>", "exec"), env, env)  # noqa: S102 — AST validated above
    dur = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "duration_ms": dur,
        "calls_made": calls_log,
        "stdout": buf.getvalue()[:8000],
        "result": env.get("result"),
    }


# ---------------------------------------------------------------------------
# Declarative DAG Pipeline Code Mode
# ---------------------------------------------------------------------------

def _resolve_templates(value: Any, step_results: Dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$steps."):
        parts = value[len("$steps."):].split(".")
        cur: Any = step_results
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return value
        return cur
    if isinstance(value, dict):
        return {k: _resolve_templates(v, step_results) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_templates(v, step_results) for v in value]
    return value


def run_pipeline_dag(
    steps: List[Dict[str, Any]],
    stop_on_error: bool = True,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute a multi-step declarative tool DAG with $steps.<id>.<field> interpolation."""
    od = out_dir or _default_out_dir()
    registry = _build_internal_registry(od)
    ns = _ToolNamespace(registry, od, [])
    step_results: Dict[str, Any] = {}
    trace: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps):
        sid = str(step.get("id") or f"step_{idx+1}")
        tool = str(step.get("tool") or "")
        deps = [str(d) for d in (step.get("depends_on") or [])]
        missing = [d for d in deps if d not in step_results]
        if missing:
            err_msg = f"Unmet dependencies for {sid}: {missing}"
            trace.append({"id": sid, "tool": tool, "ok": False, "error": err_msg})
            if stop_on_error:
                return {"ok": False, "steps": step_results, "trace": trace, "error": err_msg}
            continue
        raw_args = step.get("args") or {}
        resolved_args = _resolve_templates(raw_args, step_results)
        try:
            out = ns.call(tool, **(resolved_args if isinstance(resolved_args, dict) else {}))
            step_results[sid] = out
            trace.append({"id": sid, "tool": tool, "ok": True})
        except Exception as exc:
            trace.append({"id": sid, "tool": tool, "ok": False, "error": str(exc)})
            if stop_on_error:
                return {"ok": False, "steps": step_results, "trace": trace, "error": str(exc)}
    return {"ok": True, "steps": step_results, "trace": trace}


# ---------------------------------------------------------------------------
# Progressive Discovery, Faro Reification & Mahoraga Telemetry
# ---------------------------------------------------------------------------

def discover_tools(query: str = "", category: str = "", limit: int = 10, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    od = out_dir or _default_out_dir()
    registry = _build_internal_registry(od)
    docs = []
    for name, spec in registry.items():
        if category and spec.get("category") != category:
            continue
        docs.append({
            "id": name,
            "title": name,
            "text": f"{name} {spec.get('category', '')} {spec.get('description', '')}",
        })
    if query.strip():
        hits = _bm25_rank_docs(query, docs, top_k=max(1, min(int(limit), 30)))
        names = [h["id"] for h in hits]
    else:
        names = [d["id"] for d in docs[:max(1, min(int(limit), 30))]]

    results = [
        {
            "name": n,
            "category": registry[n]["category"],
            "offline": bool(registry[n].get("offline")),
            "description": registry[n]["description"],
            "inputSchema": registry[n]["inputSchema"],
        }
        for n in names if n in registry
    ]
    return {"total_available": len(registry), "returned": len(results), "tools": results}


def reify_tool(
    name: str,
    description: str,
    code: str,
    input_schema: Optional[Dict[str, Any]] = None,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Faro Protocol: validate & persist a Python Code Mode snippet as a reusable MCP tool."""
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name.strip())
    if not clean_name:
        raise ValueError("Tool name cannot be empty")
    _validate_codemode_ast(code)
    od = out_dir or _default_out_dir()
    path = _reified_path(od)
    with _REIFY_LOCK:
        existing = _load_json_safe(path, {})
        if not isinstance(existing, dict):
            existing = {}
        existing[clean_name] = {
            "description": description.strip(),
            "code": code,
            "inputSchema": input_schema or {"type": "object", "properties": {}},
            "created_at": round(time.time(), 3),
        }
        _save_json_safe(path, existing)
    return {"ok": True, "reified_tool": clean_name, "total_reified": len(existing)}


def get_ecosystem_telemetry(out_dir: Optional[Path] = None) -> Dict[str, Any]:
    od = out_dir or _default_out_dir()
    raw = _load_json_safe(_telemetry_path(od), {"tools": {}, "updated_at": 0})
    summary: Dict[str, Any] = {}
    for tname, entry in (raw.get("tools") or {}).items():
        lats = entry.get("latencies_ms") or []
        calls = int(entry.get("calls") or 0)
        errors = int(entry.get("errors") or 0)
        summary[tname] = {
            "calls": calls,
            "errors": errors,
            "error_rate_pct": round((errors / calls) * 100.0, 2) if calls else 0.0,
            "p50_ms": _percentile(lats, 50),
            "p95_ms": _percentile(lats, 95),
            "last_error": entry.get("last_error") or "",
        }
    return {
        "ok": True,
        "system": _tool_system_health(od),
        "tools_telemetry": summary,
        "reified_tools": sorted((_load_json_safe(_reified_path(od), {}) or {}).keys()),
    }


# ---------------------------------------------------------------------------
# MCP Protocol Handler (Tools + Resources + Prompts + Code Mode)
# ---------------------------------------------------------------------------

def _exposed_mcp_tools(out_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    from .youtube_studio_mcp import TOOL_REGISTRY as YT_TOOLS
    tools: List[Dict[str, Any]] = [
        {
            "name": "mcp_discover_tools",
            "description": "Progressive BM25 discovery over all 20+ offline & Studio internal tools (system, vault, publish, ai, mahoraga, reified).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": ""},
                    "category": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
        {
            "name": "mcp_call_tool",
            "description": "Invoke any discovered internal or Faro-reified tool by name with JSON arguments.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "args": {"type": "object", "default": {}},
                },
                "required": ["tool"],
            },
        },
        {
            "name": "mcp_execute_codemode",
            "description": "Offline AST-sandboxed Python Code Mode. Chain multiple tools in one call via `studio.<domain>.<fn>(...)` or `tools.call(name, **kwargs)` and assign final output to `result`.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "args": {"type": "object", "default": {}},
                },
                "required": ["code"],
            },
        },
        {
            "name": "mcp_run_pipeline_dag",
            "description": "Declarative JSON DAG Code Mode. Execute ordered steps `[{id, tool, args, depends_on}]` with `$steps.<id>.<field>` interpolation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "steps": {"type": "array", "items": {"type": "object"}},
                    "stop_on_error": {"type": "boolean", "default": True},
                },
                "required": ["steps"],
            },
        },
        {
            "name": "mcp_reify_tool",
            "description": "Faro Protocol: persist a validated Python Code Mode snippet as a permanent reusable offline MCP tool.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "code": {"type": "string"},
                    "input_schema": {"type": "object", "default": {}},
                },
                "required": ["name", "description", "code"],
            },
        },
        {
            "name": "mcp_ecosystem_telemetry",
            "description": "Mahoraga Adaptive Telemetry: p50/p95 latencies, error rates, Wi-Fi/offline routing state, and reified tools.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    for name, spec in YT_TOOLS.items():
        tools.append({"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]})
    return tools


RESOURCES = [
    {"uri": "autoshorts://system/health", "name": "System & Wi-Fi Health", "mimeType": "application/json", "description": "OS, Wi-Fi-only guard, disk, FFmpeg/C11 binaries, and routing mode."},
    {"uri": "autoshorts://vault/audit", "name": "Published Vault Audit", "mimeType": "application/json", "description": "Duplicate thumbnail SHA-256 & asset integrity audit."},
    {"uri": "autoshorts://autopublish/plan", "name": "Autopublish Plan", "mimeType": "application/json", "description": "Candidate ranking, daily caps, and cooldowns across IG/TikTok/YT."},
    {"uri": "autoshorts://mahoraga/state", "name": "Mahoraga Dharma Wheel", "mimeType": "application/json", "description": "Adaptive wheel state and immunity counters."},
    {"uri": "autoshorts://tools/catalog", "name": "Internal Tools & Telemetry", "mimeType": "application/json", "description": "Full catalog of offline + studio + reified tools."},
]

PROMPTS = [
    {
        "name": "diagnose-and-heal",
        "description": "Run an offline-first Code Mode diagnostic across system health, Wi-Fi guard, vault audit, and autopublish plan.",
        "arguments": [],
    },
    {
        "name": "codemode-orchestration",
        "description": "Template for multi-tool Python Code Mode execution inside AutoShorts MCP.",
        "arguments": [{"name": "goal", "description": "Workflow goal", "required": True}],
    },
]


def handle_mcp_request(req: Dict[str, Any], out_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Process one JSON-RPC 2.0 MCP request (tools, resources, prompts, Code Mode)."""
    od = out_dir or _default_out_dir()
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    if method == "notifications/initialized" or req_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "autoshorts-adaptive-mcp", "version": "2.0.0"},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _exposed_mcp_tools(od)}}

    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        t0 = time.perf_counter()
        ok = True
        err = ""
        try:
            if name == "mcp_discover_tools":
                res = discover_tools(str(args.get("query", "")), str(args.get("category", "")), int(args.get("limit", 10)), od)
            elif name == "mcp_call_tool":
                reg = _build_internal_registry(od)
                target = str(args.get("tool") or "")
                if target not in reg:
                    raise KeyError(f"Unknown internal tool: {target}")
                res = reg[target]["handler"](args.get("args") or {})
            elif name == "mcp_execute_codemode":
                res = execute_codemode(str(args["code"]), args=args.get("args") or {}, out_dir=od)
            elif name == "mcp_run_pipeline_dag":
                res = run_pipeline_dag(list(args.get("steps") or []), stop_on_error=bool(args.get("stop_on_error", True)), out_dir=od)
            elif name == "mcp_reify_tool":
                res = reify_tool(str(args["name"]), str(args["description"]), str(args["code"]), args.get("input_schema"), od)
            elif name == "mcp_ecosystem_telemetry":
                res = get_ecosystem_telemetry(od)
            else:
                reg = _build_internal_registry(od)
                if name not in reg:
                    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
                res = reg[name]["handler"](args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]},
            }
        except Exception as exc:
            ok = False
            err = str(exc)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"isError": True, "content": [{"type": "text", "text": f"Error: {exc}"}]},
            }
        finally:
            _record_telemetry(name, ok, (time.perf_counter() - t0) * 1000.0, err, od)

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": RESOURCES}}

    if method == "resources/read":
        uri = str(params.get("uri") or "")
        mapping = {
            "autoshorts://system/health": lambda: _tool_system_health(od),
            "autoshorts://vault/audit": lambda: _tool_vault_audit(od),
            "autoshorts://autopublish/plan": lambda: _tool_autopublish_plan(od),
            "autoshorts://mahoraga/state": lambda: _tool_mahoraga_state(od),
            "autoshorts://tools/catalog": lambda: discover_tools(limit=30, out_dir=od),
        }
        fn = mapping.get(uri)
        if not fn:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Unknown resource URI: {uri}"}}
        data = fn()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, ensure_ascii=False, indent=2)}]},
        }

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": PROMPTS}}

    if method == "prompts/get":
        pname = str(params.get("name") or "")
        pargs = params.get("arguments") or {}
        if pname == "diagnose-and-heal":
            msg = (
                "Call `mcp_execute_codemode` with:\n"
                "```python\n"
                "health = studio.system.health()\n"
                "audit = studio.vault.audit()\n"
                "plan = studio.autopublish.plan()\n"
                "result = {'health': health, 'warnings': audit.get('warnings_count'), 'ig_pending': plan['channels']['instagram']['pending_count']}\n"
                "```"
            )
        elif pname == "codemode-orchestration":
            goal = str(pargs.get("goal") or "Inspect vault and rank candidates")
            msg = f"Use `mcp_discover_tools` first, then chain calls in one `mcp_execute_codemode` block to achieve: {goal}"
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Unknown prompt: {pname}"}}
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"messages": [{"role": "user", "content": {"type": "text", "text": msg}}]},
        }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not supported: {method}"}}


def serve_stdio() -> None:
    """Serve Adaptive AutoShorts MCP JSON-RPC 2.0 over stdin/stdout (100% offline-capable)."""
    import sys
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        resp = handle_mcp_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
