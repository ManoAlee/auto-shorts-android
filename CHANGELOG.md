# Changelog

All notable changes to **auto-shorts-android** are documented in this file.

## [2.8.0] - 2026-11-13

### Added
- **Instagram Niche Auto-Highlights (`publisher.py`):** Automatically organizes published Reels into niche-specific Highlights (`_resolve_highlight_title`, `_auto_add_reel_to_highlight`).
- **Post-Publish Audit Engine (`publisher.py`, `webapp.py`):** Added `verify_published_post()`, `audit_published_vault()`, and `GET /api/publish/audit` to compute `thumbnail_sha256` across sibling packs, detect duplicate thumbnails, and verify live media state.
- **Public Tunnel Discovery (`webapp.py`):** Added `_read_tunnel_url()`, `GET /api/tunnel`, and `tunnel_url` in `GET /api/system`.
- **Strict Wi-Fi-Only Guard & Autopublish Mutex (`smart_autopublish.py`):** Added `is_wifi_connected()` (`SIOCGIFADDR` ioctl on `wlan0`/`wlan1`, enforced via `WIFI_ONLY=1` or on Termux) so mobile/4G data is never consumed, plus `_AUTOPUBLISH_LOCK` around `run_smart_publish_cycle()` to prevent duplicate concurrent posts.

### Fixed
- **Black-Screen Instagram Stories & Highlights (`publisher.py`):** Replaced black `media_share_to_story` canvas with real 9:16 video uploads via `cl.video_upload_to_story(..., thumbnail=thumb_path)` and `cover_story_id=story_pk` (with `TypeError` fallback).
- **Stale Reel Thumbnails (`publisher.py`):** Updated `_ensure_reel_thumbnail()` to invalidate stale `.mp4.jpg` files (`mtime < mp4.mtime`), prefer fresh `_cover_9x16.jpg`, or extract a frame at ~22% duration via `ffprobe`/`ffmpeg`.
- **Incoherent Thumbnail Hook Titles (`highlights.py`):** Updated `_polish_hook_phrase()` and `_pick_best_hook()` to reject conversational fragments (`"a gente "`, `"eu "`, `"você "`, `"pessoal "`, `"aconteceu "`, `"o que "`, `"não "`) and require niche keyword relevance (`best_score >= 6` and `best_has_kw`) before overriding `src_hook`.
- **YouTube/TikTok Publishing Hardening (`publisher.py`):** Enforced upload idempotency, `#Shorts` tag guarantee, caption sanitization, and `.env` token refresh.

## [2.7.0] - 2026-11-12

### Added
- **Full Anime Episode Engine (`src/auto_shorts/anime_archive_downloader.py`):** Zero-auth, pure-Python scraper for Archive.org and AnimesDigital without requiring Selenium or heavy browser runtimes on mobile. Fetches 1080p/720p direct MP4 streams for complete sagas (*Yu Yu Hakusho*, *Dragon Ball Z*, *Naruto*, *Cavaleiros do Zodíaco*, *Death Note*).
- **Intelligent Long-Episode Slicing Pipeline (`pipeline.py`, `highlights.py`):** Automatic skipping of opening (OP) and ending (ED) sequences (90s windowing), energetic dialogue/climax detection, authentic Brazilian dubbing preservation (zero synthetic voice overlay), and ITU-R BS.1770-4 loudness normalization (-14 LUFS).
- **Dual-Cycle Autonomous Sentinel (`sentinel.py`, `world_news.py`):** When Google Drive has no pending raw files, the engine autonomously alternates 50/50 between slicing dubbed anime episodes from the web and generating investigative tech incident Shorts with verified Root Cause Analysis (RCA).
- **Web Studio Episode Search UI (`src/auto_shorts/frontend/`):** Added `🎬 Buscar Episódios Dublados` action button, interactive search modal (`#modal-anime-search`), and REST API `GET /api/animes/search?q={query}`.
- **Breaking News RCA Integration:** Live incident feeds (Google News Cloud Outage, Tecnoblog, BleepingComputer) and automated root-cause extraction. Successfully rendered and published global Microsoft 365 outage Short (`EX1550543` / `MO1550821`) live to YouTube Shorts ([p3Vya4M49a4](https://youtube.com/shorts/p3Vya4M49a4)).
- **Comprehensive Documentation (`docs/MOTOR_AUTONOMO_EPISODIOS_E_INCIDENTES.md`):** Complete guide detailing the 24/7 autonomous loop, episode slicing mechanics, audio safeguards, and operational commands.

### Fixed
- **Ephemeral Storage Auto-Purge:** Automatic cleanup of large raw episode source files in `_work_*` directories after slicing to prevent storage exhaustion on Android.
- **YouTube Token Environment Loading (`publisher.py`):** Loaded `.env` at module level to guarantee client credentials are valid across standalone scripts.

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

