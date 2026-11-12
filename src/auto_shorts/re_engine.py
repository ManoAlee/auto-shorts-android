"""Advanced Reverse Engineering, YouTube InnerTube Heatmap & OMEGA-SYNAPSE Resilience Core.

Combines techniques inspired by open-source GitHub engineering projects:
- InnerTube & Most-Replayed Heatmap Reverse Engineering (youtube-heatmap / yt-heatmap-clipper)
- Kinetic Word-Cadence & Subtitle Beat Profiling (MoneyPrinterTurbo / auto-captions / pycaps)
- Native ELF + C11 Symbol & Literal Trace (REA-compatible static xref trace)
- Closed-Loop Mahoraga Immunity & Faro p50/p95 Latency Telemetry (OMEGA-SYNAPSE)
"""

import ast
import datetime as _dt
import hashlib
import json
import re
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional


BUILTIN_IMMUNITY_RULES = [
    {
        "id": "kokoro_tensor_f32_guard",
        "signature": "onnxruntime float32 speed tensor & >210 char prosody cutoff",
        "mitigation": "Chunk PT-BR sentences <=210 chars with 0.16s pause and float32 ONNX tensor binding.",
        "spoke": "Faro TTS Guard",
        "status": "ACTIVE",
    },
    {
        "id": "llama_chatml_leak_shield",
        "signature": "Local Qwen/Llama meta-reasoning leak (First, I need / <think> / /data/data/)",
        "mitigation": "Wrap llama-cli in ChatML stops, strip <think> + prefaces, reject en_leaks>=3 in validator.",
        "spoke": "Dharma Lexical Shield",
        "status": "ACTIVE",
    },
    {
        "id": "stagnant_visual_roi_reject",
        "signature": "Static/frozen MP4 frames or empty titleband false positive",
        "mitigation": "Sample 5 frames across clip, enforce center ROI motion >=1.8 and frozen_pairs < 2.",
        "spoke": "Visual Motion Gate",
        "status": "ACTIVE",
    },
    {
        "id": "ffmpeg_audio_stream_probe",
        "signature": "Stream specifier ':a' matches no streams on silent stock/news clip",
        "mitigation": "Inspect ffprobe stream metadata before aselect/filter_complex routing.",
        "spoke": "FFmpeg Graph Guard",
        "status": "ACTIVE",
    },
    {
        "id": "youtube_quota_queue_deferral",
        "signature": "YouTube Data API v3 uploadLimitExceeded daily quota exhaustion",
        "mitigation": "Park validated MP4+SEO packs in safe auto-publish queue for flush on quota reset.",
        "spoke": "Faro Queue Deferral",
        "status": "ACTIVE",
    },
    {
        "id": "ucb1_background_anti_repeat",
        "signature": "Visual monotony from single repeated background gameplay",
        "mitigation": "10 UCB1 background styles + topic-dynamic query discovery + .last_gameplay lock.",
        "spoke": "UCB1 Entropy Engine",
        "status": "ACTIVE",
    },
    {
        "id": "bright_background_luma_gate",
        "signature": "Dark space/fade-in background clip (luma < 20) causing blank black Short rejection",
        "mitigation": "1-frame 32x32 FFmpeg luma+std probe before render with UCB1 penalty & bright fallback.",
        "spoke": "Luma Pre-Render Gate",
        "status": "ACTIVE",
    },
    {
        "id": "pytubefix_download_failover",
        "signature": "yt-dlp HTTP 403 / PO-token block on YouTube video streams",
        "mitigation": "Automatic secondary failover to pytubefix progressive stream acquisition.",
        "spoke": "Dual-Stack Downloader",
        "status": "ACTIVE",
    },
    {
        "id": "multiscene_broll_sidechain_audio",
        "signature": "Single static background monotony or BGM swallowing narration speech",
        "mitigation": "Rotate 4.2s multi-scene visual cuts across bright styles + FFmpeg sidechaincompress ducking.",
        "spoke": "Kinetic B-Roll & Ducking",
        "status": "ACTIVE",
    },
    {
        "id": "opus_perception_signalstats_runbook",
        "signature": "Flat/low-variance frames or slow late-stakes Shorts under 70% reach bar",
        "mitigation": "OpusClip video-perception FFmpeg signalstats + reel-runbook 0-100 calibrated hook grader.",
        "spoke": "Opus Perception & Scorecard",
        "status": "ACTIVE",
    },
]


