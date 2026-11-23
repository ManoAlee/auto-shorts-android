import json
from pathlib import Path

p = Path("output/mundo_br_20261123_144848.publish.json")
if p.is_file():
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=== NEW VIDEO VALIDATION AUDIT ===")
    print(f"Title:             {d.get('title')}")
    print(f"Hook:              {d.get('hook_title')}")
    print(f"Category / Niche:  {d.get('niche')}")
    print(f"Duration:          {d.get('validation', {}).get('duration')}s")
    print(f"Script words:      {d.get('script_integrity', {}).get('script_words')}")
    print(f"Sentinel Approved: {d.get('sentinel_approved')}")
    print(f"Sentinel Score:    {d.get('sentinel_overall_score')}/100")
    print(f"Visual Decision:   {d.get('visual_audit', {}).get('decision')}")
    print("\n--- SPOKEN DIALOGUE ---")
    ass_path = p.with_suffix(".ass")
    if ass_path.is_file():
        lines = [line.split(",", 9)[-1].strip() for line in ass_path.read_text(encoding="utf-8").splitlines() if line.startswith("Dialogue:")]
        print(" ".join(lines))
    print("\n--- CAPTION LEAD ---")
    print(d.get("caption", "")[:350])
else:
    print(f"File not found: {p}")
