# Development: Local Setup

Guidelines for configuring a local development environment for contributing to AutoShorts.

---

## 1. Development Environment Prerequisites

- **Python:** Version 3.11, 3.12, or 3.13.
- **Node.js:** Version 18+ (used strictly for syntax verification of `studio.js`).
- **FFmpeg:** Installed with `libx264` and `aac` support.
- **Git:** Git 2.30+ configured.

---

## 2. Repository Setup

```bash
# Clone the repository
git clone https://github.com/ManoAlee/auto-shorts-android.git
cd auto-shorts-android

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Or .\.venv\Scripts\Activate.ps1 on Windows

# Install production and development dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov ruff bandit
```

---

## 3. Code Standards & Static Analysis

Before opening a pull request, run local quality gates:

```bash
# 1. Compile bytecode across all source trees
python -m compileall -q src tests scripts

# 2. Validate frontend JavaScript syntax
node --check src/auto_shorts/frontend/studio.js

# 3. Run full automated test suite
PYTHONPATH=src pytest tests -q

# 4. Run SAST security check
bandit -r src/ -ll -ii -x src/auto_shorts/frontend/
```
