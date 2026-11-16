"""Bridge to Tencent BrowserSkill (`bsk`) running on Termux/Linux/Windows for JS-rendered scraping & viral radar."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Dict, List


def is_bsk_ready(timeout: float = 2.5) -> bool:
    """Return True if `bsk` CLI is installed and at least 1 Chromium extension browser is connected."""
    if not shutil.which("bsk"):
        return False
    try:
        proc = subprocess.run(
            ["bsk", "status"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            return False
        m = re.search(r"browsers connected\s+(\d+)", proc.stdout or "", re.I)
        return bool(m and int(m.group(1)) >= 1)
    except Exception:
        return False


def bsk_fetch_rendered_html(url: str, timeout: float = 18.0) -> str:
    """Open URL in the paired Chromium browser via `bsk`, extract rendered HTML, and always close the session."""
    if not url or not url.startswith(("http://", "https://")) or not is_bsk_ready():
        return ""
    try:
        open_proc = subprocess.run(
            ["bsk", "open", url],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if open_proc.returncode != 0:
            return ""
        html_proc = subprocess.run(
            ["bsk", "get-html"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        return html_proc.stdout or ""
    except Exception:
        return ""
    finally:
        try:
            subprocess.run(["bsk", "close"], capture_output=True, text=True, timeout=5.0, check=False)
        except Exception:
            pass


def bsk_fetch_google_trends_br(limit: int = 6, timeout: float = 20.0) -> List[Dict]:
    """Fetch live Google Trends Brazil trending searches via `bsk` VOM snapshot when browser is connected."""
    if not is_bsk_ready():
        return []
    items: List[Dict] = []
    try:
        proc = subprocess.run(
            ["bsk", "open", "https://trends.google.com/trending?geo=BR"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            return []
        snap = proc.stdout or ""
        # Extract meaningful trend titles from VOM snapshot lines
        seen: set[str] = set()
        for line in snap.splitlines():
            m = re.search(r'(?:text|heading|link|cell)\s+"([^"]{6,64})"', line)
            if not m:
                continue
            cand = m.group(1).strip()
            low = cand.lower()
            if any(skip in low for skip in ("google", "trends", "trending", "search", "explore", "sign in", "menu", "privacy", "terms", "active", "hours ago")):
                continue
            if low in seen or len(cand.split()) < 2:
                continue
            seen.add(low)
            items.append({
                "id": f"bsk_trend_{len(items) + 1}",
                "title": cand,
                "source": "Google Trends BR (BrowserSkill)",
                "url": f"https://www.google.com/search?q={cand.replace(' ', '+')}",
            })
            if len(items) >= limit:
                break
    except Exception:
        return []
    finally:
        try:
            subprocess.run(["bsk", "close"], capture_output=True, text=True, timeout=5.0, check=False)
        except Exception:
            pass
    return items
