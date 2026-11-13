"""Native Chromium CDP YouTube Studio Web Publisher (Termux/Linux/Windows).

Reuses the zero-dependency CDPClient and Chromium launcher primitives from
``tiktok_cdp`` to upload Shorts directly via ``https://studio.youtube.com``:
- Zero YouTube Data API v3 daily quota limit (10,000 units/day bypassed)
- Supports Studio-only options (made-for-kids, altered content, visibility, schedule)
- Warm single-session batch publishing & live Google/YouTube cookie persistence
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tiktok_cdp import (
    CDPClient,
    _pick_free_port,
    _wait_cdp_page_ws,
    find_chromium_binary,
)

_YT_AUTH_COOKIE_NAMES = frozenset({"SID", "SAPISID", "SSID", "HSID", "__Secure-1PSID", "__Secure-3PSID"})


def _yt_cookies_path(out_dir: Path) -> Path:
    return out_dir / "youtube_cookies.json"


def _yt_profile_dir(out_dir: Path) -> Path:
    return out_dir / "youtube_chrome_profile"


def save_youtube_cookies(out_dir: Path, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Persist YouTube/Google Studio cookies locally for Chromium CDP sessions."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cleaned: List[Dict[str, Any]] = []
    for c in cookies:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        value = str(c.get("value") or "").strip()
        if not name or not value:
            continue
        cleaned.append({
            "name": name,
            "value": value,
            "domain": str(c.get("domain") or ".youtube.com"),
            "path": str(c.get("path") or "/"),
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        })
    p = _yt_cookies_path(out_dir)
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    has_auth = any(c["name"] in _YT_AUTH_COOKIE_NAMES for c in cleaned)
    return {"ok": True, "saved_count": len(cleaned), "has_auth_cookies": has_auth, "path": str(p)}


def _sync_live_yt_cookies(cdp: CDPClient, out_dir: Path) -> int:
    """Capture refreshed .youtube.com / .google.com cookies from live CDP."""
    try:
        res = cdp.call("Network.getAllCookies")
        all_ck = res.get("cookies") if isinstance(res, dict) else []
        if not isinstance(all_ck, list):
            return 0
        yt_ck = [
            c for c in all_ck
            if isinstance(c, dict)
            and any(d in str(c.get("domain") or "").lower() for d in ("youtube.com", "google.com"))
            and c.get("name") and c.get("value")
        ]
        if any(str(c.get("name")) in _YT_AUTH_COOKIE_NAMES for c in yt_ck):
            save_youtube_cookies(out_dir, yt_ck)
            return len(yt_ck)
    except Exception:
        pass
    return 0


def get_youtube_cdp_status(out_dir: Path) -> Dict[str, Any]:
    """Report Chromium binary availability, persistent profile, and YouTube Studio session cookies."""
    chrome = find_chromium_binary()
    ck_file = _yt_cookies_path(out_dir)
    prof = _yt_profile_dir(out_dir)
    cookies_count = 0
    has_auth = False
    if ck_file.is_file():
        try:
            data = json.loads(ck_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                cookies_count = len(data)
                has_auth = any(isinstance(c, dict) and c.get("name") in _YT_AUTH_COOKIE_NAMES for c in data)
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "ok": bool(chrome),
        "chromium_binary": chrome,
        "profile_exists": prof.is_dir(),
        "cookies_saved": cookies_count,
        "has_auth_cookies": has_auth,
        "ready_to_publish": bool(chrome and (has_auth or prof.is_dir())),
    }


def _launch_yt_chromium(out_dir: Path, port: int, headless: bool = True) -> subprocess.Popen:
    chrome = find_chromium_binary()
    if not chrome:
        raise RuntimeError("Chromium nao encontrado. No Termux rode: pkg install -y x11-repo chromium")
    prof = _yt_profile_dir(out_dir)
    prof.mkdir(parents=True, exist_ok=True)
    for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock_p = prof / lock_name
        if lock_p.exists() or lock_p.is_symlink():
            try:
                lock_p.unlink()
            except OSError:
                pass
    args = [
        chrome,
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--renderer-process-limit=1",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--mute-audio",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,900",
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={prof}",
    ]
    if headless:
        args.append("--headless=new")
    args.append("about:blank")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _inject_yt_cookies(cdp: CDPClient, out_dir: Path) -> None:
    ck_file = _yt_cookies_path(out_dir)
    if not ck_file.is_file():
        return
    try:
        cookies = json.loads(ck_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(cookies, list):
        return
    for ck in cookies:
        if isinstance(ck, dict) and ck.get("name") and ck.get("value"):
            cdp.call("Network.setCookie", {
                "name": str(ck["name"]),
                "value": str(ck["value"]),
                "domain": str(ck.get("domain") or ".youtube.com"),
                "path": str(ck.get("path") or "/"),
                "secure": True,
            })


def _build_youtube_cdp_metadata(pack: Dict[str, Any], fallback_stem: str) -> Dict[str, str]:
    """Prepare YouTube Shorts SEO title (<=100 chars) and description with #Shorts."""
    from .publisher import _sanitize_publish_caption

    title = _sanitize_publish_caption(str(pack.get("title") or pack.get("hook_title") or fallback_stem))
    title = " ".join(title.split())[:95] or fallback_stem[:95]
    desc = _sanitize_publish_caption(str(pack.get("caption") or title))
    if "#shorts" not in desc.lower():
        desc = f"{desc}\n\n#Shorts".strip()
    return {"title": title, "description": desc[:4800]}


