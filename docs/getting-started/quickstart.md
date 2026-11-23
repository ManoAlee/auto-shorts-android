# Quickstart Guide

Get up and running with AutoShorts in less than 5 minutes. This guide covers your first automated video render and starting the interactive Web Studio.

---

## 1. Quick Video Generation (CLI)

The fastest way to generate an end-to-end vertical short (9:16) with neural Portuguese TTS, dynamic subtitles, and B-Roll is via the command-line interface:

```bash
# Generate a tech news short with Sentinel Pre-Render validation
python main.py --niche mundo --duration 45 --out output
```

### What happens during execution:
1. **Trend Ingestion:** AutoShorts reads live RSS feeds (Tecnoblog, BBC Brasil, Canaltech) and filters out stubs.
2. **Mahoraga 3-Act Scripting:** The story engine writes Act 1 (The Hook), Act 2 (The Tension/Story), and Act 3 (The Takeaway).
3. **Neural Narration:** Kokoro-82M (or Edge-TTS fallback) synthesizes natural PT-BR speech.
4. **Auto-Transcribe & Subtitles:** Aligns audio tokens into word-level CapCut-style subtitles.
5. **Sentinel Pre-Render QA:** 10 automated Quality Gates validate title-content coherence, audio levels, scene pacing, and visual framing.
6. **Hardware Render:** FFmpeg stitches vertical B-Roll with dynamic subtitles, audio ducking, and cover poster export.
7. **Vault Ingestion:** The final video and metadata pack (`.publish.json`) are stored in `output/`.

---

## 2. Launching Web Studio

AutoShorts includes a responsive, zero-framework Web Studio with dark mode, live telemetry, and video library management:

```bash
python main.py --serve --port 8787
```

- **Local Access:** Open your browser to `http://127.0.0.1:8787`
- **Android Mobile Access:** Open Chrome on your phone to `http://localhost:8787`

### Key Studio Features:
- **Criar Vídeo:** Single-click generation with custom topics, platform presets (TikTok, Shorts, Reels), and voice selection.
- **Sentinel QA Panel:** Real-time pre-render quality scores, gate breakdowns, and automated remediation feedback.
- **Meus Vídeos (Vault):** Comprehensive library of generated shorts, preview playback, technical scores, and publish queue triggers.
- **Tendências & Radar:** Live radar monitoring high-engagement topics from Brazilian and global news sources.
- **Piloto Automático:** 24/7 background worker that schedules and produces shorts at configured intervals.

---

## 3. Generating a Viral News Short

To specifically generate a viral news short from current RSS headlines:

```bash
python -c "from auto_shorts.world_news import produce_world_news_short; produce_world_news_short('output', niche='mundo')"
```

The resulting file will be saved in `output/mundo_br_<timestamp>.mp4` alongside its 16:9 and 9:16 thumbnail posters.
