"""Direct entrypoint: python main.py ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from auto_shorts.cli import main  # noqa: E402
from auto_shorts.config import load_dotenv_file  # noqa: E402

if __name__ == "__main__":
    load_dotenv_file(Path(__file__).resolve().parent / ".env")
    raise SystemExit(main())

