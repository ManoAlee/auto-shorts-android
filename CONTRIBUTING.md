# Contributing to `auto-shorts-android`

Thank you for helping improve `auto-shorts-android`!

## Development Workflow

1. **Fork & Branch:** Create focused branches (`feat/<scope>`, `fix/<scope>`).
2. **Environment Setup:**
   ```bash
   cp .env.example .env
   pip install pytest
   ```
3. **Engineering Guidelines:**
   - Keep zero mandatory heavy runtime dependencies (no PyTorch/Docker requirement) so Android Termux `aarch64` stays fast.
   - Maintain single-purpose helpers, structured API error payloads (`_send_error`), and deterministic validation checks.
   - **Never** commit `.env`, API keys, OAuth tokens, `.db`, `.gguf`, `.mp4`, or compiled binaries.
4. **Verification Gate (Required Before PR):**
   ```bash
   python -m pytest tests -q
   node --check src/auto_shorts/frontend/studio.js
   ```
