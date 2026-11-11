"""Offline Android Edge-LLM engine: ARM64 ISA probing, GGUF inventory, CoT stripping & BM25 RAG.

Synthesizes patterns from OfflineLLM (dotprod/fp16/i8mm/SVE diagnostics + <think> stripping),
Local-LLM-AI (RAM-tiered GGUF model recommendations + TTFT/tok-s telemetry),
local-llms-on-android (OpenAI-compatible /v1 LAN endpoints + BM25 retrieval),
and Project NOMAD (self-contained offline benchmark & local knowledge base).
"""

import hashlib
import json
import math
import os
import platform
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


_ISA_FLAGS = ("asimddp", "dotprod", "asimdhp", "fp16", "i8mm", "sve", "sme", "neon", "asimd")
_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_]+")
_THINK_RE = re.compile(r"<(?:think|\|?thought\|?)>.*?</(?:think|\|?thought\|?)>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_RE = re.compile(r"<(?:think|\|?thought\|?)>.*$", re.IGNORECASE | re.DOTALL)

# Model tiers matching Local-LLM-AI & OfflineLLM device RAM guidelines
GGUF_MODEL_TIERS = [
    {"id": "qwen3-0.6b-pocket", "label": "Qwen 3 0.6B Pocket Turbo", "min_ram_gb": 2.0, "size_mb": 390},
    {"id": "qwen2.5-1.5b-q4", "label": "Qwen 2.5 1.5B Instruct Q4_K_M", "min_ram_gb": 4.0, "size_mb": 1120},
    {"id": "smollm2-1.7b-q4", "label": "SmolLM2 1.7B Instruct", "min_ram_gb": 4.0, "size_mb": 1180},
    {"id": "gemma-4-e2b-it", "label": "Gemma 4 E2B Instruct (Vision/OCR)", "min_ram_gb": 6.0, "size_mb": 2590},
    {"id": "qwen3-4b-reasoning", "label": "Qwen 3 4B Hybrid Reasoning", "min_ram_gb": 8.0, "size_mb": 2660},
]


def strip_reasoning_tags(text: str) -> str:
    """Remove closed or truncated <think>/<thought> blocks so Shorts copy never leaks CoT traces."""
    raw = str(text or "")
    cleaned = _THINK_RE.sub("", raw)
    cleaned = _UNCLOSED_THINK_RE.sub("", cleaned)
    return cleaned.strip()


def detect_android_llm_capabilities(models_dir: Optional[Path] = None, llama_url: str = "http://127.0.0.1:8080") -> Dict:
    """Inspect CPU ISA features, RAM headroom, installed GGUF files, and recommended local model tier."""
    base_dir = models_dir or (Path.home() / "models" / "llm")
    arch = platform.machine() or os.uname().machine if hasattr(os, "uname") else platform.machine()
    cpu_cores = os.cpu_count() or 4

    isa_detected: List[str] = []
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        try:
            txt = cpuinfo.read_text(encoding="utf-8", errors="ignore").lower()
            m = re.search(r"(?:features|flags)\s*:\s*(.+)", txt)
            if m:
                raw_flags = set(m.group(1).split())
                isa_detected = [f for f in _ISA_FLAGS if f in raw_flags]
        except OSError:
            pass

    total_ram_gb = 0.0
    avail_ram_gb = 0.0
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            mtxt = meminfo.read_text(encoding="utf-8", errors="ignore")
            mt = re.search(r"MemTotal:\s+(\d+)\s+kB", mtxt)
            ma = re.search(r"MemAvailable:\s+(\d+)\s+kB", mtxt)
            if mt:
                total_ram_gb = round(int(mt.group(1)) / (1024 * 1024), 2)
            if ma:
                avail_ram_gb = round(int(ma.group(1)) / (1024 * 1024), 2)
        except OSError:
            pass

    ggufs: List[Dict] = []
    if base_dir.is_dir():
        for p in sorted(base_dir.glob("*.gguf")):
            try:
                st = p.stat()
                ggufs.append({
                    "name": p.name,
                    "size_mb": round(st.st_size / (1024 * 1024), 1),
                    "path": str(p),
                })
            except OSError:
                continue

    tier = GGUF_MODEL_TIERS[0]
    eff_ram = total_ram_gb if total_ram_gb > 0 else 4.0
    for cand in GGUF_MODEL_TIERS:
        if eff_ram >= cand["min_ram_gb"]:
            tier = cand

    llama_online = False
    active_model = ""
    try:
        req = urllib.request.Request(f"{llama_url.rstrip('/')}/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data") or []
            llama_online = True
            if models:
                active_model = str(models[0].get("id") or "")
    except Exception:
        pass

    return {
        "arch": str(arch or "unknown"),
        "cpu_cores": int(cpu_cores),
        "recommended_threads": min(4, max(2, int(cpu_cores) // 2)),
        "isa_features": isa_detected,
        "has_fast_gemm": any(k in isa_detected for k in ("asimddp", "dotprod", "i8mm")),
        "total_ram_gb": total_ram_gb,
        "avail_ram_gb": avail_ram_gb,
        "recommended_tier": tier,
        "gguf_models": ggufs,
        "llama_server_online": llama_online,
        "active_model": active_model or (ggufs[0]["name"] if ggufs else "offline-heuristic"),
    }


def benchmark_local_llm(llama_url: str = "http://127.0.0.1:8080") -> Dict:
    """Measure local llama-server TTFT + tok/s or return deterministic CPU telemetry."""
    caps = detect_android_llm_capabilities(llama_url=llama_url)
    if caps["llama_server_online"]:
        t0 = time.perf_counter()
        payload = json.dumps({
            "model": caps["active_model"] or "local",
            "messages": [{"role": "user", "content": "Diga apenas: Motor offline pronto em 1 linha."}],
            "max_tokens": 24,
            "temperature": 0.1,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{llama_url.rstrip('/')}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = max(1.0, (time.perf_counter() - t0) * 1000.0)
            usage = data.get("usage") or {}
            comp_toks = int(usage.get("completion_tokens") or 12)
            tok_s = round((comp_toks / (elapsed_ms / 1000.0)), 1)
            raw_reply = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            return {
                "ok": True,
                "mode": "llama-server",
                "model": caps["active_model"],
                "latency_ms": round(elapsed_ms, 1),
                "tokens_per_sec": tok_s,
                "sample_reply": strip_reasoning_tags(raw_reply)[:120],
                "isa_features": caps["isa_features"],
            }
        except Exception as exc:
            return {"ok": False, "mode": "llama-server-error", "error": str(exc), "isa_features": caps["isa_features"]}

    # Pure-Python deterministic CPU / SHA throughput fallback benchmark (inspired by Project NOMAD)
    t0 = time.perf_counter()
    blob = b"autoshorts-arm64-probe" * 256
    for _ in range(400):
        blob = hashlib.sha256(blob).digest()
    cpu_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "ok": True,
        "mode": "cpu-heuristic",
        "model": caps["active_model"],
        "latency_ms": cpu_ms,
        "tokens_per_sec": 0.0,
        "recommended_tier": caps["recommended_tier"],
        "isa_features": caps["isa_features"],
        "note": "llama-server desligado; usando pipeline heuristico instantaneo + nuvem gratis.",
    }


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(str(text or "")) if len(t) > 1]


def bm25_search_shorts(query: str, out_dir: Path, top_k: int = 5) -> List[Dict]:
    """Rank generated Shorts and publish metadata offline with Okapi BM25 (zero dependencies)."""
    q_tokens = _tokenize(query)
    if not q_tokens or not out_dir.is_dir():
        return []

    docs: List[Dict] = []
    for p in sorted(out_dir.glob("*.publish.json")):
        try:
            pack = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        text = " ".join([
            str(pack.get("title") or ""),
            str(pack.get("hook_title") or ""),
            str(pack.get("caption") or ""),
            str(pack.get("niche") or ""),
            " ".join(pack.get("hashtags") or []),
        ])
        toks = _tokenize(text)
        if toks:
            mp4_name = f"{p.name[:-len('.publish.json')]}.mp4" if p.name.endswith(".publish.json") else p.with_suffix(".mp4").name
            docs.append({"filename": mp4_name, "pack": pack, "tokens": toks})

    if not docs:
        return []

    n_docs = len(docs)
    avgdl = sum(len(d["tokens"]) for d in docs) / max(1, n_docs)
    df: Dict[str, int] = {}
    for qt in set(q_tokens):
        df[qt] = sum(1 for d in docs if qt in d["tokens"])

    k1, b = 1.5, 0.75
    scored: List[tuple[float, Dict]] = []
    for d in docs:
        toks = d["tokens"]
        dl = len(toks)
        tf_map: Dict[str, int] = {}
        for tok in toks:
            tf_map[tok] = tf_map.get(tok, 0) + 1
        score = 0.0
        for qt in q_tokens:
            f = tf_map.get(qt, 0)
            if f <= 0:
                continue
            idf = math.log(1.0 + (n_docs - df[qt] + 0.5) / (df[qt] + 0.5))
            denom = f + k1 * (1.0 - b + b * (dl / max(1.0, avgdl)))
            score += idf * ((f * (k1 + 1.0)) / max(1e-9, denom))
        if score > 0:
            scored.append((round(score, 4), {
                "filename": d["filename"],
                "title": d["pack"].get("title", d["filename"]),
                "hook_title": d["pack"].get("hook_title", ""),
                "niche": d["pack"].get("niche", ""),
                "score_bm25": round(score, 3),
                "opus_score": (d["pack"].get("opus_scorecard") or {}).get("opus_score"),
            }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:top_k]]


def answer_studio_question_offline(
    prompt: str,
    out_dir: Path,
    llama_url: str = "http://127.0.0.1:8080",
) -> Dict:
    """Answer user prompt using BM25 local context + local llama-server (or deterministic fallback)."""
    q = str(prompt or "").strip()
    if not q:
        return {"ok": False, "answer": "Informe uma pergunta ou comando.", "sources": [], "backend": "none"}

    hits = bm25_search_shorts(q, out_dir, top_k=4)
    caps = detect_android_llm_capabilities(llama_url=llama_url)
    ctx_lines = [
        f"- {h['title']} ({h['filename']}, nicho={h['niche']}, hook={h['hook_title']})"
        for h in hits
    ]
    ctx_blob = "\n".join(ctx_lines) if ctx_lines else "Nenhum Short correspondente no acervo."

    if caps["llama_server_online"]:
        sys_msg = (
            "Voce e o assistente offline do AutoShorts Studio no Android/Termux. "
            "Responda em portugues claro em no maximo 4 frases usando o contexto BM25 abaixo.\n"
            f"Acervo relevante:\n{ctx_blob}"
        )
        payload = json.dumps({
            "model": caps["active_model"] or "local",
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": q},
            ],
            "max_tokens": 220,
            "temperature": 0.4,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{llama_url.rstrip('/')}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_txt = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            clean_txt = strip_reasoning_tags(raw_txt)
            if clean_txt:
                return {"ok": True, "answer": clean_txt, "sources": hits, "backend": f"llama-server ({caps['active_model']})"}
        except Exception:
            pass

    if hits:
        summary = " | ".join(f"{h['title']} [BM25 {h['score_bm25']}]" for h in hits)
        ans = f"Encontrei {len(hits)} Short(s) relevantes offline (BM25): {summary}."
    else:
        ans = (
            f"Sistema offline pronto ({caps['arch']}, {caps['cpu_cores']} nucleos, "
            f"modelo recomendado: {caps['recommended_tier']['label']}). "
            "Nenhuma correspondencia exata encontrada no acervo atual."
        )
    return {"ok": True, "answer": ans, "sources": hits, "backend": "bm25-offline"}
