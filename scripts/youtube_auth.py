#!/usr/bin/env python3
"""One-time YouTube Data API v3 OAuth2 helper (supports --json client_secret file and /go redirect)."""

import argparse
import http.server
import json
import os
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Tuple


REDIRECT_URI = "http://localhost:8765"
# Full youtube scope enables upload + metadata updates + playlists + thumbnails.set
SCOPE = "https://www.googleapis.com/auth/youtube"


def load_client_credentials(json_path: str | None) -> Tuple[str, str]:
    if json_path:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        section = data.get("installed") or data.get("web") or {}
        cid = str(section.get("client_id") or "").strip()
        csec = str(section.get("client_secret") or "").strip()
        if not cid or not csec:
            raise ValueError(f"Invalid OAuth JSON structure in {json_path}")
        return cid, csec

    cid = input("YT_CLIENT_ID: ").strip()
    csec = input("YT_CLIENT_SECRET: ").strip()
    if not cid or not csec:
        raise ValueError("Client ID and Client Secret are required.")
    return cid, csec


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Authorize YouTube Data API v3 upload and save to .env")
    parser.add_argument("--json", dest="json_path", default=None, help="Path to Google OAuth client_secret_*.json")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args(argv)

    client_id, client_secret = load_client_credentials(args.json_path)

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
    print("\nAbra http://localhost:8765/go no navegador (ou em Aba Anonima Ctrl+Shift+N):\n", flush=True)
    if not args.no_browser:
        webbrowser.open("http://localhost:8765/go")

    auth_code = {}

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
                auth_code["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>YouTube autorizado! Pode fechar esta aba e voltar ao chat/Termux.</h2>")
            else:
                err = qs.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h3>Erro OAuth: {err}. Tente novamente em http://localhost:8765/go</h3>".encode("utf-8"))

        def log_message(self, format, *args):
            return

    import time
    server = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
    server.timeout = 30
    deadline = time.time() + 600
    while "code" not in auth_code and time.time() < deadline:
        server.handle_request()

    code = auth_code.get("code")
    if not code:
        print("Nenhum codigo OAuth recebido.", flush=True)
        return 1

    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=token_data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        tokens = json.loads(resp.read().decode("utf-8"))

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(f"Erro ao obter refresh_token: {tokens}", flush=True)
        return 1

    env_path = Path(__file__).resolve().parents[1] / ".env"
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = [
        ln for ln in existing.splitlines()
        if not ln.startswith(("YT_CLIENT_ID=", "YT_CLIENT_SECRET=", "YT_REFRESH_TOKEN=", "YT_PRIVACY_STATUS="))
    ]
    lines.extend([
        f"YT_CLIENT_ID={client_id}",
        f"YT_CLIENT_SECRET={client_secret}",
        f"YT_REFRESH_TOKEN={refresh_token}",
        f"YT_PRIVACY_STATUS={os.getenv('YT_PRIVACY_STATUS', 'public')}",
    ])
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nCredenciais salvas em {env_path}! Pronto para enviar Shorts.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