def extract_youtube_video_id(url_or_id: str) -> str:
    raw = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    parsed = urllib.parse.urlparse(raw)
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        cand = qs["v"][0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", cand):
            return cand
    m = re.search(r"(?:youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", raw)
    return m.group(1) if m else ""


def _parse_json_object_after_marker(html: str, marker: str) -> Optional[Dict]:
    idx = html.find(marker)
    if idx < 0:
        return None
    brace_start = html.find("{", idx)
    if brace_start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(brace_start, min(len(html), brace_start + 1_500_000)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[brace_start : i + 1])
                except Exception:
                    return None
    return None


def _extract_heat_markers_recursive(obj: object, limit: int = 120) -> List[Dict]:
    out: List[Dict] = []

    def _walk(node: object) -> None:
        if len(out) >= limit:
            return
        if isinstance(node, dict):
            hm = node.get("heatMarkerRenderer")
            if isinstance(hm, dict):
                start_ms = hm.get("timeRangeStartMillis")
                dur_ms = hm.get("markerDurationMillis")
                score = hm.get("heatMarkerIntensityScoreNormalized")
                if isinstance(start_ms, (int, float)) and isinstance(score, (int, float)):
                    out.append({
                        "start_sec": round(float(start_ms) / 1000.0, 2),
                        "duration_sec": round(float(dur_ms or 5000.0) / 1000.0, 2),
                        "intensity": round(float(score), 4),
                    })
                    return
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for it in node:
                _walk(it)

    _walk(obj)
    out.sort(key=lambda x: x["start_sec"])
    return out


def call_innertube_player(
    video_id: str,
    poster: Optional[Callable[[str, Dict], Dict]] = None,
    timeout: int = 10,
) -> Dict:
    """Query YouTube internal /youtubei/v1/player endpoint using ANDROID client context."""
    url = "https://www.youtube.com/youtubei/v1/player"
    body = {
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "19.09.37",
                "androidSdkVersion": 34,
                "hl": "pt",
                "gl": "BR",
            }
        },
        "videoId": video_id,
    }
    if poster is not None:
        try:
            return poster(url, body) or {}
        except Exception:
            return {}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "com.google.android.youtube/19.09.37"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def inspect_youtube_innertube(
    url_or_id: str,
    fetcher: Optional[Callable[[str], str]] = None,
    timeout: int = 15,
) -> Dict:
    """Reverse-engineer YouTube watch page + ytInitialData Most-Replayed heatmap & retention peaks."""
    vid = extract_youtube_video_id(url_or_id)
    if not vid:
        return {"ok": False, "error": "ID ou link de video YouTube invalido."}

    watch_url = f"https://www.youtube.com/watch?v={vid}&hl=pt&gl=BR"

    def _default_fetch(target_url: str) -> str:
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    get_text = fetcher or _default_fetch
    try:
        html = get_text(watch_url)
    except Exception as exc:
        return {"ok": False, "video_id": vid, "error": str(exc)}

    player = _parse_json_object_after_marker(html, "ytInitialPlayerResponse =") or {}
    initial_data = _parse_json_object_after_marker(html, "ytInitialData =") or {}

    vd = player.get("videoDetails") or {}
    title = str(vd.get("title") or "").strip()
    channel = str(vd.get("author") or "").strip()
    length_sec = int(float(vd.get("lengthSeconds") or 0))
    views = int(float(vd.get("viewCount") or 0))

    markers = _extract_heat_markers_recursive(initial_data)
    source_method = "ytInitialData.heatMarkerRenderer"

    # Fallback: InnerTube /youtubei/v1/player ANDROID client if HTML metadata missed details
    if not vd and fetcher is None:
        player = call_innertube_player(vid, timeout=timeout) or {}
        vd = player.get("videoDetails") or {}
        title = str(vd.get("title") or title).strip()
        channel = str(vd.get("author") or channel).strip()
        length_sec = int(float(vd.get("lengthSeconds") or length_sec or 0))
        views = int(float(vd.get("viewCount") or views or 0))

    # Fallback: LemnosLife community InnerTube proxy if page DOM omits markers
    if not markers and fetcher is None:
        try:
            lemnos = get_text(f"https://yt.lemnoslife.com/videos?part=mostReplayed&id={vid}")
            ldata = json.loads(lemnos)
            raw_m = (((ldata.get("items") or [{}])[0]).get("mostReplayed") or {}).get("markers") or []
            for m in raw_m[:120]:
                markers.append({
                    "start_sec": round(float(m.get("startMillis", 0)) / 1000.0, 2),
                    "duration_sec": round(max(4.0, (length_sec / max(1, len(raw_m)))), 2),
                    "intensity": round(float(m.get("intensityScoreNormalized", 0)), 4),
                })
            if markers:
                source_method = "innertube.lemnos_mostReplayed"
        except Exception:
            pass

    peaks: List[Dict] = []
    if markers:
        ranked = sorted(markers, key=lambda m: m["intensity"], reverse=True)
        chosen: List[Dict] = []
        for m in ranked:
            if all(abs(m["start_sec"] - c["start_sec"]) >= 25.0 for c in chosen):
                end_s = min(length_sec or (m["start_sec"] + 45.0), round(m["start_sec"] + 42.0, 1))
                chosen.append({
                    "start_sec": max(0.0, round(m["start_sec"] - 4.0, 1)),
                    "peak_sec": m["start_sec"],
                    "end_sec": end_s,
                    "intensity_pct": round(m["intensity"] * 100, 1),
                    "label": f"Pico {int(m['start_sec'] // 60)}:{int(m['start_sec'] % 60):02d} • {round(m['intensity'] * 100)}% Replayed",
                })
            if len(chosen) >= 4:
                break
        peaks = chosen
    elif length_sec > 30:
        source_method = "innertube.structural_fallback"
        for frac, lbl in ((0.18, "Gancho Inicial"), (0.48, "Climax Central"), (0.76, "Virada Final")):
            st = round(length_sec * frac, 1)
            peaks.append({
                "start_sec": st,
                "peak_sec": round(st + 12.0, 1),
                "end_sec": round(min(length_sec, st + 42.0), 1),
                "intensity_pct": round(82.0 - frac * 10, 1),
                "label": f"{lbl} ({int(st // 60)}:{int(st % 60):02d})",
            })

    return {
        "ok": True,
        "video_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": title or f"Video {vid}",
        "channel": channel or "YouTube",
        "duration_sec": length_sec,
        "views": views,
        "method": source_method,
        "heatmap_points": len(markers),
        "heatmap_curve": markers[:60],
        "peaks": peaks,
    }


