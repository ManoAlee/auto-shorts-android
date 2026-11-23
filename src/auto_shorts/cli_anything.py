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
    elif args.subcommand == "serve":
        from .webapp import serve_webapp
        serve_webapp(host="0.0.0.0", port=args.port, out_dir=str(out_dir))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
