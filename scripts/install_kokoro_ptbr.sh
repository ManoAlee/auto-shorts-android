#!/usr/bin/env bash
# Instalador oficial do Kokoro-82M ONNX PT-BR (StyleTTS 2 humano, 100% offline em ARM64/Desktop)
set -euo pipefail

TTS_DIR="${HOME}/models/tts"
mkdir -p "$TTS_DIR"

echo "[1/3] Instalando dependencias kokoro-onnx (mantendo onnxruntime do Termux se existir)..."
if command -v pkg >/dev/null 2>&1; then
  pkg install -y espeak python-onnxruntime || true
  pip install --no-deps --no-cache-dir -U kokoro-onnx || true
  pip install --no-cache-dir -U phonemizer colorlog || true
else
  pip install --no-cache-dir -U kokoro-onnx
fi

echo "[2/3] Baixando pesos Kokoro-82M INT8 (108 MB) e pacote de vozes PT-BR (26 MB)..."
curl -fL --retry 3 -o "$TTS_DIR/kokoro-v1.0.int8.onnx" \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx"
curl -fL --retry 3 -o "$TTS_DIR/voices-v1.0.bin" \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"

echo "[3/3] Pronto! Vozes PT-BR disponiveis offline: pm_alex, pm_santa, pf_dora"
ls -lh "$TTS_DIR"

