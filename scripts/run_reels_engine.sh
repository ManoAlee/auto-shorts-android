#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

cd "$HOME/auto-shorts-android"
termux-wake-lock 2>/dev/null || true

NICHE="${1:-entretenimento_animes}"
CLIPS="${2:-1}"

echo "[Reels Engine] Nicho=$NICHE | Cortes=$CLIPS | Retencao Inteligente ATIVA"
python main.py --discover --niche "$NICHE" --platform instagram_reels --clips "$CLIPS" --auto-count 1 --auto-layout --offline