def analyze_kinetic_pacing(text: str, duration_sec: float = 38.0) -> Dict:
    """Profile Shorts speaking pace and visual-change rhythm (MoneyPrinterTurbo / PyCaps patterns)."""
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    dur = max(1.0, float(duration_sec or 38.0))
    wps = round(len(words) / dur, 2)
    visual_beats = max(1, int(round(dur / 3.0)))
    cadence = "ideal_shorts" if 2.3 <= wps <= 3.6 else ("lento_acelerar" if wps < 2.3 else "rapido_dividir")
    return {
        "word_count": len(words),
        "duration_sec": round(dur, 2),
        "words_per_sec": wps,
        "visual_beats_3s": visual_beats,
        "recommended_caption_words": 3 if wps >= 2.8 else 4,
        "cadence_status": cadence,
    }


def score_short_opus_runbook(pack: Dict, validation: Optional[Dict] = None, duration: float = 0.0) -> Dict:
    """Calibrated 0-100 Short scorecard synthesized from opus-pro/reel-runbook empirical findings."""
    val = validation or pack.get("validation") or {}
    vis = (pack.get("visual_audit") or {}).get("visual") or {}
    dur = float(duration or val.get("duration") or 38.0)
    hook = str(pack.get("hook_title") or pack.get("title") or "").strip()
    cap = str(pack.get("caption") or "").strip()

    # 1. First frame contrast & visual punch (0-20)
    luma_std = float(vis.get("luma_std") or 35.0)
    sig = vis.get("signalstats") or {}
    yrange = float(sig.get("yrange_mean") or (luma_std * 3.5))
    c_first = 18 if (yrange >= 90 and len(hook) >= 6) else (14 if luma_std >= 22 else 8)

    # 2. Hook 0-3s curiosity/stakes density (0-20)
    flaws: List[str] = []
    hk_words = hook.split()
    strong_triggers = ("segredo", "erro", "nunca", "muda", "ninguem", "porque", "agora", "hoje", "teoria", "verdade")
    has_trigger = any(t in hook.lower() or t in cap[:180].lower() for t in strong_triggers)
    c_hook = 18 if (2 <= len(hk_words) <= 8 and has_trigger) else (14 if hk_words else 7)
    if ">>" in hook or hook.startswith('"') or "salve, salve" in hook.lower() or "autoshorts" in hook.lower():
        c_hook = min(c_hook, 9)
        flaws.append("Gancho/titulo com saudacao generica ou marcador '>>'; execute Otimizar IA.")

    # 3. Re-hook visual cadence (~3s switches / subtitles coverage) (0-20)
    bg_style = str(pack.get("background_style") or "")
    cues = int(val.get("subtitle_cues") or 0)
    has_multi_bg = ("+" in bg_style) or float(vis.get("motion_delta") or 0) >= 12.0
    if cues == 0:
        c_rehook = 11 if has_multi_bg else 7
        flaws.append("Zero legendas detectadas (0 cues) — retencao no feed mudo cai ~40%.")
    else:
        c_rehook = 19 if (has_multi_bg and cues >= 12) else (15 if (cues >= 8 or has_multi_bg) else 9)

    # 4. Payoff & crisp ending without repetitive beg-outro bloat (0-20)
    is_tiktok = "tiktok" in str(pack.get("platform") or pack.get("output_path") or "").lower()
    weak_outro = "acompanhar os proximos cortes" in cap.lower() and dur > 52.0 and not is_tiktok
    if weak_outro:
        flaws.append("Outro generico longo no final; encurte payoff para elevar loop.")
    c_payoff = 15 if weak_outro else (18 if (18.0 <= dur <= 58.0 or (is_tiktok and 60.0 <= dur <= 130.0)) else 13)
    if dur > 57.0 and not is_tiktok:
        flaws.append("Duracao perto de 60s reduz taxa de conclusao no Feed Shorts.")
    if not has_multi_bg:
        flaws.append("Fundo unico ou pouco dinamico — prefira B-Roll multi-cena ~4s.")

    # 5. Audio clarity & caption sync (0-20)
    vol = val.get("mean_volume_db")
    overlaps = int(val.get("subtitle_overlaps") or 0)
    vol_ok = isinstance(vol, (int, float)) and -21.0 <= float(vol) <= -12.0
    if cues == 0:
        c_audio = 10 if vol_ok else 7
    else:
        c_audio = 20 if (vol_ok and overlaps == 0) else (14 if overlaps == 0 else 8)
    if overlaps > 0:
        flaws.append(f"{overlaps} sobreposicoes de legenda detectadas.")

    total = max(0, min(100, c_first + c_hook + c_rehook + c_payoff + c_audio))
    return {
        "opus_score": total,
        "band": "ESCALAR (>=70 • 2.7x+ alcance potencial)" if total >= 70 else "REEDITAR (<70)",
        "dimensions": {
            "first_frame_contrast": c_first,
            "hook_0_3s": c_hook,
            "rehook_cadence": c_rehook,
            "payoff_no_bloat": c_payoff,
            "audio_clarity": c_audio,
        },
        "flaws": flaws,
    }


