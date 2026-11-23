"""Generate a high-quality, substantive Short audited by Sentinel Pre-Render."""
import json
import logging
import sys
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GenerateSentinelShort")

from auto_shorts.world_news import produce_world_news_short

def run():
    logger.info("Starting Sentinel-governed video production...")
    res = produce_world_news_short(
        out_dir=BASE_DIR / "output",
        topic="tech",
        bg_video="auto",
        style="podcast_female",
        use_llm=False,  # Uses the immunized Mahoraga 8-Spoke synthesis
        target_platform="tiktok_rewards",
    )
    logger.info("Production finished successfully!")
    print("\n=== GENERATED VIDEO RESULT ===")
    print(f"Title:         {res.get('title')}")
    print(f"Hook:          {res.get('hook_title')}")
    print(f"Output MP4:    {res.get('output_path')}")
    print(f"Duration:      {res.get('duration')}s")
    print(f"Delivery:      {res.get('delivery_status')}")
    if res.get("visual_audit"):
        print(f"Visual Audit:  {res['visual_audit'].get('decision')} (Score: {res['visual_audit'].get('quality_score')})")
    
    # Check publish pack
    mp4_path = Path(res.get("output_path", ""))
    pub_path = mp4_path.with_suffix(".publish.json")
    if pub_path.is_file():
        data = json.loads(pub_path.read_text(encoding="utf-8"))
        print(f"Script words:  {data.get('script_integrity', {}).get('script_words')}")
        print(f"Sentinel gate: {data.get('sentinel_status')} (Score: {data.get('sentinel_overall_score')})")
        print("\n--- SPOKEN SCRIPT ---")
        caption = data.get("caption", "")
        print(caption[:300])

if __name__ == "__main__":
    run()
