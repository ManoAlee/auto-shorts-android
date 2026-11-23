# Installation Guide

AutoShorts Android is engineered to run as a native, self-contained audiovisual studio on **Android 14+ ARM64 (via Termux)** with zero external server dependencies, and is fully portable to **Linux x86_64** and **Windows 11** workstations.

---

## 1. Primary Target: Android Termux (ARM64)

### Prerequisites
- Android 10+ (tested extensively on Android 14 / Samsung Exynos 1480).
- [Termux](https://github.com/termux/termux-app) (from GitHub releases or F-Droid, never Google Play).
- Minimum 3 GB free internal storage.
- Stable Wi-Fi or mobile data connection for initial package installation.

### Automated One-Liner Setup
Run the following bootstrap command inside your Termux terminal:

```bash
pkg update -y && pkg install -y git python ffmpeg openssl clang libjpeg-turbo
git clone https://github.com/ManoAlee/auto-shorts-android.git
cd auto-shorts-android
bash scripts/install_termux.sh
```

### Manual Termux Package Configuration
If you prefer configuring individual dependencies:

1. **Update package repositories:**
   ```bash
   pkg update -y && pkg upgrade -y
   ```

2. **Install core toolchain & media binaries:**
   ```bash
   pkg install -y python git ffmpeg openssh termux-api jq
   ```

3. **Install Python virtual environment & dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

4. **Acquire Termux Wake Lock (Prevents Android OS process freezing):**
   ```bash
   termux-wake-lock
   ```

---

## 2. Auxiliary Development Workstation: Windows 11

Windows serves as a high-speed development, code review, and QA environment.

### Prerequisites
- Python 3.11, 3.12, or 3.13 (64-bit).
- [FFmpeg](https://ffmpeg.org/download.html) installed and added to system `PATH`.
- Git for Windows.

### Installation Steps
```powershell
# Clone repository
git clone https://github.com/ManoAlee/auto-shorts-android.git
cd auto-shorts-android

# Setup Virtual Environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest ruff bandit
```

---

## 3. Auxiliary Host: Linux (Ubuntu / Debian x86_64)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv ffmpeg git curl
git clone https://github.com/ManoAlee/auto-shorts-android.git
cd auto-shorts-android

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Verification Check

To confirm your installation is operational across all engines:

```bash
# Verify Python import and test suite
PYTHONPATH=src pytest tests -q

# Check FFmpeg capabilities
ffmpeg -version | head -n 1
```
All tests should pass without errors.
