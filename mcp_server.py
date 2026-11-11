"""Stdio MCP entrypoint for youtube-studio-mcp (works on Windows PC and Android Termux)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_shorts.youtube_studio_mcp import serve_stdio


if __name__ == "__main__":
    serve_stdio()

