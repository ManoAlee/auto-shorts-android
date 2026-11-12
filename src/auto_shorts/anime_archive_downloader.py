"""Automated scraper and downloader for full Brazilian dubbed anime episodes.

Integrates:
1. Internet Archive (Archive.org) Anime Collections (direct zero-auth MP4s)
2. AnimesDigital (animesdigital.org) API & HLS direct streams
3. Direct download & auto-slicing into vertical shorts
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("AnimeArchiveDownloader")


def search_archive_org_animes(query: str, limit: int = 6) -> List[Dict]:
    """Search Archive.org for full anime collections and episodes dubbed in Brazilian Portuguese."""
    clean_q = re.sub(r"[^\w\s]", " ", query).strip()
    encoded = urllib.parse.quote(f"{clean_q} dublado mediatype:movies")
    url = f"https://archive.org/advancedsearch.php?q={encoded}&fl[]=identifier,title,description,downloads&sort[]=downloads+desc&rows={limit}&output=json"

    items: List[Dict] = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                ident = doc.get("identifier")
                title = doc.get("title") or ident
                if not ident:
                    continue
                items.append({
                    "id": ident,
                    "title": str(title).strip(),
                    "source": "archive.org",
                    "details_url": f"https://archive.org/details/{ident}",
                })
    except Exception as exc:
        logger.warning("Error querying Archive.org: %s", exc)
    return items


def list_archive_org_episode_files(identifier: str) -> List[Dict]:
    """List direct downloadable MP4 episode files inside an Archive.org collection."""
    meta_url = f"https://archive.org/metadata/{identifier}/files"
    episodes: List[Dict] = []
    try:
        req = urllib.request.Request(meta_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            files = data.get("result", [])
            for f in files:
                fname = f.get("name", "")
                if fname.lower().endswith(".mp4") and not fname.startswith(("_", ".")):
                    size_bytes = int(f.get("size") or 0)
                    size_mb = round(size_bytes / (1024 * 1024), 1)
                    # Don't list tiny samples (<15MB)
                    if size_bytes > 15 * 1024 * 1024:
                        dl_url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(fname)}"
                        episodes.append({
                            "filename": fname,
                            "title": Path(fname).stem.replace("_", " "),
                            "url": dl_url,
                            "size_mb": size_mb,
                            "source": "archive.org",
                        })
    except Exception as exc:
        logger.warning("Error listing Archive.org files for %s: %s", identifier, exc)
    return episodes


def search_animesdigital_episodes(query: str, limit: int = 5) -> List[Dict]:
    """Search animesdigital.org for Brazilian dubbed animes and direct stream links."""
    clean_q = "+".join(query.strip().split())
    search_url = f"https://animesdigital.org/?s={clean_q}"
    results: List[Dict] = []
    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://animesdigital.org/",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Extract anime page URLs
        anime_matches = re.findall(r'<a[^>]+href="(https://animesdigital\.org/anime/[^"]+)"[^>]*title="([^"]*)"', html)
        for link, title in anime_matches[:limit]:
            clean_title = title.replace("Assistir", "").replace("Online", "").strip()
            results.append({
                "title": clean_title,
                "url": link,
                "size_mb": 0.0,
                "source": "animesdigital",
            })
    except Exception as exc:
        logger.warning("Error querying AnimesDigital: %s", exc)
    return results


def search_all_anime_sources(query: str) -> List[Dict]:
    """Unified search across Archive.org and Brazilian anime repositories."""
    all_results: List[Dict] = []
    arch_items = search_archive_org_animes(query, limit=5)
    for it in arch_items:
        ep_files = list_archive_org_episode_files(it["id"])
        if ep_files:
            all_results.extend(ep_files[:4])
        else:
            all_results.append(it)

    ad_items = search_animesdigital_episodes(query, limit=3)
    all_results.extend(ad_items)
    return all_results


def download_episode_direct(
    url: str,
    dest_path: Path,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Download an episode MP4 with streaming chunks directly to disk."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".part")

    logger.info("Downloading full episode from %s to %s", url, dest_path)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "wb") as f:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)

    temp_path.rename(dest_path)
    logger.info("Download completed successfully: %s (%d MB)", dest_path, dest_path.stat().st_size // (1024 * 1024))
    return dest_path

