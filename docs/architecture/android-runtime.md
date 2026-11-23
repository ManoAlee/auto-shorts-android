# Android Termux ARM64 Runtime Architecture

AutoShorts is optimized specifically for the unique physical and kernel characteristics of Android devices running under Termux on 64-bit ARM architectures (aarch64).

---

## 1. Hardware Baseline & Constraints

Tested reference hardware: **Samsung Galaxy A55 5G**
- **SoC:** Samsung Exynos 1480 (4x Cortex-A78 @ 2.75 GHz, 4x Cortex-A55 @ 2.0 GHz)
- **GPU / NPU:** Xclipse 530 (AMD RDNA2 architecture)
- **RAM:** 8 GB LPDDR5
- **OS:** Android 14 (One UI 6.1)
- **Userland:** Termux aarch64 (glibc-free bionic libc environment)

---

## 2. Runtime Optimizations

### Wake Lock Management
Android's aggressive power manager (`Doze Mode`) suspends background CPU cycles within minutes of screen timeout. AutoShorts manages wake locks via `termux-wake-lock`:
- Keeps big cores active during FFmpeg encoding passes.
- Automatically releases on shutdown or idle periods.

### Thermal Throttling Mitigation
Continuous high-frequency video encoding triggers thermal throttling on mobile SoCs. The AutoShorts render pipeline:
- Utilizes balanced FFmpeg presets (`-preset ultrafast` or `-preset veryfast` for h264).
- Batches chunk processing with micro-sleep intervals during bulk generation.
- Enforces single-instance encoding locks (`render.lock`) to prevent concurrent encoding spikes.

### Memory Ceiling & Swap Protection
Android's Low Memory Killer (LMK) abruptly terminates processes exceeding memory thresholds:
- Python scripts enforce streaming file reads rather than buffering full media into memory.
- In-memory video frames are avoided; FFmpeg processes filtergraphs directly on disk streams.
- Maximum RAM usage during full 1080x1920 render is bounded to **<350 MB**.

---

## 3. Storage Hierarchy & Circular Retention

```text
/data/data/com.termux/files/home/auto-shorts-android/
├── assets/          <- Static B-roll loops and reference audio (read-only)
├── output/          <- Active video vault and thumbnail posters
│   ├── *.mp4        <- Master rendered videos
│   ├── *.publish.json <- Metadata, Sentinel scores, SEO tags
│   └── sentinel/    <- Pre-render diagnostic reports
└── scripts/         <- Operational shell and automation harnesses
```

The circular retention policy monitors both count (`STORAGE_MAX_VIDEOS=20`) and total volume (`STORAGE_MAX_MB=1200`). When limits are reached, the oldest published or lowest-scoring non-favorited videos are cleanly purged.
