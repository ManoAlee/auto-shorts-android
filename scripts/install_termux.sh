#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "[1/5] Updating Termux repositories and installing multimedia + AI packages..."
pkg update -y
pkg install -y ffmpeg python python-yt-dlp yt-dlp-ejs fontconfig ttf-dejavu git cmake clang make llama-cpp

echo "[2/5] Creating mobile AI directory structure..."
mkdir -p "$HOME/models/llm" "$HOME/models/whisper" "$HOME/auto-shorts-android/output"

echo "[3/5] Setting up shared Android storage symlink (optional)..."
if [ ! -d "$HOME/storage" ]; then
  termux-setup-storage || true
fi

if [ "${INSTALL_WHISPER_CPP:-0}" = "1" ]; then
  echo "[4/5] Building whisper.cpp natively for ARM64 (GGML_NO_OPENMP=ON)..."
  WHISPER_DIR="$HOME/whisper.cpp"
  if [ ! -d "$WHISPER_DIR" ]; then
    git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
  fi
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" -DGGML_NO_OPENMP=ON
  cmake --build "$WHISPER_DIR/build" -j4
  ln -sf "$WHISPER_DIR/build/bin/whisper-cli" "$PREFIX/bin/whisper-cli"

  MODEL_DIR="$HOME/models/whisper"
  if [ ! -f "$MODEL_DIR/ggml-base-q5_1.bin" ]; then
    bash "$WHISPER_DIR/models/download-ggml-model.sh" base-q5_1 "$MODEL_DIR"
  fi
else
  echo "[4/5] Skipping whisper.cpp build (run with INSTALL_WHISPER_CPP=1 to compile offline ASR)."
fi

echo "[5/5] Verifying toolchain..."
ffmpeg -version | head -n 2
yt-dlp --version
python --version
llama-cli --version | head -n 2 || true
echo "Ready! Run: python main.py --help"
