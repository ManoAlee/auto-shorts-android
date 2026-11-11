#!/usr/bin/env python3
"""One-time TikTok Content Posting API v2 OAuth2 helper (Login Kit v2 -> .env)."""

import argparse
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Dict, Tuple


REDIRECT_URI = "http://localhost:8766/callback"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
DEFAULT_SCOPES = "user.info.basic,video.upload,video.publish"
_PKCE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def _load_dotenv_defaults(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def generate_pkce_pair() -> Tuple[str, str]:
    """Generate TikTok Login Kit Desktop PKCE (code_verifier, sha256_hex_challenge)."""
    verifier = "".join(secrets.choice(_PKCE_CHARS) for _ in range(64))
    challenge = hashlib.sha256(verifier.encode("utf-8")).hexdigest()
    return verifier, challenge


def build_tiktok_authorize_url(
    client_key: str,
    redirect_uri: str = REDIRECT_URI,
    scopes: str = DEFAULT_SCOPES,
    state: str = "",
    code_challenge: str = "",
) -> str:
    """Build the TikTok OAuth2 v2 authorization URL."""
    params = {
        "client_key": client_key.strip(),
        "scope": scopes,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state or secrets.token_urlsafe(12),
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def exchange_tiktok_code(
    client_key: str,
    client_secret: str,
    code: str,
    redirect_uri: str = REDIRECT_URI,
    code_verifier: str = "",
) -> Dict:
    """Exchange an authorization code for TikTok access_token + refresh_token."""
    body_params = {
        "client_key": client_key.strip(),
        "client_secret": client_secret.strip(),
        "code": code.strip(),
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        body_params["code_verifier"] = code_verifier
    form = urllib.parse.urlencode(body_params).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def save_tiktok_credentials(env_path: Path, client_key: str, client_secret: str, tokens: Dict) -> None:
    """Update .env with TikTok OAuth2 tokens without printing secrets."""
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    keys_prefix = (
        "TIKTOK_CLIENT_KEY=",
        "TIKTOK_CLIENT_SECRET=",
        "TIKTOK_ACCESS_TOKEN=",
        "TIKTOK_REFRESH_TOKEN=",
        "TIKTOK_PUBLISH_MODE=",
        "TIKTOK_PRIVACY_LEVEL=",
    )
    lines = [ln for ln in existing.splitlines() if not ln.startswith(keys_prefix)]
    lines.extend([
        f"TIKTOK_CLIENT_KEY={client_key.strip()}",
        f"TIKTOK_CLIENT_SECRET={client_secret.strip()}",
        f"TIKTOK_ACCESS_TOKEN={str(tokens.get('access_token') or '').strip()}",
        f"TIKTOK_REFRESH_TOKEN={str(tokens.get('refresh_token') or '').strip()}",
        f"TIKTOK_PUBLISH_MODE={os.getenv('TIKTOK_PUBLISH_MODE', 'inbox')}",
        f"TIKTOK_PRIVACY_LEVEL={os.getenv('TIKTOK_PRIVACY_LEVEL', 'SELF_ONLY')}",
    ])
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    _load_dotenv_defaults(env_path)

    parser = argparse.ArgumentParser(description="Authorize TikTok Content Posting API v2 and save tokens to .env")
    parser.add_argument("--client-key", default=os.getenv("TIKTOK_CLIENT_KEY", ""))
    parser.add_argument("--client-secret", default=os.getenv("TIKTOK_CLIENT_SECRET", ""))
    parser.add_argument("--redirect-uri", default=REDIRECT_URI)
    parser.add_argument("--scopes", default=DEFAULT_SCOPES)
    parser.add_argument("--no-pkce", action="store_true", help="Disable Desktop PKCE hex challenge (Web HTTPS redirect)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args(argv)

    client_key = args.client_key.strip() or input("TIKTOK_CLIENT_KEY: ").strip()
    client_secret = args.client_secret.strip() or input("TIKTOK_CLIENT_SECRET: ").strip()
    if not client_key or not client_secret:
        raise ValueError("TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET sao obrigatorios.")

    csrf_state = secrets.token_urlsafe(12)
    code_verifier, code_challenge = ("", "") if args.no_pkce else generate_pkce_pair()
    auth_url = build_tiktok_authorize_url(
        client_key=client_key,
        redirect_uri=args.redirect_uri,
        scopes=args.scopes,
        state=csrf_state,
        code_challenge=code_challenge,
    )
    print("\nAbra http://localhost:8766/go no navegador para autorizar o TikTok:\n", flush=True)
    if not args.no_browser:
        webbrowser.open("http://localhost:8766/go")

    auth_code: Dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/go":
                self.send_response(302)
                self.send_header("Location", auth_url)
                self.end_headers()
                return

            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                auth_code["code"] = urllib.parse.unquote(qs["code"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>TikTok autorizado! Pode fechar esta aba e voltar ao terminal.</h2>")
            else:
                err = qs.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h3>Erro OAuth TikTok: {err}</h3>".encode("utf-8"))

        def log_message(self, format, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 8766), Handler)
    server.timeout = 30
    deadline = time.time() + 600
    while "code" not in auth_code and time.time() < deadline:
        server.handle_request()

    code = auth_code.get("code")
    if not code:
        print("Nenhum codigo OAuth TikTok recebido.", flush=True)
        return 1

    tokens = exchange_tiktok_code(
        client_key,
        client_secret,
        code,
        redirect_uri=args.redirect_uri,
        code_verifier=code_verifier,
    )
    if not tokens.get("access_token"):
        print(f"Falha ao trocar codigo por token TikTok: {tokens.get('error_description') or tokens.get('error') or 'unknown'}", flush=True)
        return 1

    save_tiktok_credentials(env_path, client_key, client_secret, tokens)
    print(f"\nCredenciais TikTok salvas com seguranca em {env_path}!", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