def inspect_elf_header(binary_path: Path) -> Dict:
    """Parse ELF header deterministically (without external tools) for ARM64/x86_64 C11 audits."""
    if not binary_path.exists() or not binary_path.is_file():
        return {"exists": False}
    raw = binary_path.read_bytes()
    info: Dict = {
        "exists": True,
        "path": str(binary_path),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
        "format": "unknown",
    }
    if len(raw) >= 24 and raw[:4] == b"\x7fELF":
        ei_class = "ELF64" if raw[4] == 2 else ("ELF32" if raw[4] == 1 else "ELF?")
        endian = "<" if raw[5] == 1 else ">"
        e_type, e_machine = struct.unpack(endian + "HH", raw[16:20])
        arch_map = {0xB7: "AArch64 (ARM64)", 0x3E: "x86-64", 0x28: "ARM", 0x03: "x86"}
        info.update({
            "format": "elf",
            "class": ei_class,
            "architecture": arch_map.get(e_machine, f"0x{e_machine:x}"),
            "elf_type": "DYN/PIE" if e_type == 3 else ("EXEC" if e_type == 2 else str(e_type)),
            "strings_preview": [
                s.decode("ascii", errors="ignore")
                for s in re.findall(rb"[ -~]{6,48}", raw)[:24]
            ],
        })
    return info


