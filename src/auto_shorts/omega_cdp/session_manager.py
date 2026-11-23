"""Secure Session Manager — Isolated browser profiles, credential guarding, and human verification detection."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Platform, SessionProfile

logger = logging.getLogger("autoshorts.omega_cdp.session")

_HUMAN_CHALLENGE_PATTERNS = [
    (r"accounts\.google\.com/.*challenge", "GOOGLE_AUTH_CHALLENGE", "Verificação em duas etapas ou confirmação de dispositivo do Google"),
    (r"tiktok\.com/login", "TIKTOK_LOGIN_REQUIRED", "Sessão do TikTok expirada ou não autenticada"),
    (r"verify-center|security.*challenge", "TIKTOK_CAPTCHA_VERIFY", "Verificação de segurança / puzzle captcha do TikTok"),
    (r"instagram\.com/challenge|checkpoint_required", "INSTAGRAM_CHALLENGE", "Ponto de verificação de segurança do Instagram"),
    (r"challenges\.cloudflare\.com|cf-turnstile", "CLOUDFLARE_CHALLENGE", "Desafio Cloudflare / Verificação de navegador"),
    (r"recaptcha|hcaptcha|arkose", "CAPTCHA_DETECTED", "Desafio de verificação humana detectado na página"),
]


class SecureSessionManager:
    """Gerenciador seguro de sessões de navegadores isoladas por plataforma."""

    def __init__(self, base_dir: Path | str = "output/browser_profiles") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_secure_permissions(self.base_dir, is_dir=True)

    def _ensure_secure_permissions(self, path: Path, is_dir: bool = False) -> None:
        if os.name != "nt" and path.exists():
            try:
                os.chmod(path, 0o700 if is_dir else 0o600)
            except OSError:
                pass

    def get_profile_dir(self, platform: Platform | str) -> Path:
        p_name = platform.value if isinstance(platform, Platform) else str(platform)
        p_dir = self.base_dir / p_name
        p_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_secure_permissions(p_dir, is_dir=True)
        return p_dir

    def get_cookies_path(self, platform: Platform | str) -> Path:
        return self.get_profile_dir(platform) / "cookies.json"

    def clean_stale_locks(self, platform: Platform | str) -> None:
        """Remove arquivos de trava de sessões anteriores encerradas incorretamente."""
        prof = self.get_profile_dir(platform)
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = prof / lock_name
            if lock_path.exists() or lock_path.is_symlink():
                try:
                    lock_path.unlink()
                except OSError:
                    pass

    def save_cookies(self, platform: Platform | str, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Salva cookies limpos com permissões estritas (chmod 600 em POSIX)."""
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
                "domain": str(c.get("domain") or ""),
                "path": str(c.get("path") or "/"),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
            })
        target = self.get_cookies_path(platform)
        target.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
        self._ensure_secure_permissions(target, is_dir=False)
        return {"ok": True, "count": len(cleaned), "path": str(target)}

    def load_cookies(self, platform: Platform | str) -> List[Dict[str, Any]]:
        target = self.get_cookies_path(platform)
        if not target.is_file():
            return []
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_session_profile(self, platform: Platform | str) -> SessionProfile:
        p = Platform(platform) if isinstance(platform, str) else platform
        prof_dir = self.get_profile_dir(p)
        ck_path = self.get_cookies_path(p)
        cookies = self.load_cookies(p)

        has_auth = False
        handle = ""
        if p == Platform.YOUTUBE:
            has_auth = any(c.get("name") in ("SID", "SAPISID", "SSID", "HSID") for c in cookies)
        elif p == Platform.TIKTOK:
            has_auth = any(c.get("name") == "sessionid" for c in cookies)
        elif p == Platform.INSTAGRAM:
            has_auth = any(c.get("name") == "sessionid" for c in cookies)

        return SessionProfile(
            platform=p,
            profile_dir=str(prof_dir),
            cookies_path=str(ck_path),
            is_authenticated=has_auth,
            last_validated=time.time() if has_auth else 0.0,
            account_handle=handle,
            lock_held=False,
        )

    def detect_human_challenge(self, current_url: str, html_snippet: str = "") -> Optional[Dict[str, str]]:
        """Identifica de forma passiva se a página exige intervenção humana (MFA, CAPTCHA, login).
        
        NUNCA tenta burlar: o agente deve parar e solicitar intervenção humana legítima.
        """
        combined = f"{current_url}\n{html_snippet}".lower()
        for pattern, code, desc in _HUMAN_CHALLENGE_PATTERNS:
            if re.search(pattern, combined, re.I):
                return {
                    "challenge_type": code,
                    "description": desc,
                    "url": current_url,
                }
        return None
