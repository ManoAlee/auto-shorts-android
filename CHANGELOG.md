# Changelog

All notable changes to **auto-shorts-android** are documented in this file.

## [2.6.0] - 2026-11-12

### Added
- **Mahoraga 8-Spoke Adaptive Intelligence Engine (`src/auto_shorts/mahoraga.py`):** SQLite-backed adaptive wheel (`mahoraga_adaptations`, `mahoraga_speech_ledger`) rotating 8 distinct narrative cadences across `world_news.py`, `horizon_radar.py`, and `story_engine.py` so consecutive videos never repeat the same speech formula.
- **Word-Boundary & Dangling-Token Hook Guard (`clean_word_boundary_hook`):** Strips conversational lead-ins, placeholders (`4 WORDS IN CAPS`), and trailing prepositions/verbs (`"após"`, `"sobre"`, `"escrever"`), turning truncated titles into complete hooks (`"CEO DA NVIDIA RENUNCIA"`, `"SOFTWARE CORRETO É DIFÍCIL"`).
- **3-Stage FFmpeg Auto-Heal (`renderer.py`) & Autopilot Recovery (`webapp.py`):** Automatic fallback from `punch_zoom`/overlay failures (`exit 254`) to clean `libx264` + `blur_bg`, plus automatic niche advancement and `world_news` fallback when an autopilot source fails.
- **Live Mahoraga Telemetry (`GET /api/mahoraga`, `/api/status`, Studio UI):** Real-time wheel turn counter and active Roman spoke indicator in the Web Studio.
- **Upgraded Visual GitHub Documentation (`README.md`, `docs/MAHORAGA_ADAPTIVE_ENGINE.md`, `docs/images/mahoraga-adaptive-engine.jpg`):** Full Studio gallery, Mahoraga architecture infographic, immunity matrix, and API reference.

### Fixed
- **Non-Gaming Visual Shield (`gameplay.py`, `narrator.py`):** Blocked brainrot gameplay styles (`minecraft`, `subway`, `gta_ramp`, `beamng`) outside `niche="gameplay"` and added `niche` filtering to `_build_multiscene_broll()`.
- **TikTok Creator Rewards 180s Validation (`validator.py`, `pipeline.py`, `re_engine.py`, `yt_algorithm.py`):** Allowed `60s–180s` clips for `tiktok_rewards` without failing the 60s YouTube Shorts cap.
- **Bare Feed Extraction (`world_news.py`):** Scrapes real article paragraphs and `og:image` when feeds like Hacker News provide only a bare headline (`summary == title`), eliminating duplicate title/summary narration.

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

