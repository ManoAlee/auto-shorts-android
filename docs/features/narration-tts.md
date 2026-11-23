# Neural Voice & TTS Engine

AutoShorts features a pluggable text-to-speech architecture supporting offline on-device neural synthesis as well as cloud-grade voice cloning.

---

## 1. Supported Voice Engines

| Engine | Deployment | Latency (ARM64) | Internet Required | Quality |
|---|---|---|---|---|
| **Kokoro-82M PT-BR** | On-Device ONNX | ~1.2x realtime | ❌ No (100% Offline) | High Neural Natural |
| **Edge-TTS** | Microsoft Edge API | ~0.4x realtime |  Yes | Studio Brazilian Voice |
| **OpenAI TTS** | Cloud API | ~0.5x realtime |  Yes | Premium Studio Broadcast |
| **ElevenLabs** | Cloud API | ~0.8x realtime |  Yes | Ultra-Realistic Cinematic |
| **GPT-SoVITS** | Local LAN Server | ~1.5x realtime | ❌ No (LAN) | Zero-Shot Voice Clone |
| **F5-TTS** | Local LAN Server | ~1.8x realtime | ❌ No (LAN) | Flow Matching Voice Clone |

---

## 2. Kokoro-82M On-Device Offline Setup

Kokoro-82M is the default offline engine for Android ARM64, providing high-fidelity Brazilian Portuguese speech synthesis directly inside Termux:

```bash
# Run one-time Kokoro setup script
bash scripts/install_kokoro_ptbr.sh
```

### Technical Characteristics:
- Model size: ~82M parameters (ONNX quantized weights <180 MB).
- Native Portuguese phonemization via `phonemizer` and custom stress rules.
- Memory footprint: ~150 MB RAM during synthesis.
- Zero API costs, zero privacy leakage, fully operational without cellular connectivity.

---

## 3. Cloud & Studio Fallback

When configured via `.env`, AutoShorts seamlessly routes synthesis requests through premium cloud providers while maintaining graceful fallback to Edge-TTS or Kokoro should network failures occur.
