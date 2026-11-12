"""Drive Sentinel Engine: 100% Autonomous & Intelligent Anime / Multi-Clip Workflow.

Continuously watches Google Drive 5TB (gdrive:Animes_Para_Cortar), automatically ingests
new episodes, cuts 3-5 action-packed vertical shorts preserving authentic dubber audio,
uploads completed shorts to gdrive:Shorts_Finalizados, moves source episode to
gdrive:Animes_Processados without downloading heavy bytes twice, AND AUTONOMOUSLY PULLS
trending Brazilian dubbed anime scenes directly from the web when the Drive queue is empty.
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
    upload_to_rclone,
)
from .mahoraga import MahoragaEngine

logger = logging.getLogger("DriveSentinel")

AUTO_ANIME_PULL_QUERIES = [
    "jujutsu kaisen dublado cena epica brasil",
    "dragon ball z dublado melhores momentos brasil",
    "naruto shippuden dublado luta epica brasil",
    "demon slayer dublado cena epica brasil",
    "one piece dublado cena epica brasil",
    "solo leveling dublado cena brasil",
    "bleach dublado cena epica brasil",
    "hunter x hunter dublado cena epica brasil",
    "death note dublado cena tensa brasil",
]


class DriveSentinelEngine:
    def __init__(
        self,
        out_dir: str | Path = "output",
        poll_interval_sec: int = 45,
        auto_pull_interval_min: int = 45,
        num_clips_per_episode: int = 3,
        auto_pull_enabled: bool = True,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval_sec = max(15, poll_interval_sec)
        self.auto_pull_interval_min = max(10, auto_pull_interval_min)
        self.num_clips_per_episode = max(1, min(10, num_clips_per_episode))
        self.auto_pull_enabled = auto_pull_enabled
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
            "web_animes_pulled_count": 0,
            "current_task": "",
            "last_error": "",
            "active_episode": None,
            "last_auto_pull_ts": 0.0,
            "auto_pull_query_index": 0,
            "auto_pull_enabled": self.auto_pull_enabled,
        }
        self._load_state()

    def _load_state(self) -> None:
        if self._cfg_file.is_file():
            try:
                data = json.loads(self._cfg_file.read_text(encoding="utf-8"))
                with self._lock:
                    self._state.update(data)
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
        """Trigger an immediate check of Google Drive."""
        t = threading.Thread(target=self._execute_single_round, name="DriveSentinelInstantScan", daemon=True)
        t.start()
        return {"status": "scanning_triggered", "timestamp": time.time()}

    def pull_now(self) -> Dict:
        """Force an immediate automated pull of a trending anime from the web."""
        t = threading.Thread(target=self._pull_web_anime_episode, name="DriveSentinelInstantPull", daemon=True)
        t.start()
        return {"status": "pull_triggered", "timestamp": time.time()}

    def get_telemetry(self) -> Dict:
        with self._lock:
            snap = dict(self._state)
            snap["running"] = bool(self._worker_thread and self._worker_thread.is_alive())
            snap["poll_interval_sec"] = self.poll_interval_sec
            snap["auto_pull_interval_min"] = self.auto_pull_interval_min
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

        # 3. No drive episodes pending: check if we should auto-pull an anime from the web
        with self._lock:
            auto_pull_on = bool(self._state.get("auto_pull_enabled", True))
            last_pull = float(self._state.get("last_auto_pull_ts") or 0.0)
            elapsed_min = (time.time() - last_pull) / 60.0

        if auto_pull_on and elapsed_min >= self.auto_pull_interval_min:
            self._pull_web_anime_episode()
        else:
            with self._lock:
                self._state["mode"] = "idle_watching"
                remaining_min = max(0, int(self.auto_pull_interval_min - elapsed_min))
                self._state["last_action"] = f"Drive limpo (0 pendentes). Próximo anime automático em ~{remaining_min}min."
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

            try:
                MahoragaEngine(self._db_path).record_adaptation_event(
                    phenomenon="sentinel_episode_sliced",
                    spoke="Raio VIII (Autonomous Slicer)",
                    action=f"Fatiado {ep_name} em {num_generated} cortes com audio nativo dos dubladores.",
                    success=True,
                )
            except Exception:
                pass

        except Exception as exc:
            logger.exception("Failed processing episode %s: %s", ep_name, exc)
            with self._lock:
                self._state["mode"] = "episode_error"
                self._state["last_error"] = str(exc)[:220]
                self._state["last_action"] = f"Falha ao fatiar {ep_name}. Tentando adaptação..."
                self._persist_state()
            try:
                MahoragaEngine(self._db_path).record_adaptation_event(
                    phenomenon="sentinel_episode_error",
                    spoke="Raio VIII (Autonomous Slicer)",
                    action=f"Erro em {ep_name}: {str(exc)[:160]}",
                    success=False,
                )
            except Exception:
                pass

    def _pull_web_anime_episode(self) -> None:
        """Autonomously discover and pull a trending Brazilian dubbed anime from the web and slice it."""
        with self._lock:
            idx = int(self._state.get("auto_pull_query_index", 0)) % len(AUTO_ANIME_PULL_QUERIES)
            query = AUTO_ANIME_PULL_QUERIES[idx]
            self._state["auto_pull_query_index"] = idx + 1
            self._state["mode"] = "pulling_web_anime"
            self._state["current_task"] = f"Puxando automaticamente cena de anime: '{query}'..."
            self._state["last_action"] = f"Buscando anime na web: {query}"
            self._persist_state()

        from .pipeline import run_autopilot

        try:
            logger.info("DriveSentinel auto-pulling anime from web with query: %s", query)
            res = run_autopilot(
                out_dir=self.out_dir,
                platform="youtube_shorts",
                niche="entretenimento_animes",
                query=query,
                num_clips=self.num_clips_per_episode,
                layout="blur_bg",
                quality="mobile",
                use_llm=True,
                auto_layout=True,
                playlist_name="Animes e Batalhas Épicas - Shorts",
                auto_publish=True,
            )

            num_clips = len(res.get("clips") or [])
            with self._lock:
                self._state["last_auto_pull_ts"] = time.time()
                self._state["web_animes_pulled_count"] = int(self._state.get("web_animes_pulled_count", 0)) + 1
                self._state["mode"] = "web_anime_done"
                self._state["last_action"] = f"Puxado com sucesso! {num_clips} cortes gerados de '{query}' e salvos no Drive 5TB."
                self._state["last_error"] = ""
                self._persist_state()

            try:
                MahoragaEngine(self._db_path).record_adaptation_event(
                    phenomenon="sentinel_web_anime_pulled",
                    spoke="Raio VIII (Autonomous Slicer)",
                    action=f"Anime puxado automaticamente da web ('{query}'): {num_clips} cortes salvos.",
                    success=True,
                )
            except Exception:
                pass

        except Exception as exc:
            logger.exception("Failed auto-pulling anime for query %s: %s", query, exc)
            with self._lock:
                self._state["mode"] = "pull_error"
                self._state["last_error"] = str(exc)[:200]
                self._state["last_action"] = f"Falha ao puxar da web. Próxima tentativa em {self.poll_interval_sec}s."
                self._persist_state()
