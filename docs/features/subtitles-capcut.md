# Kinetic Subtitles & CapCut-Style Animations

High audience retention on vertical video platforms requires dynamic, readable, and visually engaging captions. AutoShorts includes a native subtitle synthesis engine producing CapCut-style typography.

---

## 1. Architecture of the Subtitle Pipeline

```text
Spoken Audio (WAV)
       │
       ▼
Audio Token Alignment (Timestamp extraction per word)
       │
       ▼
ASS (Advanced SubStation Alpha) Generation
├── Font Family: Montserrat ExtraBold / Arial Black
├── Primary Color: #FFFFFF (Clean White)
├── Active Karaoke Accent: #FFD700 (Vibrant Gold) / #00FFAA (Cyan)
├── High-Contrast Outline: 3px Solid Black (#000000)
└── Positioning: Bottom-Center (within 9:16 platform safe zone)
       │
       ▼
FFmpeg Hardware Overlay (-vf "subtitles=...")
```

---

## 2. Safe-Zone Compliance

Vertical social platforms (TikTok, Instagram Reels, YouTube Shorts) overlay interactive buttons, profile handles, and sound titles over portions of the screen.

AutoShorts places subtitles strictly inside the verified **Safe Visual Box**:
- **Top Margin:** 200px clear (avoids platform search bars and live status).
- **Bottom Margin:** 320px clear (avoids platform engagement icons, caption text, and sound ribbons).
- **Left/Right Margins:** 70px side padding (prevents truncation on curved mobile displays).

---

## 3. Kinetic Word-by-Word Highlighting

Instead of rendering static paragraphs, the subtitle engine segments speech into short 3 to 5 word bursts with real-time active-word coloring, maintaining viewer visual engagement throughout the entire video.
