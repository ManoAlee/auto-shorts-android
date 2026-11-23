#!/usr/bin/env python3
"""Retroactive Title Healing & Anti-Repetition Engine.

Inspects all video metadata sidecars (*.publish.json) in the vault and repairs:
1. Formulaic streamer live cuts: "GTA 6 Ao Vivo: Gaules (Parte 1) | Gameplay #Shorts"
   -> Context-specific viral curiosity titles based on streamer & segment transcript.
2. Generic Reddit / nosleep stories: "Histórias Bizarras e Assustadoras do Reddit (r/nosleep) (Parte 10)"
   -> Saliency-extracted mystery headlines ("A Coisa Que Sorriu na Floresta | Relatos do Reddit").
3. Category-mismatched news:
   - Biology / frog discovery labeled as "Plantão Economia" -> "Ciência & Natureza"
   - Sports / tennis (Carlos Alcaraz) labeled as "Plantão Tech" -> "Plantão Esportes"
4. Preserves backward compatibility and writes directly to *.publish.json and shorts_evolution.db.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to sys.path so auto_shorts can be imported cleanly
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from auto_shorts.viral_titling import generate_smart_clip_title, detect_accurate_category
from auto_shorts.viral_intelligence import AntiSlopHumanizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HealVaultTitles")


def _extract_text_from_ass_or_srt(ass_or_srt_path: Path) -> str:
    """Extract spoken dialogue lines from subtitle sidecar."""
    if not ass_or_srt_path.is_file():
        return ""
    try:
        content = ass_or_srt_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    # Parse ASS Dialogue lines
    lines = []
    for line in content.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) >= 10:
                raw_text = parts[9]
                clean = re.sub(r"\{.*?\}", "", raw_text).strip()
                clean = clean.replace(r"\N", " ").replace(r"\n", " ")
                if clean:
                    lines.append(clean)
        elif line.strip() and not line.strip().isdigit() and "-->" not in line and not line.startswith("["):
            lines.append(line.strip())
    return " ".join(lines)


def _detect_streamer_from_name(name: str) -> str:
    """Identify streamer from video stem or title."""
    low = name.lower()
    if "gaules" in low:
        return "Gaules"
    if "lipao" in low or "lipaogamer" in low:
        return "LipaoGamer"
    if "davy" in low or "davyjones" in low:
        return "Davy Jones"
    if "xqc" in low:
        return "xQc"
    if "alanzoka" in low:
        return "Alanzoka"
    if "coringa" in low:
        return "Coringa"
    if "nobru" in low:
        return "Nobru"
    if "cerol" in low:
        return "Cerol"
    if "casimiro" in low or "caze" in low:
        return "Casimiro"
    return ""


def _detect_part_number(stem: str, title: str) -> int:
    """Extract part number from filename suffix (_p01) or title ((Parte N))."""
    m_file = re.search(r"_p(\d+)", stem)
    if m_file:
        return int(m_file.group(1))
    m_title = re.search(r"\(Parte\s+(\d+)\)", title, flags=re.I)
    if m_title:
        return int(m_title.group(1))
    return 1


def is_title_problematic(title: str, caption: str = "", filename: str = "") -> bool:
    """Determine whether a title is simplistic, repetitive, or mismatched."""
    t_low = title.lower()
    c_low = caption.lower()
    f_low = filename.lower()
    
    # 1. Repetitive streamer live cuts
    if "gta 6 ao vivo:" in t_low or "reage ao gta 6" in t_low:
        return True
    
    # 2. Formulaic Reddit / nosleep stories with part numbers
    if "histórias bizarras e assustadoras do reddit" in t_low or "r/nosleep" in t_low:
        return True

    # 3. Category mismatch in news
    if "plantão economia" in t_low:
        if any(w in t_low or w in c_low for w in ("perereca", "sapo", "especie", "espécie", "descoberta", "biologia", "animal", "fauna")):
            return True
    if "plantão tech" in t_low or "mundo hoje" in t_low:
        if any(w in t_low or w in c_low for w in ("alcaraz", "zverev", "tenista", "atp", "futebol", "neymar", "flamengo")):
            return True

    # 4. Bare filename or empty
    if not title or title.strip() == filename.replace(".mp4", "") or title.startswith("short_live_"):
        return True

    # 5. Generic (Parte N) suffix on general titles
    if re.search(r"\(Parte\s+\d+\)\s*\|\s*Gameplay\s*#Shorts", title, flags=re.I):
        return True

    return False


def heal_single_pack(
    json_path: Path,
    dry_run: bool = False,
) -> Optional[Tuple[str, str]]:
    """Heal a single JSON publish pack. Returns (old_title, new_title) if healed, else None."""
    try:
        pack = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    old_title = str(pack.get("title") or "").strip()
    caption = str(pack.get("caption") or "")
    filename = json_path.name.replace(".publish.json", ".mp4")

    if not is_title_problematic(old_title, caption=caption, filename=filename):
        return None

    # Gather spoken transcript
    clip_text = (
        pack.get("script")
        or pack.get("body_text")
        or pack.get("clip_summary")
        or ""
    )
    if not clip_text or len(clip_text) < 40:
        # Try finding subtitle file alongside mp4
        mp4_path = json_path.parent / filename
        sub_cands = [
            json_path.parent / f"_narrate_{mp4_path.stem}" / f"{mp4_path.stem}.ass",
            json_path.parent / f"{mp4_path.stem}.ass",
            json_path.parent / f"{mp4_path.stem}.srt",
        ]
        for sc in sub_cands:
            sub_text = _extract_text_from_ass_or_srt(sc)
            if sub_text:
                clip_text = sub_text
                break

    if not clip_text and caption:
        clip_text = caption

    streamer = _detect_streamer_from_name(filename) or _detect_streamer_from_name(old_title)
    part_num = _detect_part_number(filename, old_title)
    niche = str(pack.get("niche") or "geral")

    new_title = generate_smart_clip_title(
        clip_text=clip_text,
        source_title=old_title,
        streamer_or_speaker=streamer,
        niche=niche,
        part_num=part_num,
        current_title=old_title,
    )

    if not new_title or new_title == old_title:
        return None

    if not dry_run:
        pack["title"] = new_title
        pack["youtube_title"] = new_title
        pack["hook_title"] = new_title.split("|")[0].split("—")[0].strip()[:42]
        
        # Update caption replacing old title header
        if old_title and old_title in caption:
            pack["caption"] = caption.replace(old_title, new_title)
        elif new_title not in caption:
            pack["caption"] = f"{new_title}\n\n{caption}".strip()

        # Update cross-platform title if present
        if isinstance(pack.get("multi_platform"), dict):
            for plat_key in ("youtube_shorts", "tiktok", "instagram_reels"):
                if plat_key in pack["multi_platform"]:
                    pack["multi_platform"][plat_key]["title"] = new_title

        # Persist safely
        json_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")

    return old_title, new_title


def update_db_titles(db_path: Path, changes: List[Tuple[str, str, str]]) -> int:
    """Update titles in shorts_evolution.db if present."""
    if not db_path.is_file():
        return 0
    updated = 0
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clip_runs'")
        if cur.fetchone():
            for filename, old_t, new_t in changes:
                cur.execute(
                    "UPDATE clip_runs SET hook_title = ? WHERE output_path LIKE ? OR hook_title = ?",
                    (new_t[:42], f"%{filename}%", old_t[:42]),
                )
                if cur.rowcount > 0:
                    updated += cur.rowcount
            conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Could not update SQLite db %s: %s", db_path, exc)
    return updated


def heal_vault(vault_dir: Path, dry_run: bool = False) -> int:
    """Scan directory and heal all problematic titles."""
    if not vault_dir.is_dir():
        logger.error("Vault directory does not exist: %s", vault_dir)
        return 0

    json_files = list(vault_dir.glob("*.publish.json"))
    logger.info("Found %d publish pack files in %s", len(json_files), vault_dir)

    healed_records: List[Tuple[str, str, str]] = []  # (filename, old, new)
    for jf in json_files:
        res = heal_single_pack(jf, dry_run=dry_run)
        if res:
            old_t, new_t = res
            mp4_name = jf.name.replace(".publish.json", ".mp4")
            healed_records.append((mp4_name, old_t, new_t))
            logger.info("HEALED [%s]:\n  OLD: %s\n  NEW: %s", mp4_name, old_t, new_t)

    logger.info("Summary: %d / %d titles healed successfully.", len(healed_records), len(json_files))

    db_path = vault_dir / "shorts_evolution.db"
    if not dry_run and healed_records:
        db_updates = update_db_titles(db_path, healed_records)
        if db_updates > 0:
            logger.info("Updated %d entries in SQLite db (%s)", db_updates, db_path)

    return len(healed_records)


def main():
    parser = argparse.ArgumentParser(description="Heal repetitive, simplistic, or mismatched titles in AutoShorts vault.")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="output",
        help="Path to output vault directory containing *.publish.json sidecars",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and report without overwriting files",
    )
    args = parser.parse_args()

    target_dir = Path(args.output_dir)
    count = heal_vault(target_dir, dry_run=args.dry_run)
    print(f"\nDone! Healed {count} titles.")


if __name__ == "__main__":
    main()
