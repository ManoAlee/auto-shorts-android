import glob
import json
from pathlib import Path

out_dir = Path("output")
for f in sorted(out_dir.glob("*.publish.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        title = data.get("title", "")
        source_title = data.get("source_title", "")
        niche = data.get("niche", "")
        meta = data.get("source_meta") or data.get("meta") or {}
        channel = data.get("channel") or data.get("uploader") or meta.get("channel") or meta.get("uploader") or ""
        meta_title = meta.get("title", "")
        caption = str(data.get("caption") or "").replace("\n", " ")[:150]
        script = str(data.get("script") or data.get("body_text") or data.get("clip_summary") or "").replace("\n", " ")[:150]
        print(f"[{f.name}]")
        print(f"  TITLE:        {title}")
        print(f"  SOURCE_TITLE: {source_title}")
        print(f"  META_TITLE:   {meta_title}")
        print(f"  CHANNEL:      {channel}")
        print(f"  NICHE:        {niche}")
        print(f"  CAPTION:      {caption}")
        print(f"  SCRIPT:       {script}")
        print()
    except Exception as e:
        print(f"[{f.name}] Error: {e}")