def rea_trace_system(query: str, root_dir: Optional[Path] = None, max_hits: int = 35) -> Dict:
    """Trace a literal symbol or feature across C11 native-c, ELF binary, and Python AST."""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Informe uma consulta literal (ex: autopilot, moov, Kokoro, heatMarker)."}

    base = root_dir or Path(__file__).resolve().parents[2]
    ql = q.lower()
    matches: List[Dict] = []
    scanned_files = 0

    scan_dirs = [base / "native-c", base / "src" / "auto_shorts"]
    for d in scan_dirs:
        if not d.exists():
            continue
        for fpath in sorted(d.rglob("*")):
            if fpath.suffix not in {".c", ".h", ".py"} or not fpath.is_file():
                continue
            scanned_files += 1
            try:
                lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            current_fn = "<module>"
            fn_stack: List[tuple[int, str]] = []
            for idx, line in enumerate(lines, start=1):
                if fpath.suffix == ".py":
                    m_py = re.match(r"^(\s*)(?:async\s+)?def\s+([A-Za-z0-9_]+)\(", line)
                    if m_py:
                        ind = len(m_py.group(1))
                        while fn_stack and fn_stack[-1][0] >= ind:
                            fn_stack.pop()
                        fn_stack.append((ind, m_py.group(2)))
                        current_fn = fn_stack[-1][1]
                elif fpath.suffix in {".c", ".h"}:
                    m_c = re.match(r"^(?:static\s+)?(?:int|void|char|double)\s+\*?([A-Za-z0-9_]+)\s*\(", line)
                    if m_c and not line.strip().endswith(";"):
                        current_fn = m_c.group(1)

                if ql in line.lower():
                    matches.append({
                        "file": str(fpath.relative_to(base)).replace("\\", "/"),
                        "line": idx,
                        "symbol": current_fn,
                        "layer": "c11_native" if fpath.suffix in {".c", ".h"} else "python_core",
                        "snippet": line.strip()[:160],
                    })
                    if len(matches) >= max_hits:
                        break
            if len(matches) >= max_hits:
                break

    elf_info = inspect_elf_header(base / "bin" / "autoshorts")
    elf_hits = [
        s for s in (elf_info.get("strings_preview") or []) if ql in s.lower()
    ]
    if elf_info.get("exists") and not elf_hits:
        try:
            raw = (base / "bin" / "autoshorts").read_bytes()
            for off_m in re.finditer(re.escape(q.encode("utf-8", errors="ignore")), raw, flags=re.IGNORECASE):
                elf_hits.append(f"offset 0x{off_m.start():x}")
                if len(elf_hits) >= 6:
                    break
        except Exception:
            pass

    return {
        "ok": True,
        "query": q,
        "scanned_files": scanned_files,
        "total_hits": len(matches),
        "matches": matches,
        "native_binary": {
            k: v for k, v in elf_info.items() if k != "strings_preview"
        },
        "binary_string_hits": elf_hits,
    }


