"""Native Chromium CDP (Chrome DevTools Protocol) automation for TikTok Studio Web.

Runs 100% in pure Python (zero Playwright/Node driver dependency) on both Termux Android
(`chromium-browser` 157+ aarch64) and Windows Desktop (`chrome`/`msedge`), using a
persistent profile directory and optional cookie injection (`output/tiktok_cookies.json`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def find_chromium_binary() -> str:
    """Locate a Chromium/Chrome binary on Termux, Linux, or Windows."""
    env_bin = os.getenv("CHROMIUM_BIN", "").strip()
    if env_bin and Path(env_bin).is_file():
        return env_bin
    for name in ("chromium-browser", "chromium", "google-chrome", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        "/data/data/com.termux/files/usr/bin/chromium-browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return ""


class CDPClient:
    """Minimal zero-dependency RFC 6455 WebSocket client for Chrome DevTools Protocol."""

    def __init__(self, ws_url: str, timeout: float = 20.0) -> None:
        parsed = urllib.parse.urlparse(ws_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 9222
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += f"?{parsed.query}"
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._buf = bytearray()
        self._msg_id = 0
        self._connect()

    def _connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode("ascii"))
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake closed unexpectedly")
            raw += chunk
        header_end = raw.index(b"\r\n\r\n") + 4
        head = raw[:header_end].decode("latin1")
        if "101" not in head.splitlines()[0]:
            raise ConnectionError(f"WebSocket handshake failed: {head.splitlines()[0]}")
        expected = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()).decode("ascii")
        if expected not in head:
            raise ConnectionError("Invalid Sec-WebSocket-Accept header")
        self._sock = sock
        self._buf.extend(raw[header_end:])

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> "CDPClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _read_exact(self, n: int) -> bytes:
        assert self._sock is not None
        while len(self._buf) < n:
            chunk = self._sock.recv(max(4096, n - len(self._buf)))
            if not chunk:
                raise ConnectionError("WebSocket EOF")
            self._buf.extend(chunk)
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self._sock is not None
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | (opcode & 0x0F)])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(header) + masked)

    def _recv_message(self) -> str:
        fragments: List[bytes] = []
        while True:
            b1, b2 = self._read_exact(2)
            fin = bool(b1 & 0x80)
            opcode = b1 & 0x0F
            masked = bool(b2 & 0x80)
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            mask_key = self._read_exact(4) if masked else b""
            data = self._read_exact(length)
            if masked:
                data = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:  # close
                raise ConnectionError("WebSocket closed by Chromium")
            if opcode == 0x9:  # ping
                self._send_frame(0xA, data)
                continue
            if opcode == 0xA:  # pong
                continue
            fragments.append(data)
            if fin:
                return b"".join(fragments).decode("utf-8", errors="replace")

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._msg_id += 1
        cid = self._msg_id
        self._send_frame(0x1, json.dumps({"id": cid, "method": method, "params": params or {}}).encode("utf-8"))
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            msg = json.loads(self._recv_message())
            if msg.get("id") == cid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method} error: {msg['error']}")
                return msg.get("result") or {}
        raise TimeoutError(f"CDP {method} timed out")

    def eval_js(self, expr: str) -> Any:
        res = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS error: {res['exceptionDetails']}")
        return (res.get("result") or {}).get("value")


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _cookies_path(out_dir: Path) -> Path:
    return out_dir / "tiktok_cookies.json"


def save_tiktok_cookies(out_dir: Path, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Persist TikTok Web session cookies (e.g. sessionid) for headless CDP runs."""
    cleaned: List[Dict[str, Any]] = []
    for c in cookies:
        if isinstance(c, dict) and c.get("name") and c.get("value"):
            cleaned.append({
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": str(c.get("domain") or ".tiktok.com"),
                "path": str(c.get("path") or "/"),
            })
    p = _cookies_path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "saved_count": len(cleaned), "has_sessionid": any(c["name"] == "sessionid" for c in cleaned)}


def _sync_live_cookies(cdp: CDPClient, out_dir: Path) -> int:
    """Pull refreshed .tiktok.com cookies from Chromium back into tiktok_cookies.json."""
    try:
        res = cdp.call("Network.getAllCookies")
        all_ck = [
            c for c in (res.get("cookies") or [])
            if isinstance(c, dict) and "tiktok.com" in str(c.get("domain") or "")
        ]
        if any(c.get("name") == "sessionid" and c.get("value") for c in all_ck):
            save_tiktok_cookies(out_dir, all_ck)
            return len(all_ck)
    except Exception:
        pass
    return 0


