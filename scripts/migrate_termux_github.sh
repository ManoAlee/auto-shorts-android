#!/data/data/com.termux/files/usr/bin/bash
# Specialist Restore Script — Termux Oficial (GitHub v0.118.3+) + Termux:Boot + Termux:API
# Restaura 100% do ambiente AutoShorts sem perder chaves SSH, modelos, .env, banco ou MP4s.
set -euo pipefail

BACKUP_DIR="/sdcard/Download/TermuxMigracao"
ARCHIVE="$BACKUP_DIR/termux_home_backup.tar"

if [ ! -f "$ARCHIVE" ]; then
  echo "[ERRO] Backup nao encontrado em $ARCHIVE"
  echo "Rode primeiro termux-setup-storage e aceite a permissao de arquivos."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
APT_OPTS=(-y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold")

echo "[1/7] Atualizando repositorios oficiais Termux..."
apt-get update -y
apt-get "${APT_OPTS[@]}" upgrade

echo "[2/7] Instalando pacotes nativos (Python, FFmpeg, Clang, SSH, Services, Termux-API)..."
apt-get "${APT_OPTS[@]}" install root-repo tur-repo
apt-get update -y
apt-get "${APT_OPTS[@]}" install \
  bash ca-certificates cmake coreutils curl dos2unix espeak ffmpeg fontconfig \
  gh git htop nano net-tools nodejs-lts openssh openssl patch procps \
  python python-numpy python-yt-dlp yt-dlp-ejs tar termux-am termux-api \
  termux-exec termux-services termux-tools ttf-dejavu unzip clang make llama-cpp || true

echo "[3/7] Restaurando \$HOME completo ($ARCHIVE)..."
cd "$HOME"
tar -xpf "$ARCHIVE" -C "$HOME"

chmod 700 "$HOME/.ssh" 2>/dev/null || true
chmod 600 "$HOME/.ssh/"* 2>/dev/null || true
chmod 644 "$HOME/.ssh/"*.pub 2>/dev/null || true
chmod +x "$HOME/.termux/boot/"*.sh 2>/dev/null || true
chmod +x "$HOME/.shortcuts/"*.sh 2>/dev/null || true
chmod +x "$HOME/auto-shorts-android/scripts/"*.sh 2>/dev/null || true

echo "[4/7] Restaurando dependencias Python (edge-tts, pytest) e binarios nativos..."
pip install --no-cache-dir -U edge-tts pytest || true
if [ -d "$HOME/auto-shorts-android/native-c" ]; then
  make -C "$HOME/auto-shorts-android/native-c" -B install-termux
  ln -sf "$HOME/auto-shorts-android/bin/media_audit" "$PREFIX/bin/media_audit"
fi
if [ -x "$HOME/whisper.cpp/build/bin/whisper-cli" ]; then
  cat > "$PREFIX/bin/whisper-cli" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export LD_LIBRARY_PATH="$HOME/whisper.cpp/build/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HOME/whisper.cpp/build/bin/whisper-cli" "$@"
EOF
  chmod +x "$PREFIX/bin/whisper-cli"
fi

echo "[5/7] Configurando supervisor runit (sshd + autoshorts)..."
mkdir -p "$PREFIX/var/service/autoshorts/log"
cat > "$PREFIX/var/service/autoshorts/run" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec 2>&1
termux-wake-lock 2>/dev/null || true
cd "$HOME/auto-shorts-android" || exit 1
if [ -x "$HOME/auto-shorts-android/bin/autoshorts" ]; then
  exec "$HOME/auto-shorts-android/bin/autoshorts" watch 30
fi
exec python main.py --serve --port 8787
EOF
chmod +x "$PREFIX/var/service/autoshorts/run"

sv-enable sshd 2>/dev/null || true
if [ -f "$PREFIX/etc/profile.d/start-services.sh" ]; then
  . "$PREFIX/etc/profile.d/start-services.sh" 2>/dev/null || true
fi
pgrep -x sshd >/dev/null 2>&1 || sshd 2>/dev/null || true

echo "[6/7] Ativando Wake-Lock, storage, notificacao persistente e testes..."
termux-wake-lock 2>/dev/null || true
if command -v termux-notification >/dev/null 2>&1; then
  termux-notification --id autoshorts --title "AutoShorts Pro Ativo" --content "Studio :8787 + Watchdog rodando em segundo plano" --ongoing 2>/dev/null || true
fi

bash "$HOME/auto-shorts-android/scripts/start_webapp.sh" 8787
cd "$HOME/auto-shorts-android"
python -m pytest tests -q

echo "[7/7] CONCLUIDO! Acesse no PC:"
python -c "import getpass, socket; s=socket.socket(2,2); s.connect(('1.1.1.1',80)); ip=s.getsockname()[0]; s.close(); u=getpass.getuser(); print(f'http://{ip}:8787/  (SSH: ssh -p 8022 {u}@{ip})')"

