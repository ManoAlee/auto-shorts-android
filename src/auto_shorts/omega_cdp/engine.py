"""Omega CDP Engine — Low-level protocol abstraction over Page, DOM, Runtime, Network, Input and Performance."""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..tiktok_cdp import (
    CDPClient,
    _pick_free_port,
    _wait_cdp_page_ws,
    find_chromium_binary,
    terminate_chromium_process_group,
)

logger = logging.getLogger("autoshorts.omega_cdp.engine")


class OmegaCDPEngine:
    """Controlador CDP unificado de alto nível com isolamento de processo e limpeza de órfãos."""

    def __init__(
        self,
        profile_dir: Path | str,
        port: Optional[int] = None,
        headless: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.port = port or _pick_free_port()
        self.headless = headless
        self.timeout = timeout
        self.proc: Optional[subprocess.Popen] = None
        self.cdp: Optional[CDPClient] = None
        self.ws_url: str = ""

    def __enter__(self) -> OmegaCDPEngine:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def start(self) -> None:
        chrome = find_chromium_binary()
        if not chrome:
            raise RuntimeError("Chromium nao encontrado no ambiente.")

        # Limpar possíveis travas de sessões mortas
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_p = self.profile_dir / lock_name
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
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
        ]
        if self.headless:
            args.append("--headless=new")
        args.append("about:blank")

        extra_kwargs: Dict[str, Any] = {}
        if os.name != "nt":
            extra_kwargs["preexec_fn"] = os.setsid

        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra_kwargs)
        try:
            self.ws_url = _wait_cdp_page_ws(self.port, timeout=self.timeout)
            self.cdp = CDPClient(self.ws_url, timeout=self.timeout)
            self.cdp.call("Page.enable")
            self.cdp.call("DOM.enable")
            self.cdp.call("Network.enable")
            self.cdp.call("Runtime.enable")
        except Exception as exc:
            self.stop()
            raise RuntimeError(f"Falha ao inicializar sessao CDP na porta {self.port}: {exc}") from exc

    def stop(self) -> None:
        if self.cdp:
            try:
                self.cdp.close()
            except Exception:
                pass
            self.cdp = None
        if self.proc:
            terminate_chromium_process_group(self.proc, self.profile_dir.name)
            self.proc = None

    # --- DOMAIN: PAGE & NAVIGATION ---
    def navigate(self, url: str, wait_complete: bool = True) -> str:
        if not self.cdp:
            raise RuntimeError("Engine CDP nao iniciada.")
        self.cdp.call("Page.navigate", {"url": url})
        if wait_complete:
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                ready = self.eval_js("document.readyState")
                if ready in ("interactive", "complete"):
                    break
                time.sleep(0.35)
        return self.get_current_url()

    def get_current_url(self) -> str:
        return str(self.eval_js("window.location.href") or "")

    def get_title(self) -> str:
        return str(self.eval_js("document.title") or "")

    def capture_screenshot(self, output_path: Path | str, quality: int = 90) -> str:
        """Captura screenshot da página via CDP Page.captureScreenshot e grava arquivo JPEG/PNG."""
        if not self.cdp:
            raise RuntimeError("Engine CDP nao iniciada.")
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = self.cdp.call("Page.captureScreenshot", {"format": "jpeg", "quality": quality})
        b64_data = res.get("data", "")
        if b64_data:
            out_p.write_bytes(base64.b64decode(b64_data))
            return str(out_p)
        raise RuntimeError("Falha ao capturar screenshot via CDP")

    # --- DOMAIN: RUNTIME & DOM ---
    def eval_js(self, expr: str) -> Any:
        if not self.cdp:
            raise RuntimeError("Engine CDP nao iniciada.")
        return self.cdp.eval_js(expr)

    def query_selector_exists(self, selector: str) -> bool:
        escaped = selector.replace('"', '\\"')
        return bool(self.eval_js(f'Boolean(document.querySelector("{escaped}"))'))

    def get_element_text(self, selector: str) -> str:
        escaped = selector.replace('"', '\\"')
        return str(self.eval_js(f'document.querySelector("{escaped}")?.innerText || ""'))

    def click_element(self, selector: str) -> bool:
        escaped = selector.replace('"', '\\"')
        return bool(self.eval_js(f'''
            (() => {{
                const el = document.querySelector("{escaped}");
                if (el) {{
                    el.click();
                    return true;
                }}
                return false;
            }})()
        '''))

    def fill_input(self, selector: str, value: str) -> bool:
        escaped_sel = selector.replace('"', '\\"')
        escaped_val = value.replace('"', '\\"').replace("\n", "\\n")
        return bool(self.eval_js(f'''
            (() => {{
                const el = document.querySelector("{escaped_sel}");
                if (el) {{
                    el.value = "{escaped_val}";
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})()
        '''))

    # --- DOMAIN: NETWORK & COOKIES ---
    def get_all_cookies(self) -> List[Dict[str, Any]]:
        if not self.cdp:
            return []
        try:
            res = self.cdp.call("Network.getAllCookies")
            return res.get("cookies", []) if isinstance(res, dict) else []
        except Exception:
            return []

    def inject_cookies(self, cookies: List[Dict[str, Any]]) -> int:
        if not self.cdp:
            return 0
        injected = 0
        for ck in cookies:
            if not isinstance(ck, dict) or not ck.get("name") or not ck.get("value"):
                continue
            try:
                self.cdp.call("Network.setCookie", {
                    "name": str(ck["name"]),
                    "value": str(ck["value"]),
                    "domain": str(ck.get("domain") or ""),
                    "path": str(ck.get("path") or "/"),
                    "secure": bool(ck.get("secure", True)),
                })
                injected += 1
            except Exception:
                pass
        return injected

    # --- DOMAIN: PERFORMANCE ---
    def get_performance_metrics(self) -> Dict[str, Any]:
        if not self.cdp:
            return {}
        try:
            res = self.cdp.call("Performance.getMetrics")
            raw_metrics = res.get("metrics", []) if isinstance(res, dict) else []
            return {m["name"]: m["value"] for m in raw_metrics if "name" in m and "value" in m}
        except Exception:
            return {}
