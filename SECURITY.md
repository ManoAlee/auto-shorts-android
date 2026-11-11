# Security Policy

## Reporting a Vulnerability

Please **do not** open public GitHub issues for credential leaks, RCE vectors, or authentication bypasses.
Report security issues privately via GitHub Security Advisories (`Security -> Advisories -> Report a vulnerability`) or direct contact with `@ManoAlee`.

## Hardening & Operational Guardrails

- **No Secrets in VCS:** `.env`, OAuth tokens (`YT_REFRESH_TOKEN`), API keys (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`), and `.publish.json` runtime queues are excluded by `.gitignore`.
- **Path & SSRF Validation:** All media routes (`/media/*`, `/media-preview/*`, `/api/trim`, `/api/delete`) validate child paths via `_safe_child_path()` (`^[A-Za-z0-9._-]{1,128}$`) and filter external URLs via `_is_safe_public_http_url()`.
- **Remote Cloudflare Tunnel Auth:** Access through `*.trycloudflare.com` enforces an HttpOnly per-session secret token (`studio_tok`) checked with `secrets.compare_digest`.

