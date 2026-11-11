#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

cd "$HOME/auto-shorts-android"
termux-wake-lock 2>/dev/null || true

NICHE="${1:-entretenimento_animes}"
PLATFORM="${2:-tiktok_rewards}"
CLIPS="${3:-2}"

echo "[Autopilot] Buscando e cortando video real para nicho=$NICHE platform=$PLATFORM..."
python main.py --discover --niche "$NICHE" --platform "$PLATFORM" --clips "$CLIPS" --auto-count 1 --offline

