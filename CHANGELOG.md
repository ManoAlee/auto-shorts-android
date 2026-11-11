# Changelog

All notable changes to **auto-shorts-android** are documented in this file.

## [2.5.0] - 2026-11-11

### Added
- **Modular Web Studio UX (`src/auto_shorts/frontend/`):** Sidebar rail navigation, persistent 5-stage live render stepper (`1. Coleta` -> `5. Fila/YT`) with floating scroll dock, interactive 9:16 layout simulator (`blur_bg`, `split_top_bottom`, `center_crop`) with YouTube thumbnail auto-preview, segmented Top-6 Radar feed, accessible `<dialog>` inspector, and toast notifications.
- **Offline Edge-LLM & BM25 Engine (`offline_llm.py`):** ARM64 ISA probing (`dotprod`/`asimddp`, `fp16`/`asimdhp`, `i8mm`, `sve`), RAM-tiered GGUF recommendations, `<think>`/`<thought>` CoT tag stripping, pure-Python BM25 local RAG, `/api/ai/benchmark`, `/api/ai/chat`, and OpenAI-compatible LAN endpoints (`GET /v1/models`, `POST /v1/chat/completions`).
- **Humanized PT-BR Voice Pipeline (`narrator.py`):** CosyVoice 3.0 & FalaBrasil spoken text normalization (`R$`, `%`, `IA`, `EUA`, `STF`, `km/h`), broadcast vocal warmth EQ + de-esser post-processing, and CC-BY-SA Open-Swara Portuguese reference voice support (`assets/voices/`).
- **Zero-Cache HTTP & REST Contracts (`webapp.py`):** `Cache-Control: no-store` headers, status/query pagination on `GET /api/videos`, structured `_send_error()` payloads, and duplicate Short queue prevention.
- **C# Desktop Controller Updates (`desktop-cs/AutoShortsDesktop.cs`):** Deterministic `IDisposable` process/HTTP cleanup, structured error parsing, Opus Scorecard inspection, and batch audit/optimize trigger.

### Fixed
- Upgraded `llama-cli` fallback flag from deprecated `-no-cnv` to `--single-turn` with clean ChatML assistant parsing.
- Fixed semantic topic routing in `build_horizon_spoken_script()` so AI/Tech topics never receive personal-finance boilerplate.
- Fixed English title detection (`_looks_english_title`), `>>` / greeting sanitization in `_polish_hook_phrase`, and `.ass` persistence on clipped YouTube Shorts.

