# Web Studio & Telemetry Dashboard

AutoShorts features a built-in Single-Page Application (SPA) Web Studio, designed with modern dark-mode aesthetics, zero runtime framework dependencies, and full mobile optimization.

---

## 1. Architecture

The Web Studio is powered by an embedded Python HTTP server (`src/auto_shorts/webapp.py`) serving a vanilla HTML5, CSS Variables, and JavaScript bundle:
- **Design System:** Custom CSS design tokens defined in `src/auto_shorts/frontend/tokens.css`.
- **Zero Third-Party CDNs:** All icons, styles, fonts, and scripts are embedded locally for 100% offline mobile usability.
- **Server-Sent Events (SSE) & REST:** Real-time generation progress, background worker telemetry, and status polling without page reloads.

---

## 2. Visual Navigation & Views

| View ID | Title | Description |
|---|---|---|
| `#panel-cortes` | **Criar Vídeo** | Manual video creation interface with topic input, duration sliders, niche selection, voice preview, and instant render trigger. |
| `#panel-sentinel` | **Sentinel QA** | Real-time multimodal quality inspection dashboard displaying all 10 Quality Gates, individual metrics, and diagnostic remediation reports. |
| `#panel-videos` | **Meus Vídeos (Vault)** | Media library displaying all generated MP4s with 16:9 thumbnails, technical scores, duration chips, and single-click publish buttons. |
| `#panel-synapse` | **Tendências & Radar** | Live news feed monitoring, trending topics in Brazil and globally, and direct story pack generation. |
| `#panel-equipe` | **Piloto Automático** | Autonomous scheduling engine configuration, interval controls, and background worker state. |
| `#panel-sistema` | **Configurações & Status** | System health telemetry, Kokoro-82M status, FFmpeg configuration, storage quotas, and remote tunnel link. |

---

## 3. Mobile First Responsive Layout

When accessed on mobile screens (<768px), the Web Studio dynamically adapts:
- Header collapse into a compact brand bar.
- Fixed bottom navigation bar with thumb-accessible icons.
- Single-column card layout with touch-friendly controls.
