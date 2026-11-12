"""Drive Sentinel Engine: 100% Autonomous & Intelligent Anime / Multi-Clip Workflow.

Continuously watches Google Drive 5TB (gdrive:Animes_Para_Cortar), automatically ingests
new episodes, cuts 3-5 action-packed vertical shorts preserving authentic dubber audio,
uploads completed shorts to gdrive:Shorts_Finalizados, moves source episode to
gdrive:Animes_Processados without downloading heavy bytes twice, and falls back to
autonomous viral trend cycles when the drive queue is clear.
"""

import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from .downloader import (
    list_gdrive_episodes,
    move_gdrive_episode,
    refresh_gdrive_token,
)
from .mahoraga import MahoragaEngine

logger = logging.getLogger("DriveSentinel")


class DriveSentinelEngine:
    def __init__(
        self,
        out_dir: str | Path = "output",
        poll_interval_sec: int = 45,
        autonomous_fallback_hours: int = 3,
        num_clips_per_episode: int = 3,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval_sec = max(15, poll_interval_sec)
        self.autonomous_fallback_hours = max(1, autonomous_fallback_hours)
        self.num_clips_per_episode = max(1, min(10, num_clips_per_episode))
        self._db_path = self.out_dir / "shorts_evolution.db"
        self._cfg_file = self.out_dir / "sentinel_state.json"
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        self._state: Dict = {
            "enabled": True,
            "running": False,
            "mode": "idle",
            "last_check_ts": 0.0,
            "last_action": "Sentinela inicializado",
            "episodes_processed_count": 0,
            "current_task": "",
            "last_error": "",
            "active_episode": None,
            "last_autonomous_cycle_ts": 0.0,
        }
        self._load_state()

    def _load_state(self) -> None:
        if self._cfg_file.is_file():
            try:
                data = json.loads(self._cfg_file.read_text(encoding="utf-8"))
                with self._lock:
                    self._state.update(data)
                    # Reset dynamic execution flags
                    self._state["running"] = False
                    self._state["active_episode"] = None
            except Exception:
                pass

    def _persist_state(self) -> None:
        with self._lock:
            snap = dict(self._state)
            snap["running"] = bool(self._worker_thread and self._worker_thread.is_alive())
        try:
            self._cfg_file.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def is_active(self) -> bool:
        with self._lock:
            return bool(self._state.get("enabled", True) and self._worker_thread and self._worker_thread.is_alive())

    def start(self) -> bool:
        with self._lock:
            self._state["enabled"] = True
            if self._worker_thread and self._worker_thread.is_alive():
                return True
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._run_loop, name="DriveSentinelWorker", daemon=True)
            self._worker_thread.start()
            self._state["last_action"] = "Sentinela iniciado em segundo plano"
            self._persist_state()
            return True

    def stop(self) -> bool:
        with self._lock:
            self._state["enabled"] = False
            self._state["mode"] = "stopped"
            self._state["last_action"] = "Sentinela pausado pelo operador"
            self._stop_event.set()
            self._persist_state()
            return True

    def scan_now(self) -> Dict:
        """Trigger an immediate check outside the scheduled sleep."""
        t = threading.Thread(target=self._execute_single_round, name="DriveSentinelInstantScan", daemon=True)
        t.start()
        return {"status": "scanning_triggered", "timestamp": time.time()}

    def get_telemetry(self) -> Dict:
        with self._lock:
            snap = dict(self._state)
            snap["running"] = bool(self._worker_thread and self._worker_thread.is_alive())
            snap["poll_interval_sec"] = self.poll_interval_sec
            snap["num_clips_per_episode"] = self.num_clips_per_episode
            return snap

    def _run_loop(self) -> None:
        logger.info("DriveSentinel daemon loop started.")
        while not self._stop_event.is_set():
            try:
                self._execute_single_round()
            except Exception as exc:
                with self._lock:
                    self._state["last_error"] = str(exc)
                    self._state["mode"] = "error_backoff"
                logger.exception("Error in sentinel loop iteration: %s", exc)

            # Sleep in 1-second chunks for responsive thread termination
            for _ in range(self.poll_interval_sec):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _execute_single_round(self) -> None:
        if self._stop_event.is_set():
            return

        with self._lock:
            self._state["last_check_ts"] = time.time()
            self._state["mode"] = "checking_gdrive"

        # 1. Google Drive Token Auto-Refresh
        try:
            refresh_gdrive_token()
        except Exception:
            pass

        # 2. Check pending episodes in Google Drive
        pending_episodes: List[str] = []
        try:
            pending_episodes = list_gdrive_episodes("gdrive:Animes_Para_Cortar")
        except Exception as exc:
            with self._lock:
                self._state["last_error"] = f"Erro listando Drive: {exc}"

        if pending_episodes:
            target_ep = pending_episodes[0]
            self._process_drive_episode(target_ep)
            return

        # 3. No drive episodes pending: check autonomous trend cycle fallback
        with self._lock:
            last_auto = float(self._state.get("last_autonomous_cycle_ts") or 0.0)
            elapsed_hours = (time.time() - last_auto) / 3600.0

        if elapsed_hours >= self.autonomous_fallback_hours:
            self._trigger_autonomous_fallback()
        else:
            with self._lock:
                self._state["mode"] = "idle_watching"
                self._state["last_action"] = f"Drive limpo (0 pendentes). Monitorando a cada {self.poll_interval_sec}s."
                self._state["active_episode"] = None
                self._persist_state()

    def _process_drive_episode(self, episode_remote_path: str) -> None:
        """Fully automated slice -> burn ASS -> backup to Shorts_Finalizados -> move to Animes_Processados."""
        ep_name = Path(episode_remote_path).name
        clean_title = Path(ep_name).stem.replace("_", " ").title()

        with self._lock:
            self._state["mode"] = "processing_episode"
            self._state["active_episode"] = ep_name
            self._state["current_task"] = f"Fatiando clímax épicos de {clean_title}..."
            self._state["last_action"] = f"Processando: {clean_title}"
            self._persist_state()

        from .pipeline import run_pipeline

        try:
            logger.info("DriveSentinel starting automated multi-slice on %s", episode_remote_path)
            res = run_pipeline(
                source=episode_remote_path,
                out_dir=self.out_dir,
                platform="youtube_shorts",
                niche="entretenimento_animes",
                num_clips=self.num_clips_per_episode,
                layout="blur_bg",
                quality="mobile",
                use_llm=True,
                auto_layout=True,
                file_prefix=f"anime_{Path(ep_name).stem[:16]}",
                playlist_name="Animes e Batalhas Épicas - Shorts",
                auto_publish=True,
            )

            # Move processed source episode to gdrive:Animes_Processados/ so it never duplicates
            move_gdrive_episode(episode_remote_path, "gdrive:Animes_Processados")

            with self._lock:
                self._state["episodes_processed_count"] = int(self._state.get("episodes_processed_count", 0)) + 1
                self._state["mode"] = "episode_completed"
                num_generated = len(res.get("clips") or [])
                self._state["last_action"] = f"Sucesso! {num_generated} cortes de {clean_title} salvos em Shorts_Finalizados."
                self._state["active_episode"] = None
                self._state["last_error"] = ""
                self._persist_state()

            # Record in Mahoraga
            MahoragaEngine(self._db_path).record_adaptation_event(
                phenomenon="sentinel_episode_sliced",
                spoke="Raio VIII (Autonomous Slicer)",
                action=f"Fatiado {ep_name} em {num_generated} cortes com audio nativo dos dubladores.",
                success=True,
            )

        except Exception as exc:
            logger.exception("Failed processing episode %s: %s", ep_name, exc)
            with self._lock:
                self._state["mode"] = "episode_error"
                self._state["last_error"] = str(exc)[:220]
                self._state["last_action"] = f"Falha ao fatiar {ep_name}. Tentando adaptação..."
                self._persist_state()
            MahoragaEngine(self._db_path).record_adaptation_event(
                phenomenon="sentinel_episode_error",
                spoke="Raio VIII (Autonomous Slicer)",
                action=f"Erro em {ep_name}: {str(exc)[:160]}",
                success=False,
            )

    def _trigger_autonomous_fallback(self) -> None:
        """When Google Drive has no pending anime episodes, autonomously create viral news/trends shorts."""
        with self._lock:
            self._state["mode"] = "autonomous_cycle"
            self._state["current_task"] = "Gerando Short de Notícias / Radar de Animes..."
            self._persist_state()

        from .world_news import produce_world_news_short

        try:
            fb = produce_world_news_short(
                out_dir=self.out_dir,
                topic="world",
                auto_publish=True,
                use_llm=True,
            )
            # Backup to Google Drive Shorts_Finalizados
            from .downloader import upload_to_rclone
            out_file = fb.get("output")
            if out_file and Path(out_file).is_file():
                upload_to_rclone(Path(out_file), "gdrive:Shorts_Finalizados")

            with self._lock:
                self._state["last_autonomous_cycle_ts"] = time.time()
                self._state["mode"] = "autonomous_cycle_done"
                self._state["last_action"] = f"Ciclo de tendências concluído: {fb.get('title', '')[:50]}"
                self._persist_state()

        except Exception as exc:
            logger.exception("Autonomous trend cycle fallback failed: %s", exc)
            with self._lock:
                self._state["last_error"] = str(exc)[:200]
                self._persist_state()