def _publish_single_yt_in_cdp(
    cdp: CDPClient,
    mp4: Path,
    out_dir: Path,
    privacy_status: str = "PUBLIC",
    altered_content: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Upload and publish one Short via YouTube Studio Web inside an open CDP session."""
    pack_path = mp4.with_suffix(".publish.json")
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
    existing = pack.get("youtube") or {}
    if not force and existing.get("video_id"):
        return {**existing, "status": "already_published_youtube", "skipped": True, "file": mp4.name}

    meta = _build_youtube_cdp_metadata(pack, mp4.stem)
    cdp.call("Page.navigate", {"url": "https://www.youtube.com/upload"})

    cur_url = ""
    file_node_id = 0
    for _ in range(36):
        time.sleep(0.8)
        try:
            cur_url = str(cdp.eval_js("window.location.href") or "")
            if "accounts.google.com" in cur_url.lower():
                return {
                    "status": "login_required",
                    "reason": "Sessao do YouTube Studio Web nao autenticada. Salve os cookies via /api/youtube/cdp/cookies.",
                    "current_url": cur_url,
                    "file": mp4.name,
                }
            # Open Create -> Upload videos dialog if file input not yet in DOM
            cdp.eval_js("""
            (() => {
                if (document.querySelector('input[type="file"]')) return;
                const createBtn = document.querySelector('#create-icon') || document.querySelector('ytcp-button#create-icon');
                if (createBtn) createBtn.click();
                const uploadItem = document.querySelector('#text-item-0') || document.querySelector('[test-id="upload-betas"]');
                if (uploadItem) uploadItem.click();
            })()
            """)
            doc = cdp.call("DOM.getDocument", {"depth": -1})
            inp = cdp.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "input[type='file']"})
            file_node_id = int(inp.get("nodeId") or 0)
            if file_node_id:
                break
        except RuntimeError:
            # Cross-origin redirect from youtube.com/upload -> studio.youtube.com
            continue

    _sync_live_yt_cookies(cdp, out_dir)
    if not file_node_id:
        return {"status": "error", "reason": "Campo input[type=file] nao encontrado no YouTube Studio.", "current_url": cur_url, "file": mp4.name}

    if dry_run:
        return {"status": "youtube_cdp_dry_run_ready", "current_url": cur_url, "title": meta["title"], "file": mp4.name}

    cdp.call("DOM.setFileInputFiles", {"nodeId": file_node_id, "files": [str(mp4.resolve())]})

    # Wait for Details dialog title/description textboxes
    has_boxes = False
    for _ in range(30):
        time.sleep(0.8)
        has_boxes = bool(cdp.eval_js("document.querySelectorAll('#textbox[contenteditable=\"true\"]').length >= 1"))
        if has_boxes:
            break

    if has_boxes:
        # Fill Title (index 0) and Description (index 1) via CDP Input
        for idx, val in enumerate([meta["title"], meta["description"]]):
            focused = cdp.eval_js(f"""
            (() => {{
                const boxes = document.querySelectorAll('#textbox[contenteditable="true"]');
                if (!boxes[{idx}]) return false;
                boxes[{idx}].focus();
                return true;
            }})()
            """)
            if focused:
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
                cdp.call("Input.insertText", {"text": val})
                time.sleep(0.4)

    # Set "No, not made for kids" + optional altered content disclosure
    cdp.eval_js(f"""
    (() => {{
        const notKids = document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
        if (notKids) notKids.click();
        const showMore = document.querySelector('#toggle-button');
        if (showMore && showMore.getAttribute('aria-expanded') !== 'true') showMore.click();
        const altName = {json.dumps("ALTERED_CONTENT_YES" if altered_content else "ALTERED_CONTENT_NO")};
        const altBtn = document.querySelector(`tp-yt-paper-radio-button[name="${{altName}}"]`);
        if (altBtn) altBtn.click();
    }})()
    """)

    # Advance through Details -> Video elements -> Checks -> Visibility
    for _ in range(4):
        time.sleep(0.8)
        at_vis = bool(cdp.eval_js(f"Boolean(document.querySelector('tp-yt-paper-radio-button[name={json.dumps(privacy_status.upper())}]'))"))
        if at_vis:
            break
        cdp.eval_js("(() => { const n = document.querySelector('#next-button'); if (n && !n.disabled) n.click(); })()")

    # Select visibility and click Publish/Save (#done-button)
    vis_name = privacy_status.upper() if privacy_status.upper() in ("PUBLIC", "UNLISTED", "PRIVATE") else "PUBLIC"
    published_url = ""
    for _ in range(45):
        time.sleep(1.0)
        res_state = cdp.eval_js(f"""
        (() => {{
            const vis = document.querySelector('tp-yt-paper-radio-button[name="{vis_name}"]');
            if (vis && vis.getAttribute('aria-checked') !== 'true') vis.click();
            const link = document.querySelector('a[href*="youtu.be/"], a[href*="/shorts/"], a[href*="watch?v="]');
            const href = link ? link.getAttribute('href') : '';
            const done = document.querySelector('#done-button');
            if (done && !done.disabled && done.getAttribute('aria-disabled') !== 'true') {{
                done.click();
                return {{clicked: true, href}};
            }}
            return {{clicked: false, href}};
        }})()
        """)
        if isinstance(res_state, dict):
            if res_state.get("href"):
                published_url = str(res_state["href"])
            if res_state.get("clicked"):
                break

    if not published_url:
        time.sleep(2.0)
        published_url = str(cdp.eval_js("(() => { const l = document.querySelector('a[href*=\"youtu.be/\"], a[href*=\"/shorts/\"], a[href*=\"watch?v=\"]'); return l ? l.href : ''; })()") or "")

    vid_match = re.search(r"(?:youtu\.be/|/shorts/|v=)([A-Za-z0-9_-]{6,})", published_url)
    vid = vid_match.group(1) if vid_match else f"cdp:{int(time.time())}"
    final_url = f"https://youtube.com/shorts/{vid}" if vid_match else published_url
    _sync_live_yt_cookies(cdp, out_dir)

    yt_record = {
        "video_id": vid,
        "url": final_url,
        "privacy": vis_name.lower(),
        "mode": "cdp",
        "altered_content": altered_content,
        "published_at": int(time.time()),
    }
    pack["youtube"] = yt_record
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "published_youtube_cdp", "file": mp4.name, **yt_record}


def publish_pack_to_youtube_cdp(
    video_path: Path,
    privacy_status: str = "PUBLIC",
    altered_content: bool = False,
    force: bool = False,
    headless: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Upload and publish one MP4 Short to YouTube Studio Web via native Chromium CDP."""
    from .smart_autopublish import is_wifi_connected

    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"Video not found: {mp4}")
    if not is_wifi_connected():
        return {"status": "deferred", "reason": "wifi_only_no_wifi"}

    pack_path = mp4.with_suffix(".publish.json")
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
    existing = pack.get("youtube") or {}
    if not force and existing.get("video_id"):
        return {**existing, "status": "already_published_youtube", "skipped": True}

    out_dir = mp4.parent
    if not get_youtube_cdp_status(out_dir)["ok"]:
        return {"status": "skipped_unconfigured", "reason": "Chromium nao instalado no ambiente."}

    port = _pick_free_port()
    proc = _launch_yt_chromium(out_dir, port, headless=headless)
    try:
        ws_url = _wait_cdp_page_ws(port, timeout=20.0)
        with CDPClient(ws_url, timeout=30.0) as cdp:
            cdp.call("Page.enable")
            cdp.call("DOM.enable")
            cdp.call("Network.enable")
            _inject_yt_cookies(cdp, out_dir)
            return _publish_single_yt_in_cdp(
                cdp, mp4, out_dir,
                privacy_status=privacy_status,
                altered_content=altered_content,
                force=force,
                dry_run=dry_run,
            )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def publish_batch_to_youtube_cdp(
    video_paths: List[Path],
    privacy_status: str = "PUBLIC",
    altered_content: bool = False,
    force: bool = False,
    headless: bool = True,
    max_videos: int = 5,
    dry_run: bool = False,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Publish multiple MP4 Shorts to YouTube Studio Web in one warm Chromium CDP session."""
    from .smart_autopublish import is_wifi_connected

    if not is_wifi_connected():
        return {"status": "deferred", "reason": "wifi_only_no_wifi", "results": []}

    results: List[Dict[str, Any]] = []
    pending: List[Path] = []
    for vp in video_paths:
        mp4 = Path(vp)
        if not mp4.is_file():
            results.append({"file": mp4.name, "status": "error", "reason": "file_not_found"})
            continue
        pack_path = mp4.with_suffix(".publish.json")
        pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
        existing = pack.get("youtube") or {}
        if not force and existing.get("video_id"):
            results.append({**existing, "file": mp4.name, "status": "already_published_youtube", "skipped": True})
            continue
        pending.append(mp4)

    target_batch = pending[: max(1, int(max_videos))]
    if not target_batch:
        return {
            "status": "batch_complete",
            "published_count": 0,
            "skipped_count": sum(1 for r in results if r.get("skipped")),
            "error_count": sum(1 for r in results if r.get("status") == "error"),
            "results": results,
        }

    od = out_dir or target_batch[0].parent
    if not get_youtube_cdp_status(od)["ok"]:
        return {"status": "skipped_unconfigured", "reason": "Chromium nao instalado no ambiente.", "results": results}

    port = _pick_free_port()
    proc = _launch_yt_chromium(od, port, headless=headless)
    try:
        ws_url = _wait_cdp_page_ws(port, timeout=20.0)
        with CDPClient(ws_url, timeout=30.0) as cdp:
            cdp.call("Page.enable")
            cdp.call("DOM.enable")
            cdp.call("Network.enable")
            _inject_yt_cookies(cdp, od)
            for mp4 in target_batch:
                res = _publish_single_yt_in_cdp(
                    cdp, mp4, od,
                    privacy_status=privacy_status,
                    altered_content=altered_content,
                    force=force,
                    dry_run=dry_run,
                )
                results.append(res)
                if res.get("status") == "login_required":
                    break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    return {
        "status": "batch_complete",
        "published_count": sum(1 for r in results if r.get("status") == "published_youtube_cdp"),
        "skipped_count": sum(1 for r in results if r.get("skipped")),
        "error_count": sum(1 for r in results if r.get("status") == "error"),
        "results": results,
    }

