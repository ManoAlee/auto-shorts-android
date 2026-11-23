import json
from pathlib import Path

p = Path("output/sentinel/reports/sentinel_1795456128_report.json")
if p.is_file():
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=== SENTINEL PRE-RENDER 10 QUALITY GATES AUDIT ===")
    print(f"Project ID:     {d.get('project_id')}")
    print(f"Title:          {d.get('title')}")
    print(f"Is Approved:    {d.get('is_approved')}")
    print(f"Overall Score:  {d.get('overall_score')}/100")
    print(f"HTML Preview:   {d.get('storyboard', {}).get('html_preview_path')}")
    print("\n--- INDIVIDUAL GATES ---")
    for gid, g in sorted(d.get("gates", {}).items()):
        status = g.get("status")
        score = g.get("score")
        name = g.get("name")
        errs = g.get("errors", [])
        warns = g.get("warnings", [])
        notes = f" (Errors: {errs})" if errs else (f" (Warnings: {warns})" if warns else "")
        print(f"[{status:<7}] {gid:<32} {score:>3}/100 | {name}{notes}")
    
    print("\n--- REVISION HISTORY ---")
    for r in d.get("revision_history", []):
        print(f"- Iteration {r.get('iteration')}: {r.get('changes')}")
