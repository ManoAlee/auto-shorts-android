#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

cd "$HOME/auto-shorts-android"
timeout 3 termux-wake-lock >/dev/null 2>&1 || true

# Start local 1.1GB Qwen2.5 server only when explicitly requested (START_LOCAL_LLM=1)
# or when no cloud free LLM key (OPENROUTER_API_KEY / GEMINI_API_KEY) is configured,
# avoiding Android OOM pressure during concurrent Whisper + FFmpeg renders.
HAS_CLOUD_LLM=0
if [ -f ".env" ] && grep -qE '^(OPENROUTER_API_KEY|GEMINI_API_KEY)=.+' ".env"; then
  HAS_CLOUD_LLM=1
fi

LLM_MODEL="${LLM_MODEL:-$HOME/models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf}"
if [ "${START_LOCAL_LLM:-0}" = "1" ] || [ "$HAS_CLOUD_LLM" = "0" ]; then
  if command -v llama-server >/dev/null 2>&1 && [ -f "$LLM_MODEL" ]; then
    if ! pgrep -f "llama-server.*8080" >/dev/null 2>&1; then
      setsid llama-server -m "$LLM_MODEL" --host 127.0.0.1 --port 8080 -t 4 -c 2048 > "$HOME/auto-shorts-android/output/llama.log" 2>&1 < /dev/null &
      sleep 2
    fi
  fi
fi

pkill -f "main.py --serve" 2>/dev/null || true
pkill -f "termux-api Notification" 2>/dev/null || true
sleep 1
nohup setsid python main.py --serve --port "${1:-8787}" > "$HOME/auto-shorts-android/output/webapp.log" 2>&1 < /dev/null &
sleep 2
curl -s -o /dev/null -w "HTTP:%{http_code}\n" "http://127.0.0.1:${1:-8787}/"

if [ -x "$HOME/auto-shorts-android/bin/autoshorts" ]; then
  if ! pgrep -f "autoshorts watch" >/dev/null 2>&1; then
    nohup setsid "$HOME/auto-shorts-android/bin/autoshorts" watch 30 > "$HOME/auto-shorts-android/output/watchdog.log" 2>&1 < /dev/null &
  fi
fi

if command -v termux-notification >/dev/null 2>&1; then
  CUR_IP=$(python -c "import socket; s=socket.socket(2,2); s.connect(('1.1.1.1',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1")
  timeout 3 termux-notification --id autoshorts --title "AutoShorts Pro Ativo" --content "Acesse: http://${CUR_IP}:${1:-8787}/ (Cockpit + Kokoro PT-BR)" --ongoing </dev/null >/dev/null 2>&1 || true
fi
