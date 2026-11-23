import json
import sys
from pathlib import Path

targets = sys.argv[1:]
if not targets:
    targets = [
        "3usldBhhO5c_short_01_youtube_shorts.publish.json",
        "BRE4dNUr9HQ_short_01_tiktok_rewards.publish.json",
        "HVNyN3pd4CY_short_01_youtube_shorts.publish.json",
        "UiK9pl8tKao_short_01_youtube_shorts.publish.json",
        "hgxQ5k1OmrY_short_01_youtube_shorts.publish.json",
        "mundo_br_20261123_043904.publish.json",
        "mundo_br_20261123_130740.publish.json",
    ]

for t in targets:
    p = Path("output") / t if not t.startswith("output") else Path(t)
    if not p.is_file():
        p = Path(t)
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            print("=" * 60)
            print(f"FILE: {p.name}")
            print(f"TITLE: {d.get('title')}")
            print(f"NICHE: {d.get('niche')}")
            print(f"CAPTION:\n{d.get('caption')}")
            print("-" * 40)
            # Check if subtitle or script files exist
            stem = p.stem.replace(".publish", "")
            sub_file = p.parent / f"{stem}.ass"
            if sub_file.is_file():
                print(f"SUBTITLE ({sub_file.name}): {sub_file.read_text(encoding='utf-8')[:300]}")
        except Exception as e:
            print(f"Error {p}: {e}")
