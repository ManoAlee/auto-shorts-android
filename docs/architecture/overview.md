# System Architecture Overview

AutoShorts is an autonomous audiovisual production platform engineered for resource-constrained mobile environments (Android Termux ARM64) and high-throughput production workstations.

---

## 1. High-Level Subsystem Architecture

```mermaid
flowchart TD
    subgraph INGESTION["1. Content Discovery & Intelligence"]
        RSS["RSS News Feeds<br/>(BBC, Tecnoblog, Canaltech)"]
        TRENDS["Global Trends Radar<br/>(YouTube / TikTok / Google)"]
        VIRAL_TITLES["Viral Titling Engine<br/>(CTR & Hook Heuristics)"]
    end

    subgraph CREATIVE["2. Narrative & Voice Studio"]
        MAHORAGA["Mahoraga 3-Act Engine<br/>(Hook / Story / Tension)"]
        TTS["Neural TTS Pipeline<br/>(Kokoro-82M / Edge-TTS / ElevenLabs)"]
        SUBTITLES["Kinetic Subtitles Engine<br/>(Word-level Alignment & Colors)"]
    end

    subgraph VALIDATION["3. Pre-Render Validation"]
        SENTINEL["Sentinel Pre-Render Orchestrator<br/>(10 Quality Gates & Scoring)"]
        SENT_REP["Diagnostic Report & Gate Decisions<br/>(APPROVE / REJECT / REMEDIATE)"]
    end

    subgraph RENDER["4. Video Composition & Render"]
        BROLL["Vertical B-Roll Catalog<br/>(Ambient / Dynamic Loops)"]
        FFMPEG["FFmpeg ARM64 Pipeline<br/>(Filtergraphs, Ducking, 1080x1920)"]
        POSTERS["Thumbnail & Poster Exporter<br/>(16:9 & 9:16 Visual Covers)"]
    end

    subgraph DISTRIBUTION["5. Vault & Multiplatform Publish"]
        VAULT["Video Vault Library<br/>(Metadata, Scores, Retention Guard)"]
        PUBLISH["Publish Orchestrator<br/>(TikTok API, YouTube API, Reels, Webhook)"]
        STUDIO_UI["Web Studio & Mobile UI<br/>(SPA Dashboard, SSE Telemetry)"]
    end

    RSS --> MAHORAGA
    TRENDS --> VIRAL_TITLES
    VIRAL_TITLES --> MAHORAGA
    MAHORAGA --> TTS
    TTS --> SUBTITLES
    SUBTITLES --> SENTINEL
    SENTINEL --> SENT_REP
    SENT_REP -->|Approved| FFMPEG
    BROLL --> FFMPEG
    FFMPEG --> POSTERS
    POSTERS --> VAULT
    VAULT --> PUBLISH
    VAULT --> STUDIO_UI
```

---

## 2. Core Architectural Principles

### Zero External Server Dependency
The entire pipeline runs locally on an Android device running Termux. Voice synthesis, transcript alignment, video composition, and thumbnail generation execute on-device without requiring hosted cloud servers.

### Pre-Render Quality Gating (Fail-Fast)
Rendering 1080x1920 60fps video on mobile hardware costs 30 to 60 seconds of compute and battery life. AutoShorts executes the **Sentinel Pre-Render** engine *before* invoking FFmpeg, inspecting script metrics, audio dynamics, narrative pacing, and title promises. Flawed content is rejected or repaired in milliseconds.

### Storage & Memory Guardrails
Mobile devices have hard physical limits on RAM and flash write cycles. AutoShorts enforces strict circular quotas (`STORAGE_MAX_VIDEOS`, `STORAGE_MAX_MB`), automated orphan cleanup, and streaming pipeline execution to eliminate out-of-memory kernel kills.
