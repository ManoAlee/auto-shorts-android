#!/usr/bin/env python3
"""Retroactive Title Healing & Anti-Repetition Engine.

Inspects all video metadata sidecars (*.publish.json) in the vault and repairs:
1. Streamer templates falsely applied to non-gamers (Anime, Business, Podcasts, Tutorials):
   - "A reação inacreditável do Escanor Animes ao vivo! #Shorts" -> "Entrada Épica de Netero e Zeno vs Pitou | Hunter x Hunter #Shorts"
   - "Negócios em Mente descobriu esse segredo ao vivo! #Shorts" -> "As 4 Ferramentas e a Fórmula Secreta de Agentes de IA #Shorts"
   - "O Maior Caos do Jhonatas Silva no GTA 6! #Shorts" -> "Como Criar 200 Cortes com 1 Clique Usando Opus Clip #Shorts"
   - "Irmãos Dias Podcast perdeu o controle nessa hora! #Shorts" -> "Como Ultrapassei Todos no Marketing Digital em 1 Ano | Irmãos Dias Podcast #Shorts"
   - "Esse foi o momento mais insano do Jhonny Salazar Olivera! #Shorts" -> "Naruto vs Sasuke Dublado: O Confronto Final Decisivo! #Shorts"
2. Category-mismatched news:
   - São Paulo severe rain labeled as "Plantão Esportes" -> "Chuvas em São Paulo Fazem Cidade Entrar em Estado de Alerta | Mundo Hoje"
   - Microsoft / Outlook email outage labeled as "Ciência & Natureza" -> "Microsoft Admite: E-mails Não Foram Entregues Após Apagão | Plantão Tech"
   - Biology / frog discovery labeled as "Plantão Economia" -> "Ciência & Natureza"
   - Sports / tennis (Carlos Alcaraz) labeled as "Plantão Tech" -> "Plantão Esportes"
3. Formulaic streamer live cuts & generic Reddit / nosleep stories with part numbers.
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

from auto_shorts.viral_titling import (
    generate_smart_clip_title,
    detect_accurate_category,
    VERIFIED_GAMING_STREAMERS,
    _clean_alnum_text,
)
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
    """Identify streamer ONLY if matching verified gaming streamers."""
    low = name.lower()
    for s in VERIFIED_GAMING_STREAMERS:
        if s in low:
            if s in ("lipao", "lipaogamer"):
                return "LipaoGamer"
            if s in ("davy", "davy jones", "davyjones"):
                return "Davy Jones"
            if s == "xqc":
                return "xQc"
            if s == "casimiro" or s == "caze":
                return "Casimiro"
            return s.capitalize()
    return ""


def _detect_part_number(stem: str, title: str) -> int:
    """Extract part number from filename suffix (_p01, _short_02) or title ((Parte N))."""
    m_file = re.search(r"_(?:p|short_)0*(\d+)", stem)
    if m_file:
        return int(m_file.group(1))
    m_title = re.search(r"\(Parte\s+(\d+)\)", title, flags=re.I)
    if m_title:
        return int(m_title.group(1))
    return 1


def is_title_problematic(title: str, caption: str = "", filename: str = "") -> bool:
    """Determine whether a title is simplistic, repetitive, clickbait-hijacked, or mismatched."""
    t_low = title.lower()
    c_low = caption.lower()
    f_low = filename.lower()
    
    # 1. Repetitive streamer live cuts formula
    if "gta 6 ao vivo:" in t_low or "reage ao gta 6" in t_low:
        return True
    
    # 2. Formulaic Reddit / nosleep stories with part numbers
    if "histórias bizarras e assustadoras do reddit" in t_low or "r/nosleep" in t_low:
        return True

    # 3. Streamer clickbait falsely applied to non-gamers (Anime, Business, Podcasts, Tutorials)
    clickbait_templates = (
        "descobriu esse segredo ao vivo",
        "perdeu o controle nessa hora",
        "a reação inacreditável do",
        "o momento exato em que",
        "ficou em choque total",
        "nem o",
        "quase não acreditou no que viu",
        "esse foi o momento mais insano do",
    )
    for cb in clickbait_templates:
        if cb in t_low:
            # Check if uploader/channel in title is NOT a verified gamer
            is_real_gamer = any(g in t_low for g in VERIFIED_GAMING_STREAMERS)
            if not is_real_gamer:
                return True

    # 4. Erroneously claims "no GTA 6!" when the content is not GTA 6
    body_caption = c_low.replace(t_low, "")
    if "gta 6" in t_low or "gta" in t_low:
        if any(w in body_caption for w in ("opus clip", "marçal", "marcal", "monetizar", "marketing digital", "agente", "podcast")):
            return True
        if not any(w in body_caption for w in ("rockstar", "gta vi", "gta 6", "vice city", "lucia", "jason", "trevor", "michael", "franklin")):
            if not any(g in t_low for g in VERIFIED_GAMING_STREAMERS):
                return True

    # 5. Category mismatch in news
    if "plantão esportes" in t_low:
        if any(w in t_low or w in c_low for w in (
            "chuva", "chuvas", "temporal", "alagamento", "inundação", "enchente",
            "defesa civil", "regula", "orgao regulador", "órgão regulador",
            "concessionaria", "prefeitura", "governo", "governador", "tarifa"
        )):
            return True
        sports_terms = ("futebol", "gol", "gols", "campeonato", "brasileirao", "tenis", "atp", "flamengo", "palmeiras", "corinthians", "sao paulo fc", "vasco", "gremio", "cruzeiro", "santos fc", "zverev", "alcaraz")
        if not any(w in t_low or w in c_low for w in sports_terms):
            return True
    if "ciência & natureza" in t_low:
        if any(w in t_low or w in c_low for w in ("microsoft", "outlook", "exchange", "email", "e-mail", "apagão", "apagao", "servidor")):
            return True
    if "plantão economia" in t_low:
        if any(w in t_low or w in c_low for w in ("perereca", "sapo", "especie", "espécie", "descoberta", "biologia", "animal", "fauna")):
            return True
    if "plantão tech" in t_low or "mundo hoje" in t_low:
        if any(w in t_low or w in c_low for w in ("alcaraz", "zverev", "tenista", "atp", "futebol", "neymar", "flamengo")):
            return True

    # 6. Bare filename or empty or truncated
    if not title or title.strip() == filename.replace(".mp4", "") or title.startswith("short_live_"):
        return True

    # 7. Generic (Parte N) suffix on general titles
    if re.search(r"\(Parte\s+\d+\)\s*\|\s*Gameplay\s*#Shorts", title, flags=re.I):
        return True

    return False


def _extract_source_info_from_caption(caption: str) -> Tuple[str, str, str]:
    """Extract (source_title, uploader_channel, spoken_text) from caption text."""
    source_title = ""
    channel = ""
    spoken_text = ""

    # 1. Fonte / Referencia line
    m_fonte = re.search(r"Fonte\s*/\s*Referencia:\s*\n([^\n]+)", caption, flags=re.I)
    if m_fonte:
        ref_line = m_fonte.group(1).strip()
        if " - " in ref_line:
            parts = ref_line.split(" - ", 1)
            channel = parts[0].strip()
            source_title = parts[1].strip()
        else:
            source_title = ref_line

    # 2. Fonte original with URL slug
    m_orig = re.search(r"Fonte original.*?\((.*?)\):\s*https?://[^\s/]+/([^/\s]+)/([^\s/]+)", caption, flags=re.I)
    if m_orig:
        slug = m_orig.group(3).strip().replace("-", " ")
        if not source_title or len(source_title) < 15:
            source_title = slug

    # 3. Destaque line
    m_destaque = re.search(r"Destaque:\s*([^\n]+)", caption, flags=re.I)
    if m_destaque:
        dest = m_destaque.group(1).strip()
        if not source_title:
            source_title = dest

    # 4. Spoken text / summary
    m_sobre = re.search(r"Sobre este corte:\s*\n(.*?)(?:\n\nFonte|\Z)", caption, flags=re.I | re.DOTALL)
    if m_sobre:
        spoken_text = m_sobre.group(1).strip()
    else:
        m_resumo = re.search(r"Resumo da noticia.*:\s*\n(.*?)(?:\n\nFonte|\Z)", caption, flags=re.I | re.DOTALL)
        if m_resumo:
            spoken_text = m_resumo.group(1).strip()

    return source_title, channel, spoken_text


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

    # Extract real context from caption and sidecars
    cap_src_title, cap_channel, cap_speech = _extract_source_info_from_caption(caption)

    # Gather spoken transcript
    clip_text = (
        pack.get("script")
        or pack.get("body_text")
        or pack.get("clip_summary")
        or cap_speech
        or ""
    )
    if not clip_text or len(clip_text) < 40:
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

    source_title = pack.get("source_title") or cap_src_title or old_title
    streamer = _detect_streamer_from_name(cap_channel) or _detect_streamer_from_name(filename) or _detect_streamer_from_name(old_title)
    part_num = _detect_part_number(filename, old_title)
    niche = str(pack.get("niche") or "geral")

    # If niche was misclassified as games_gta6 for tutorial
    if "opus clip" in caption.lower() or "como criar 200 cortes" in caption.lower() or "ai agents" in caption.lower():
        niche = "ia_tech"

    new_title = generate_smart_clip_title(
        clip_text=clip_text,
        source_title=source_title,
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
        pack["niche"] = niche
        pack["hook_title"] = new_title.split("|")[0].split("—")[0].strip()[:42]
        
        # Update caption replacing old title header
        new_caption = caption
        if old_title and old_title in new_caption:
            new_caption = new_caption.replace(old_title, new_title)
        elif new_title not in new_caption:
            new_caption = f"{new_title}\n\n{new_caption}".strip()

        # Fix category mismatch in caption footers and hashtags
        if "mundo_br_20261123_043904" in filename or "chuvas em são paulo" in old_title.lower():
            pack["niche"] = "noticias_mundiais"
            new_caption = new_caption.replace("O que você achou dessa conquista? Deixe seu comentário e siga o canal para novidades do esporte!", "Fique atento aos alertas da Defesa Civil e compartilhe para avisar mais pessoas!")
            new_caption = re.sub(r"#Esportes\s+#Futebol\s+#Tenis\s+#EsporteBrasil", "#Mundo #Brasil #SaoPaulo #Clima #Alerta #Chuva", new_caption)

        if "mundo_br_20261123_130740" in filename or "microsoft admite" in old_title.lower():
            pack["niche"] = "tech_ia"
            new_caption = new_caption.replace("Curtiu essa descoberta? Deixe seu like e siga o canal para mais fatos fascinantes da ciência!", "Seu e-mail também foi afetado pela instabilidade da Microsoft? Deixe sua experiência nos comentários!")
            new_caption = re.sub(r"#Ciencia\s+#Natureza\s+#Descobertas\s+#Biologia\s+#Curiosidades", "#Microsoft #Outlook #Exchange #Tecnologia #Tech #NoticiasTech", new_caption)

        if "3usldBhhO5c" in filename:
            pack["niche"] = "ia_tech"

        pack["caption"] = new_caption

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
