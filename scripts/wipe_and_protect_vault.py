#!/usr/bin/env python3
"""Wipe all old/defective videos and protect Android Gallery with .nomedia."""

import glob
import os
import shutil
import sqlite3
import sys
from pathlib import Path

def wipe_vault(vault_dir: Path, shared_movies_dir: Path = None):
    print(f"[*] Wiping vault directory: {vault_dir}")
    removed_files = 0
    removed_bytes = 0

    if vault_dir.is_dir():
        # Remove all video and metadata artifacts
        patterns = [
            "*.mp4", "*.publish.json", "*.jpg", "*.png", "*.ass", "*.srt",
            "*.raw_chunk", "*.tmp", "*.part", "*.ytdl", "*.part-Frag*",
            "live_*.raw.mp4*", "_work_live_*"
        ]
        for pat in patterns:
            for f in vault_dir.glob(pat):
                try:
                    removed_bytes += f.stat().st_size
                    f.unlink(missing_ok=True)
                    removed_files += 1
                except OSError:
                    pass

        # Remove temporary directories
        for d in vault_dir.glob("_*"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

        # Place .nomedia to protect Android Gallery
        nomedia = vault_dir / ".nomedia"
        nomedia.touch(exist_ok=True)
        print(f"[+] Placed .nomedia in {vault_dir}")

        # Clean SQLite tables so past duplicate titles don't block fresh runs
        db_path = vault_dir / "shorts_evolution.db"
        if db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("DELETE FROM clip_runs")
                conn.execute("DELETE FROM clip_metrics")
                conn.execute("DELETE FROM processed_sources")
                conn.commit()
                conn.close()
                print(f"[+] Reset clip_runs and processed_sources in {db_path.name}")
            except Exception as e:
                print(f"[-] SQLite reset error: {e}")

    if shared_movies_dir and shared_movies_dir.is_dir():
        print(f"[*] Cleaning shared movies dir: {shared_movies_dir}")
        for mp4 in shared_movies_dir.glob("*.mp4"):
            try:
                mp4.unlink(missing_ok=True)
                removed_files += 1
            except OSError:
                pass
        shared_nomedia = shared_movies_dir / ".nomedia"
        shared_nomedia.touch(exist_ok=True)
        print(f"[+] Placed .nomedia in {shared_movies_dir}")

    print(f"[✓] Successfully wiped {removed_files} files ({removed_bytes / (1024*1024):.2f} MB).")
    print(f"[✓] Gallery shield active (.nomedia).")

if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    vault = Path(sys.argv[1]) if len(sys.argv) > 1 else (base / "output")
    shared = Path.home() / "storage" / "shared" / "Movies" / "AutoShorts"
    if not shared.exists():
        shared = None
    wipe_vault(vault, shared)