def _telemetry_file(output_dir: Path) -> Path:
    return output_dir / "synapse_telemetry.json"


def load_synapse_telemetry(output_dir: Path) -> Dict:
    p = _telemetry_file(output_dir)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"stages": {}, "custom_immunities": [], "updated_at": ""}


def record_synapse_stage(output_dir: Path, stage: str, elapsed_ms: float, ok: bool = True) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        data = load_synapse_telemetry(output_dir)
        stages = data.setdefault("stages", {})
        rec = stages.setdefault(stage, {"samples_ms": [], "ok": 0, "err": 0})
        samples = list(rec.get("samples_ms") or [])
        samples.append(round(float(elapsed_ms), 1))
        rec["samples_ms"] = samples[-40:]
        rec["ok"] = int(rec.get("ok") or 0) + (1 if ok else 0)
        rec["err"] = int(rec.get("err") or 0) + (0 if ok else 1)
        data["updated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        _telemetry_file(output_dir).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_synapse_overview(output_dir: Path, root_dir: Optional[Path] = None) -> Dict:
    """Compute OMEGA-SYNAPSE Faro & Mahoraga telemetry, p50/p95 latencies, and binary status."""
    raw = load_synapse_telemetry(output_dir)
    base = root_dir or Path(__file__).resolve().parents[2]
    elf_info = inspect_elf_header(base / "bin" / "autoshorts")
    stage_stats: List[Dict] = []
    for name, info in (raw.get("stages") or {}).items():
        vals = sorted(float(v) for v in (info.get("samples_ms") or []) if isinstance(v, (int, float)))
        if not vals:
            continue
        p50 = vals[len(vals) // 2]
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        ok_n = int(info.get("ok") or 0)
        err_n = int(info.get("err") or 0)
        stage_stats.append({
            "stage": name,
            "samples": len(vals),
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "ok": ok_n,
            "err": err_n,
            "success_rate_pct": round((ok_n / max(1, ok_n + err_n)) * 100.0, 1),
        })

    custom = list(raw.get("custom_immunities") or [])
    all_immunities = BUILTIN_IMMUNITY_RULES + custom
    return {
        "protocol": "OMEGA-SYNAPSE v3.0 (Faro + Mahoraga + REA)",
        "wheel_state": "IMMUNE_ACTIVE",
        "immunity_count": len(all_immunities),
        "immunities": all_immunities,
        "stage_latencies": stage_stats,
        "native_binary": {k: v for k, v in elf_info.items() if k != "strings_preview"},
        "github_patterns": [
            "InnerTube & Most-Replayed Heatmap Peak Extractor (ytInitialData + SVG intensity)",
            "MoneyPrinterTurbo / PyCaps Kinetic Beat Pacing (words/sec & 3s visual-change target)",
            "ShortGPT / Multi-Horizon Auto-Rotation (Anime Season/Year/TopLiked + News + UCB1)",
        ],
        "updated_at": raw.get("updated_at") or _dt.datetime.now().isoformat(timespec="seconds"),
    }