def get_tiktok_cdp_status(out_dir: Path) -> Dict[str, Any]:
    """Return readiness of native Chromium CDP TikTok Studio Web automation."""
    chrome = find_chromium_binary()
    prof = out_dir / "tiktok_chrome_profile"
    ck_file = _cookies_path(out_dir)
    cookies = []
    if ck_file.is_file():
        try:
            cookies = json.loads(ck_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cookies = []
    has_session = bool(os.getenv("TIKTOK_SESSIONID", "").strip()) or any(
        isinstance(c, dict) and c.get("name") == "sessionid" and c.get("value") for c in cookies
    )
    return {
        "ok": bool(chrome),
        "chromium_bin": chrome,
        "profile_dir": str(prof),
        "profile_exists": prof.is_dir(),
        "cookies_saved": len(cookies),
        "has_sessionid": has_session,
        "ready_to_publish": bool(chrome and (has_session or prof.is_dir())),
    }


def _launch_chromium(out_dir: Path, port: int, headless: bool = True) -> subprocess.Popen:
    chrome = find_chromium_binary()
    if not chrome:
        raise RuntimeError("Chromium nao encontrado. No Termux rode: pkg install -y x11-repo chromium")
    prof = out_dir / "tiktok_chrome_profile"
    prof.mkdir(parents=True, exist_ok=True)
    args = [
        chrome,
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={prof}",
    ]
    if headless:
        args.append("--headless=new")
    args.append("about:blank")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_cdp_page_ws(port: int, timeout: float = 15.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2.0) as r:
                pages = json.loads(r.read().decode("utf-8"))
            for p in pages:
                if p.get("type") == "page" and p.get("webSocketDebuggerUrl"):
                    return str(p["webSocketDebuggerUrl"])
        except Exception:
            time.sleep(0.35)
    raise TimeoutError(f"Chromium CDP did not open on port {port}")


def publish_pack_to_tiktok_cdp(
    video_path: Path,
    force: bool = False,
    headless: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Upload and publish an MP4 to TikTok Studio Web via native Chromium CDP."""
    from .smart_autopublish import is_wifi_connected
    from .publisher import _sanitize_publish_caption

    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"Video not found: {mp4}")

    if not is_wifi_connected():
        return {"status": "deferred", "reason": "wifi_only_no_wifi"}

    pack_path = mp4.with_suffix(".publish.json")
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
    existing = pack.get("tiktok") or {}
    if not force and existing.get("publish_id"):
        return {**existing, "status": "already_published_tiktok", "skipped": True}

    out_dir = mp4.parent
    status = get_tiktok_cdp_status(out_dir)
    if not status["ok"]:
        return {"status": "skipped_unconfigured", "reason": "Chromium nao instalado no ambiente."}

    caption = _sanitize_publish_caption(str(pack.get("caption") or pack.get("title") or mp4.stem))[:2200]
    port = _pick_free_port()
    proc = _launch_chromium(out_dir, port, headless=headless)
    try:
        ws_url = _wait_cdp_page_ws(port, timeout=20.0)
        with CDPClient(ws_url, timeout=30.0) as cdp:
            cdp.call("Page.enable")
            cdp.call("DOM.enable")
            cdp.call("Network.enable")

            # Inject saved cookies or TIKTOK_SESSIONID if provided
            cookies: List[Dict[str, Any]] = []
            ck_file = _cookies_path(out_dir)
            if ck_file.is_file():
                try:
                    cookies = json.loads(ck_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    cookies = []
            env_sid = os.getenv("TIKTOK_SESSIONID", "").strip()
            if env_sid and not any(c.get("name") == "sessionid" for c in cookies if isinstance(c, dict)):
                cookies.append({"name": "sessionid", "value": env_sid, "domain": ".tiktok.com", "path": "/"})
            for ck in cookies:
                if isinstance(ck, dict) and ck.get("name") and ck.get("value"):
                    cdp.call("Network.setCookie", {
                        "name": str(ck["name"]),
                        "value": str(ck["value"]),
                        "domain": str(ck.get("domain") or ".tiktok.com"),
                        "path": str(ck.get("path") or "/"),
                        "secure": True,
                    })

            cdp.call("Page.navigate", {"url": "https://www.tiktok.com/tiktokstudio/upload?from=webapp"})
            cur_url = ""
            file_node_id = 0
            for _ in range(18):
                time.sleep(1.5)
                cur_url = str(cdp.eval_js("window.location.href") or "")
                if "/login" in cur_url.lower():
                    return {
                        "status": "login_required",
                        "reason": "Sessao do TikTok Studio Web nao autenticada. Salve o cookie sessionid via /api/tiktok/cdp/cookies.",
                        "current_url": cur_url,
                    }
                doc = cdp.call("DOM.getDocument", {"depth": -1})
                root_id = doc["root"]["nodeId"]
                inp = cdp.call("DOM.querySelector", {"nodeId": root_id, "selector": "input[type='file']"})
                file_node_id = int(inp.get("nodeId") or 0)
                if file_node_id:
                    break

            _sync_live_cookies(cdp, out_dir)
            if not file_node_id:
                return {"status": "error", "reason": "Campo input[type=file] nao encontrado no TikTok Studio Web.", "current_url": cur_url}

            if dry_run:
                return {"status": "cdp_dry_run_ready", "current_url": cur_url, "caption_preview": caption[:80]}

            cdp.call("DOM.setFileInputFiles", {"nodeId": file_node_id, "files": [str(mp4.resolve())]})
            time.sleep(10.0)

            # Wait for caption editor and set sanitized caption
            js_caption = json.dumps(caption)
            for _ in range(12):
                has_ed = cdp.eval_js("Boolean(document.querySelector('[contenteditable=\"true\"]'))")
                if has_ed:
                    break
                time.sleep(2.0)

            cdp.eval_js(f"""
            (() => {{
                const ed = document.querySelector('[contenteditable="true"]');
                if (!ed) return false;
                ed.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, {js_caption});
                return true;
            }})()
            """)
            time.sleep(2.0)

            # Wait up to 90s for Post/Publicar button to become enabled and click
            posted = False
            for _ in range(30):
                clicked = cdp.eval_js("""
                (() => {
                    const dismiss = Array.from(document.querySelectorAll('button, [role="button"]')).find(b => {
                        const txt = (b.innerText || '').trim();
                        return /^(got it|entendi)$/i.test(txt) && !b.disabled;
                    });
                    if (dismiss) { dismiss.click(); }
                    const byE2e = document.querySelector('[data-e2e="post_video_button"]');
                    const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                    const target = byE2e || btns.find(b => {
                        const txt = (b.innerText || '').trim();
                        return /^(post|publicar)$/i.test(txt);
                    });
                    if (!target) return false;
                    const dis = target.disabled || target.getAttribute('aria-disabled') === 'true' || target.getAttribute('data-disabled') === 'true';
                    if (dis) return false;
                    target.scrollIntoView({block: 'center'});
                    target.click();
                    return true;
                })()
                """)
                if clicked:
                    posted = True
                    break
                time.sleep(3.0)

            if posted:
                # Handle optional confirmation modal (e.g. "Post now" / "Continue") and wait for redirect
                for _ in range(10):
                    time.sleep(2.0)
                    cdp.eval_js("""
                    (() => {
                        const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                        const confirm = btns.find(b => {
                            const txt = (b.innerText || '').trim();
                            const dis = b.disabled || b.getAttribute('aria-disabled') === 'true';
                            return /^(post now|publicar agora|continue)$/i.test(txt) && !dis;
                        });
                        if (confirm) confirm.click();
                    })()
                    """)
                    url_now = cdp.eval_js("location.href") or ""
                    if "/upload" not in url_now:
                        break

            if not posted:
                return {"status": "error", "reason": "Botao Post/Publicar nao ficou habilitado a tempo."}

            time.sleep(6.0)
            _sync_live_cookies(cdp, out_dir)
            pub_id = f"cdp:{int(time.time())}"
            tt_info = {"publish_id": pub_id, "mode": "cdp", "published_at": int(time.time())}
            pack["tiktok"] = tt_info
            pack["tiktok_publish_id"] = pub_id
            pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "published_tiktok_cdp", **tt_info}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

