"""
AutoShorts Aegis — CLI-Anything Autonomous Harness (HKUDS Specification)
Interface determinística, estruturada em JSON-First, com auto-cura e diagnósticos
para operação humana e por agentes autônomos.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    _src = Path(__file__).resolve().parent.parent
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    __package__ = "auto_shorts"

from .job_recovery import JobRecoveryManager, JobState


def get_system_health(out_dir: Path) -> Dict[str, Any]:
    """Coleta métricas reais de saúde de baixo nível sem suposições e sem dependência estrita de psutil."""
    total_mb = 0
    avail_mb = 0
    percent_used = 0.0
    swap_used_mb = 0

    # 1. Tentar psutil se instalado
    try:
        import psutil
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        total_mb = vm.total // (1024 * 1024)
        avail_mb = vm.available // (1024 * 1024)
        percent_used = vm.percent
        swap_used_mb = swap.used // (1024 * 1024)
    except ImportError:
        # Fallback Linux/Android: ler /proc/meminfo diretamente
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.is_file():
            try:
                info: Dict[str, int] = {}
                for line in meminfo_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        info[k] = int(v)
                total_kb = info.get("MemTotal", 0)
                avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
                total_mb = total_kb // 1024
                avail_mb = avail_kb // 1024
                used_kb = total_kb - avail_kb
                percent_used = round((used_kb / total_kb * 100.0), 1) if total_kb > 0 else 0.0
                swap_total_kb = info.get("SwapTotal", 0)
                swap_free_kb = info.get("SwapFree", 0)
                swap_used_mb = (swap_total_kb - swap_free_kb) // 1024
            except Exception:
                pass

    pressure = "NORMAL"
    if avail_mb < 250:
        pressure = "CRITICAL"
    elif avail_mb < 500:
        pressure = "CONSTRAINED"

    # Disk usage via shutil.disk_usage (Standard Library)
    import shutil
    try:
        disk = shutil.disk_usage(str(out_dir.resolve()))
        total_gb = round(disk.total / (1024**3), 1)
        free_gb = round(disk.free / (1024**3), 1)
        disk_pct = round((disk.used / disk.total * 100.0), 1) if disk.total > 0 else 0.0
    except Exception:
        total_gb = 0.0
        free_gb = 0.0
        disk_pct = 0.0

    # Checar portas locais
    web_ok = False
    ssh_ok = False
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            web_ok = (s.connect_ex(("127.0.0.1", 8787)) == 0)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            ssh_ok = (s.connect_ex(("127.0.0.1", 8022)) == 0)
    except Exception:
        pass

    return {
        "status": "HEALTHY" if (web_ok and pressure != "CRITICAL") else "DEGRADED",
        "timestamp": time.time(),
        "platform": {
            "os": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "services": {
            "webapp_8787": {"alive": web_ok, "port": 8787},
            "sshd_8022": {"alive": ssh_ok, "port": 8022},
        },
        "memory": {
            "total_mb": total_mb,
            "available_mb": avail_mb,
            "percent_used": percent_used,
            "swap_used_mb": swap_used_mb,
            "pressure": pressure,
        },
        "storage": {
            "total_gb": total_gb,
            "free_gb": free_gb,
            "percent_used": disk_pct,
        },
    }


def cmd_status(args: argparse.Namespace, out_dir: Path) -> int:
    import urllib.request
    status_data = {}
    try:
        req = urllib.request.Request("http://127.0.0.1:8787/api/status", headers={"User-Agent": "CLI-Anything/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        status_data = {"error": f"Servidor Web inacessivel: {exc}", "running": False}

    if args.json:
        print(json.dumps(status_data, indent=2, ensure_ascii=False))
    else:
        print("\n=== AUTOSHORTS STUDIO STATUS ===")
        print(f" Em Execucao : {'SIM' if status_data.get('running') else 'NAO'}")
        print(f" Ultimo Status: {status_data.get('last_status', '-')}")
        print(f" Progresso    : {status_data.get('progress_pct', 0)}%")
        mahoraga = status_data.get("mahoraga", {})
        if mahoraga:
            print(f" Mahoraga Raio: {mahoraga.get('active_spoke', {}).get('name', '-')}")
        print("================================\n")
    return 0 if "error" not in status_data else 3


def cmd_health(args: argparse.Namespace, out_dir: Path) -> int:
    health = get_system_health(out_dir)
    if args.json:
        print(json.dumps(health, indent=2, ensure_ascii=False))
    else:
        print("\n=== AUTOSHORTS AEGIS SYSTEM HEALTH ===")
        print(f" Status Geral : {health['status']}")
        print(f" WebApp :8787 : {'ONLINE' if health['services']['webapp_8787']['alive'] else 'OFFLINE'}")
        print(f" OpenSSH :8022: {'ONLINE' if health['services']['sshd_8022']['alive'] else 'OFFLINE'}")
        print(f" RAM Livre    : {health['memory']['available_mb']} MB (Pressao: {health['memory']['pressure']})")
        print(f" Disco Livre  : {health['storage']['free_gb']} GB")
        print("======================================\n")
    return 0 if health["status"] == "HEALTHY" else 3


def cmd_jobs(args: argparse.Namespace, out_dir: Path) -> int:
    mgr = JobRecoveryManager(out_dir)
    action = getattr(args, "job_action", "list")

    if action == "list":
        jobs = [j.to_dict() for j in mgr.list_jobs(limit=args.limit)]
        if args.json:
            print(json.dumps({"jobs": jobs, "count": len(jobs)}, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== JOBS DE PRODUCAO ({len(jobs)} encontrados) ===")
            for j in jobs:
                print(f" [{j['job_id']}] Estado: {j['state']} | Nicho: {j['niche']} | Erro: {j['last_error'] or 'Nenhum'}")
            print("====================================================\n")
        return 0

    elif action == "recoverable":
        recoverable = [j.to_dict() for j in mgr.find_recoverable_jobs()]
        if args.json:
            print(json.dumps({"recoverable_jobs": recoverable, "count": len(recoverable)}, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== JOBS RECUPERAVEIS ({len(recoverable)} encontrados) ===")
            for j in recoverable:
                print(f" [{j['job_id']}] Estado Anterior: {j['state']} | Criado: {time.ctime(j['created_at'])}")
            print("=========================================================\n")
        return 0

    return 2


def cmd_audit(args: argparse.Namespace, out_dir: Path) -> int:
    from .validator import inspect_video_5d

    path = Path(args.file)
    if not path.is_file():
        err = {"error": f"Arquivo nao encontrado: {path}", "path": str(path)}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"[Erro] Arquivo inexistente: {path}", file=sys.stderr)
        return 2

    scorecard = inspect_video_5d(path)
    if args.json:
        print(json.dumps(scorecard, indent=2, ensure_ascii=False))
    else:
        print("\n=== SCORECARD 5D AUDITORIA DE VIDEO ===")
        print(f" Arquivo    : {path.name}")
        print(f" Nota Geral : {scorecard.get('overall_score', 0)}/100")
        print(f" Status     : {'APROVADO' if scorecard.get('approved') else 'REPROVADO'}")
        print(f" Duração    : {scorecard.get('duration_sec', 0):.1f}s")
        print(f" Resolução  : {scorecard.get('width', 0)}x{scorecard.get('height', 0)}")
        print("=======================================\n")
    return 0 if scorecard.get("approved") else 1


def cmd_omega(args: argparse.Namespace, out_dir: Path) -> int:
    from .omega_cdp import OmegaControlOrchestrator
    orch = OmegaControlOrchestrator(out_dir)
    action = getattr(args, "omega_action", "status")

    if not action or action == "status":
        data = orch.get_dashboard_telemetry()
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("\n=== OMEGA CDP CONTROL ENGINE TELEMETRY ===")
            print(f" Status : {data['status']}")
            print(f" Tarefas: {data['task_counts']}")
            print("==========================================\n")
        return 0

    elif action == "capabilities":
        caps = orch.registry.list_capabilities()
        if args.json:
            print(json.dumps({"capabilities": caps}, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== CAPACIDADES DE PLATAFORMA ({len(caps)}) ===")
            for c in caps:
                print(f" Plataforma: {c['platform']} | Adaptador: {c['primary_adapter']} | Operações: {c['allowed_operations_count']}")
            print("============================================\n")
        return 0

    elif action == "sessions":
        sessions = orch.get_dashboard_telemetry().get("sessions", {})
        if args.json:
            print(json.dumps({"sessions": sessions}, indent=2, ensure_ascii=False))
        else:
            print("\n=== PERFIS DE SESSAO CDP ===")
            for p, s in sessions.items():
                print(f" Plataforma: {p} | Autenticado: {s.get('ready_to_publish')}")
            print("============================\n")
        return 0

    elif action == "tasks":
        sub_act = getattr(args, "action", "list")
        if sub_act == "list":
            tasks = [t.to_dict() for t in orch.list_tasks(limit=getattr(args, "limit", 20))]
            if args.json:
                print(json.dumps({"tasks": tasks, "count": len(tasks)}, indent=2, ensure_ascii=False))
            else:
                print(f"\n=== TAREFAS OMEGA ({len(tasks)} encontradas) ===")
                for t in tasks:
                    print(f" [{t['task_id']}] {t['platform']} | Estado: {t['state']} | Título: {t['title'][:40]}")
                print("================================================\n")
            return 0

        elif sub_act == "create":
            if not getattr(args, "video", "") or not getattr(args, "title", ""):
                err = {"error": "Parametros --video e --title sao obrigatorios"}
                print(json.dumps(err) if args.json else err["error"], file=sys.stderr)
                return 2
            t = orch.create_task(
                platform=getattr(args, "platform", "youtube"),
                video_path=args.video,
                title=args.title,
                require_approval=not getattr(args, "auto_approve", False),
            )
            if args.json:
                print(json.dumps({"task": t.to_dict()}, indent=2, ensure_ascii=False))
            else:
                print(f"[Omega] Tarefa criada com sucesso: {t.task_id} (Estado: {t.state.value})")
            return 0

        elif sub_act == "approve":
            tid = getattr(args, "task_id", "")
            if not tid:
                return 2
            t = orch.approve_task(tid, operator=getattr(args, "operator", "operator_admin"), comment=getattr(args, "comment", ""))
            if args.json:
                print(json.dumps({"task": t.to_dict()}, indent=2, ensure_ascii=False))
            else:
                print(f"[Omega] Tarefa {t.task_id} aprovada.")
            return 0

        elif sub_act == "reject":
            tid = getattr(args, "task_id", "")
            if not tid:
                return 2
            t = orch.reject_task(tid, operator=getattr(args, "operator", "operator_admin"), reason=getattr(args, "reason", ""))
            if args.json:
                print(json.dumps({"task": t.to_dict()}, indent=2, ensure_ascii=False))
            else:
                print(f"[Omega] Tarefa {t.task_id} rejeitada.")
            return 0

        elif sub_act == "verify":
            tid = getattr(args, "task_id", "")
            if not tid:
                return 2
            t = orch.verify_task(tid)
            if args.json:
                print(json.dumps({"task": t.to_dict()}, indent=2, ensure_ascii=False))
            else:
                print(f"[Omega] Tarefa {t.task_id} verificada. Estado: {t.state.value}")
            return 0

    elif action == "inventory":
        health = get_system_health(out_dir)
        catalog_path = Path("auto-shorts-omega-lab/manifests/repository-catalog.json")
        cat_count = 0
        if catalog_path.is_file():
            try:
                cat_count = len(json.loads(catalog_path.read_text(encoding="utf-8")).get("repositories", []))
            except Exception:
                pass
        inv = {
            "host_os": os.name,
            "system_health": health,
            "catalog_repositories_count": cat_count,
            "harness": "Omega Repository Integration Harness",
            "compliance": "HKUDS/CLI-Anything Spec",
        }
        if args.json:
            print(json.dumps(inv, indent=2, ensure_ascii=False))
        else:
            print("\n=== OMEGA SYSTEM & REPOSITORY INVENTORY ===")
            print(f" Status Host : {health.get('status')}")
            print(f" Memória RAM : {health.get('memory', {}).get('available_mb')} MB livres")
            print(f" Repositórios: {cat_count} catalogados no laboratório")
            print("===========================================\n")
        return 0

    elif action == "repos":
        sub_act = getattr(args, "repo_action", "audit")
        try:
            from scripts.omega_repo_harness import OmegaRepoHarness
        except ImportError:
            repo_root = Path(__file__).resolve().parent.parent.parent
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            from scripts.omega_repo_harness import OmegaRepoHarness
        harness = OmegaRepoHarness()
        if sub_act == "audit":
            res = harness.run_audit()
        elif sub_act == "clone":
            res = harness.run_clone()
        elif sub_act == "test":
            res = harness.run_test()
        else:
            res = harness.run_dry_run()

        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== OMEGA REPOSITORIES ({sub_act.upper()}) ===")
            print(json.dumps(res, indent=2, ensure_ascii=False))
            print("=========================================\n")
        return 0

    elif action == "integrations":
        plan_path = Path("auto-shorts-omega-lab/manifests/integration-plan.json")
        data = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {"plan": []}
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("\n=== PLANO DE INTEGRAÇÕES OMEGA ===")
            for step in data.get("plan", []):
                print(f" [{step.get('status')}] {step.get('phase')}: {', '.join(step.get('deliverables', []))}")
            print("==================================\n")
        return 0

    elif action == "live":
        from .live_stream_sniper import GTA6_LAUNCH_WATCHLIST
        targets = [{"name": s.name, "platform": s.platform, "url": s.channel_url} for s in GTA6_LAUNCH_WATCHLIST]
        if args.json:
            print(json.dumps({"watchlist": targets, "count": len(targets)}, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== LIVE STREAM SNIPER WATCHLIST ({len(targets)}) ===")
            for t in targets:
                print(f" [{t['platform'].upper()}] {t['name']}: {t['url']}")
            print("===================================================\n")
        return 0

    elif action == "clips":
        from .live_clipping_multimodal import MultimodalHighlightScorer
        scorer = MultimodalHighlightScorer()
        fake_audio = [0.1, 0.2, 0.15, 0.8, 1.9, 2.4, 1.8, 0.3, 0.2] * 20
        fake_scenes = [12.0, 35.0, 50.0]
        fake_speech = [(2.0, 18.0), (22.0, 48.0)]
        candidates = scorer.evaluate_live_window(fake_audio, fake_scenes, fake_speech)
        res = {"candidates": [c.to_dict() for c in candidates], "count": len(candidates)}
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== CANDIDATOS A CORTE MULTIMODAL ({len(candidates)}) ===")
            for c in candidates:
                print(f" [{c.trigger_type}] {c.start_sec}s -> {c.end_sec}s ({c.duration_sec}s) | Score: {c.overall_score}")
            print("=======================================================\n")
        return 0

    elif action == "forensics":
        from .viral_forensics import ViralForensicsEngine
        engine = ViralForensicsEngine()
        dossier = engine.analyze_short_structure(
            video_id=getattr(args, "video_id", "viral_ref_01"),
            title=getattr(args, "title", "O segredo oculto da nova IA"),
            transcript_text=getattr(args, "transcript", "Como a nova inteligencia artificial consegue rodar inteiramente dentro do seu celular em 2026 sem esquentar a bateria."),
            duration_sec=getattr(args, "duration", 42.0),
            niche=getattr(args, "niche", "tech"),
        )
        json_p, md_p = engine.export_reports(dossier, out_dir=out_dir)
        res = {"dossier": dossier.to_dict(), "json_report": str(json_p), "markdown_report": str(md_p)}
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("\n=== LAUDO PERICIAL DE ENGENHARIA REVERSA (VIRAL FORENSICS) ===")
            print(f" Vídeo     : {dossier.source_title}")
            print(f" Hook Score: {dossier.hook_analysis.retention_score}/100 ({dossier.hook_analysis.hook_type})")
            print(f" Ritmo CPM : {dossier.pacing_analysis.cuts_per_minute} cortes/min")
            print(f" Relatórios: {json_p.name} e {md_p.name}")
            print("==============================================================\n")
        return 0

    elif action == "video":
        sub_act = getattr(args, "video_action", "validate")
        from .visual_qa_engine import VisualQAEngine
        engine = VisualQAEngine(out_dir=out_dir)
        target_f = getattr(args, "file", "")
        if not target_f or not Path(target_f).is_file():
            err = {"error": f"Arquivo de vídeo não encontrado: {target_f}"}
            print(json.dumps(err) if args.json else err["error"], file=sys.stderr)
            return 2
        diag = engine.run_deep_diagnostics(target_f)
        if args.json:
            print(json.dumps(diag, indent=2, ensure_ascii=False))
        else:
            print("\n=== DIAGNOSTICO VISUAL QA ===")
            print(f" Arquivo    : {diag.get('file_name')}")
            print(f" Telas Pretas: {diag.get('black_frames_detected')}")
            print(f" Telas Congel: {diag.get('frozen_frames_detected')}")
            print(f" Silêncio   : {diag.get('silence_intervals_detected')}")
            print(f" Aprovado   : {'SIM' if diag.get('passed') else 'NAO'}")
            print("=============================\n")
        return 0 if diag.get("passed") else 1

    elif action == "report":
        try:
            from scripts.omega_repo_harness import OmegaRepoHarness
        except ImportError:
            repo_root = Path(__file__).resolve().parent.parent.parent
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            from scripts.omega_repo_harness import OmegaRepoHarness
        rep = OmegaRepoHarness().run_report()
        if args.json:
            print(json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            print(f"[Omega] Relatório gerado com sucesso: {rep.get('title')}")
        return 0

    return 2


def cmd_studio(args: argparse.Namespace, out_dir: Path) -> int:
    from .design_system import DesignSystemManager
    from .quality_gates import QualityGatesEngine
    from .atlas_studio_harness import AtlasStudioMultiAgentHarness

    act = getattr(args, "studio_action", "presets")

    if not act or act == "presets":
        ds = DesignSystemManager()
        presets = ds.list_presets()
        if args.json:
            print(json.dumps({"presets": presets}, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== ATLAS STUDIO DESIGN PRESETS ({len(presets)}) ===")
            for p in presets:
                print(f" [{p['id']}] {p['label']} | Cor: {p['accent_color_hex']} | Fonte: {p['primary_font']}")
            print("==================================================\n")
        return 0

    elif act == "gates":
        file_path = getattr(args, "file", "")
        if not file_path or not Path(file_path).is_file():
            err = {"error": f"Arquivo MP4 nao encontrado: {file_path}"}
            print(json.dumps(err) if args.json else err["error"], file=sys.stderr)
            return 2
        engine = QualityGatesEngine(out_dir)
        card = engine.evaluate_video(
            mp4_path=file_path,
            title=getattr(args, "title", "Video de Teste"),
            niche=getattr(args, "niche", "podcast"),
            platform=getattr(args, "platform", "youtube_shorts"),
        )
        if args.json:
            print(json.dumps(card.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("\n=== ATLAS STUDIO QUALITY GATES (A-G) ===")
            print(f" Arquivo    : {card.file_name}")
            print(f" Nota Geral : {card.overall_score}/100")
            print(f" Aprovado   : {'SIM' if card.is_approved else 'NAO'}")
            for k, g in card.gates.items():
                print(f" Gate {k} ({g.gate_name}): {'PASS' if g.passed else 'FAIL'} (Score: {g.score})")
            print("=========================================\n")
        return 0 if card.is_approved else 1

    elif act == "pipeline":
        niche = getattr(args, "niche", "tech")
        topic = getattr(args, "topic", "Inovacoes de IA no Brasil")
        job_id = getattr(args, "job_id", f"job_studio_{int(time.time())}")
        harness = AtlasStudioMultiAgentHarness(out_dir)
        res = harness.execute_studio_pipeline(
            job_id=job_id,
            niche=niche,
            topic=topic,
            operator=getattr(args, "operator", "operator_admin"),
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("\n=== ATLAS STUDIO 13-PERSONA HARNESS PIPELINE ===")
            print(f" Job ID   : {res['job_id']}")
            print(f" Nicho    : {res['niche']} (Preset: {res['preset_applied']})")
            print(f" Contratos: {res['contracts_count']} personas executadas")
            print(f" Status   : {res['status']}")
            print("================================================\n")
        return 0

    return 2


def cmd_sentinel(args, out_dir: Path) -> int:
    """Executa auditoria pre-render multimodal e 10 Quality Gates do Sentinel."""
    from .sentinel_pre_render import (
        ContentBrief,
        PreviewMode,
        SceneContract,
        SentinelPreRenderOrchestrator,
    )

    act = getattr(args, "sentinel_action", "status") or "status"

    if act == "status":
        reports_dir = out_dir / "sentinel" / "reports"
        reports_count = len(list(reports_dir.glob("*.json"))) if reports_dir.is_dir() else 0
        data = {
            "ok": True,
            "engine": "AutoShortsSentinelPreRenderEngine",
            "active": True,
            "reports_count": reports_count,
            "reports_dir": str(reports_dir),
        }
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("\n=== AUTO SHORTS SENTINEL (PRE-RENDER INTELLIGENCE) ===")
            print(" Status: ATIVO")
            print(f" Relatórios Gerados: {reports_count}")
            print(f" Diretório: {reports_dir}")
            print("======================================================\n")
        return 0

    elif act == "validate":
        title = getattr(args, "title", "Vídeo Planejado")
        script_text = getattr(args, "script", "")
        niche = getattr(args, "niche", "geral")
        platform = getattr(args, "platform", "youtube_shorts")
        auto_correct = not getattr(args, "no_auto_correct", False)

        brief = ContentBrief(
            title=title,
            topic=getattr(args, "topic", "Geral"),
            platform=platform,
            niche=niche,
        )
        orch = SentinelPreRenderOrchestrator(out_dir=out_dir / "sentinel")
        report = orch.run_pre_render_validation(
            brief=brief,
            script_text=script_text,
            auto_correct=auto_correct,
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("\n=== SENTINEL PRE-RENDER QUALITY GATES AUDIT ===")
            print(f" Título     : {report.title}")
            print(f" Nota Geral : {report.overall_score}/100")
            print(f" Autorizado : {'LIBERADO PARA PRODUÇÃO' if report.is_approved else 'BLOQUEADO'}")
            for g_id, g in report.gates.items():
                status_sym = "✅ PASS" if g.status.value == "PASS" else f"❌ {g.status.value}"
                print(f" {g_id} ({g.name}): {status_sym} (Score: {g.score}/100)")
            if report.detected_issues:
                print("\n Problemas Detectados:")
                for iss in report.detected_issues:
                    print(f"  - [{iss.get('gate')}]: {'; '.join(iss.get('errors') or iss.get('warnings') or [])}")
            if report.revision_history:
                print("\n Auto-Correções Aplicadas:")
                for rev in report.revision_history:
                    print(f"  - [{rev.get('type')}]: {rev}")
            print("===============================================\n")

        return 0 if report.is_approved else 1

    return 2


def build_cli_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Saída em formato JSON estruturado (Agent-First)")
    common.add_argument("--out", default="output", help="Diretório de artefatos de produção (padrão: output)")

    parser = argparse.ArgumentParser(
        prog="autoshorts",
        description="AutoShorts Aegis — CLI-Anything Autonomous Production Harness (HKUDS Spec)",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcomandos de operação")

    # status
    subparsers.add_parser("status", parents=[common], help="Verifica status da produção e do piloto automático")

    # health
    subparsers.add_parser("health", parents=[common], help="Auditoria de saúde SRE de baixo nível (RAM, portas, CPU, disco)")

    # jobs
    p_jobs = subparsers.add_parser("jobs", parents=[common], help="Gerenciamento e recuperação de jobs persistidos")
    p_jobs.add_argument("job_action", choices=["list", "recoverable"], default="list", nargs="?", help="Ação de jobs")
    p_jobs.add_argument("--limit", type=int, default=20, help="Limite de listagem (padrão: 20)")

    # audit
    p_audit = subparsers.add_parser("audit", parents=[common], help="Auditoria técnica e estética 5D de arquivo MP4")
    p_audit.add_argument("file", help="Caminho do arquivo MP4 a ser auditado")

    # omega
    p_omega = subparsers.add_parser("omega", parents=[common], help="Controle do Omega CDP Control Engine")
    omega_sub = p_omega.add_subparsers(dest="omega_action", help="Ações do Omega CDP")
    omega_sub.add_parser("status", parents=[common], help="Telemetria e status das tarefas e sessões")
    omega_sub.add_parser("capabilities", parents=[common], help="Matriz de permissões e limites de plataforma")
    omega_sub.add_parser("sessions", parents=[common], help="Perfis de sessão e estado de autenticação")
    p_tasks = omega_sub.add_parser("tasks", parents=[common], help="Gerenciamento de tarefas de publicação")
    p_tasks.add_argument("--action", default="list", choices=["list", "create", "approve", "reject", "verify"])
    p_tasks.add_argument("--task-id", default="", help="ID da tarefa")
    p_tasks.add_argument("--platform", default="youtube", help="Plataforma")
    p_tasks.add_argument("--video", default="", help="Caminho do arquivo de vídeo")
    p_tasks.add_argument("--title", default="", help="Título do vídeo")
    p_tasks.add_argument("--operator", default="operator_admin", help="Operador responsável")
    p_tasks.add_argument("--reason", default="", help="Motivo da rejeição")
    p_tasks.add_argument("--comment", default="", help="Comentário da aprovação")
    p_tasks.add_argument("--limit", type=int, default=20, help="Limite de tarefas")
    p_tasks.add_argument("--auto-approve", action="store_true", help="Pular fila de aprovação humana")

    omega_sub.add_parser("inventory", parents=[common], help="Inventário de hardware, OS, memória e catálogo de repositórios")
    p_repos = omega_sub.add_parser("repos", parents=[common], help="Gerenciador de auditoria e clonagem dos repositórios open-source")
    p_repos.add_argument("repo_action", choices=["audit", "clone", "test", "status"], default="audit", nargs="?")
    omega_sub.add_parser("integrations", parents=[common], help="Plano e estado das integrações tecnológicas")
    omega_sub.add_parser("live", parents=[common], help="Monitoramento de streamers de games e lives")
    omega_sub.add_parser("clips", parents=[common], help="Detecção de cortes multimodais em lives")
    p_foren = omega_sub.add_parser("forensics", parents=[common], help="Engenharia reversa criativa e laudo de viralidade")
    p_foren.add_argument("--video-id", default="viral_ref_01", help="ID do vídeo analisado")
    p_foren.add_argument("--title", default="O segredo da IA", help="Título do vídeo")
    p_foren.add_argument("--transcript", default="Texto da transcrição", help="Texto de fala")
    p_foren.add_argument("--duration", type=float, default=45.0, help="Duração em segundos")
    p_foren.add_argument("--niche", default="tech", help="Nicho")
    p_vid = omega_sub.add_parser("video", parents=[common], help="Diagnóstico visual profundo (blackdetect, freezedetect)")
    p_vid.add_argument("file", help="Caminho do arquivo MP4")
    p_vid.add_argument("--video-action", default="validate", choices=["validate"])
    omega_sub.add_parser("report", parents=[common], help="Gera o relatório executivo de integração")

    # studio
    p_studio = subparsers.add_parser("studio", parents=[common], help="Comandos do Atlas Studio (Design System, Quality Gates, 13 Personas)")
    studio_sub = p_studio.add_subparsers(dest="studio_action", help="Ação do Studio")
    studio_sub.add_parser("presets", parents=[common], help="Lista os presets do Design System")
    p_gates = studio_sub.add_parser("gates", parents=[common], help="Avalia os 7 Quality Gates (A-G) em um vídeo")
    p_gates.add_argument("file", help="Caminho do arquivo de vídeo MP4")
    p_gates.add_argument("--title", default="Vídeo de Teste", help="Título editorial")
    p_gates.add_argument("--niche", default="podcast", help="Nicho de conteúdo")
    p_gates.add_argument("--platform", default="youtube_shorts", help="Plataforma alvo")
    p_pipe = studio_sub.add_parser("pipeline", parents=[common], help="Executa o pipeline multiagente das 13 personas")
    p_pipe.add_argument("--niche", default="tech", help="Nicho do vídeo")
    p_pipe.add_argument("--topic", default="IA e Automação", help="Tópico central")
    p_pipe.add_argument("--job-id", default="", help="ID do job")
    p_pipe.add_argument("--operator", default="operator_admin", help="Operador responsável")

    # sentinel (Pre-Render Intelligence & Quality Gates)
    p_sentinel = subparsers.add_parser("sentinel", parents=[common], help="Auto Shorts Sentinel — Pre-Render Intelligence & Quality Gates")
    sentinel_sub = p_sentinel.add_subparsers(dest="sentinel_action", help="Ação do Sentinel")
    sentinel_sub.add_parser("status", parents=[common], help="Verifica status e relatórios recentes do Sentinel")
    p_sval = sentinel_sub.add_parser("validate", parents=[common], help="Valida roteiro, cenas, promessas e 10 Quality Gates antes de renderizar")
    p_sval.add_argument("--title", default="Vídeo Planejado", help="Título editorial candidato")
    p_sval.add_argument("--script", default="", help="Texto completo do roteiro planejado")
    p_sval.add_argument("--topic", default="Geral", help="Tópico principal")
    p_sval.add_argument("--niche", default="geral", help="Nicho do canal")
    p_sval.add_argument("--platform", default="youtube_shorts", help="Plataforma alvo")
    p_sval.add_argument("--no-auto-correct", action="store_true", help="Desabilitar auto-correção automática de títulos e legendas")

    # serve (compatibilidade web)
    p_serve = subparsers.add_parser("serve", parents=[common], help="Inicia o Web Studio Dashboard")
    p_serve.add_argument("--port", type=int, default=8787, help="Porta TCP do servidor (padrão: 8787)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.subcommand or args.subcommand == "status":
        return cmd_status(args, out_dir)
    elif args.subcommand == "health":
        return cmd_health(args, out_dir)
    elif args.subcommand == "jobs":
        return cmd_jobs(args, out_dir)
    elif args.subcommand == "audit":
        return cmd_audit(args, out_dir)
    elif args.subcommand == "omega":
        return cmd_omega(args, out_dir)
    elif args.subcommand == "studio":
        return cmd_studio(args, out_dir)
    elif args.subcommand == "sentinel":
        return cmd_sentinel(args, out_dir)
    elif args.subcommand == "serve":
        from .webapp import serve_webapp
        serve_webapp(host="0.0.0.0", port=args.port, out_dir=str(out_dir))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
