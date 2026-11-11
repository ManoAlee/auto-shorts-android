#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

MODEL_PATH="${1:-$HOME/models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
PORT="${LLAMA_PORT:-8080}"
THREADS="${LLAMA_THREADS:-4}" # 4x Cortex-A78 performance cores on Exynos 1480 (SM-A556E)
CTX="${LLAMA_CTX:-2048}"

if ! command -v llama-server >/dev/null 2>&1; then
  echo "[ERR] llama-server not found. Install with: pkg install -y llama-cpp" >&2
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "[ERR] GGUF model not found at: $MODEL_PATH" >&2
  echo "Download example (Qwen2.5-1.5B-Instruct Q4_K_M ~1.1GB):" >&2
  echo "  llama-cli -hf Qwen/Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M -n 1 -p 'ok'" >&2
  exit 1
fi

echo "[INFO] Starting llama-server on 127.0.0.1:$PORT (threads=$THREADS, ctx=$CTX)"
exec llama-server -m "$MODEL_PATH" --host 127.0.0.1 --port "$PORT" -t "$THREADS" -c "$CTX"

