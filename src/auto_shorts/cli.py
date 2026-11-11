"""CLI interface for auto-shorts-android."""

import argparse
import json
from pathlib import Path

from .config import NICHES, PLATFORMS
from .evolution import EvolutionStore
from .pipeline import run_autopilot, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-shorts",
        description="Automated 9:16 video clipper & subtitle burner optimized for Android/Termux.",
    )
    parser.add_argument("source", nargs="?", help="YouTube URL or local MP4 path (omit when using --discover)")
    parser.add_argument("--out", default="output", help="Output directory (default: output)")
    parser.add_argument(
        "--platform",
        choices=sorted(PLATFORMS.keys()),
        default="tiktok_rewards",
        help="Target platform duration preset (default: tiktok_rewards >= 62s)",
    )
    parser.add_argument(
        "--niche",
        choices=sorted(list(NICHES.keys()) + ["all"]),
        default="podcast",
        help="Brazilian niche profile ('all' rotates across podcast, financas, ia_tech, etc.)",
    )
    parser.add_argument("--playlist", default=None, help="Optional YouTube playlist title (auto-created if missing)")
    parser.add_argument("--clips", type=int, default=3, help="Number of shorts to export per video")
    parser.add_argument(
        "--layout",
        choices=["blur_bg", "center_crop", "split_top_bottom"],
        default="blur_bg",
        help="9:16 vertical framing layout",
    )
    parser.add_argument("--auto-layout", action="store_true", help="Let UCB1 bandit pick best layout from past metrics")
    parser.add_argument(
        "--quality",
        choices=["mobile", "high"],
        default="mobile",
        help="mobile=720x1280 veryfast (thermal safe), high=1080x1920 fast",
    )
    parser.add_argument(
        "--encoder",
        choices=["libx264", "h264_mediacodec"],
        default="libx264",
        help="Video encoder (auto-falls back to libx264 if mediacodec fails)",
    )
    parser.add_argument("--srt", default=None, help="Optional .srt/.vtt/.json transcript path")
    parser.add_argument("--whisper-model", default=None, help="Path to whisper.cpp ggml model")
    parser.add_argument("--lang", default="pt", help="Transcript language code (default: pt)")
    parser.add_argument("--no-silence-cut", action="store_true", help="Skip jump-cut silence removal")
    parser.add_argument("--offline", action="store_true", help="Force offline heuristic (no LLM API)")
    parser.add_argument("--cookies", default=None, help="Optional yt-dlp cookies.txt path (only if YouTube asks login)")

    # Auto-discovery & autopilot flags
    parser.add_argument("--discover", action="store_true", help="Automatically search real YouTube videos by niche")
    parser.add_argument("--query", default=None, help="Custom search query for --discover")
    parser.add_argument("--search-limit", type=int, default=8, help="How many candidate videos to inspect")
    parser.add_argument("--auto-count", type=int, default=1, help="How many discovered videos to process")
    parser.add_argument("--dry-run", action="store_true", help="List discovered videos without downloading/rendering")

    # Web UI mode
    parser.add_argument("--serve", action="store_true", help="Start mobile accessible Web App on port 8787")
    parser.add_argument("--port", type=int, default=8787, help="Port for --serve web dashboard")

    # Closed-loop feedback flags
    parser.add_argument("--feedback-clip", type=int, default=None, help="Record metrics feedback for a clip_id")
    parser.add_argument("--views", type=int, default=0, help="Observed views for --feedback-clip")
    parser.add_argument("--watch-pct", type=float, default=0.0, help="Avg watch percentage (0-100) for --feedback-clip")
    parser.add_argument("--shares", type=int, default=0, help="Shares count for --feedback-clip")
    parser.add_argument("--saves", type=int, default=0, help="Saves count for --feedback-clip")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        from .webapp import serve_webapp
        serve_webapp(host="0.0.0.0", port=args.port, out_dir=args.out)
        return 0

    if args.feedback_clip is not None:
        store = EvolutionStore(Path(args.out) / "shorts_evolution.db")
        reward = store.record_feedback(
            clip_id=args.feedback_clip,
            views=args.views,
            avg_watch_pct=args.watch_pct,
            shares=args.shares,
            saves=args.saves,
        )
        print(json.dumps({"clip_id": args.feedback_clip, "reward": reward}, indent=2))
        return 0

    if args.discover:
        channel_url = args.source if (args.source and args.source.startswith(("http://", "https://"))) else None
        result = run_autopilot(
            out_dir=args.out,
            platform=args.platform,
            niche=args.niche,
            query=args.query,
            channel_url=channel_url,
            search_limit=args.search_limit,
            auto_count=args.auto_count,
            num_clips=args.clips,
            layout=args.layout,
            quality=args.quality,
            encoder=args.encoder,
            whisper_model=args.whisper_model,
            language=args.lang,
            trim_silence=not args.no_silence_cut,
            use_llm=not args.offline,
            auto_layout=args.auto_layout or True,
            cookies_path=args.cookies,
            dry_run=args.dry_run,
            playlist_name=args.playlist,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if not args.source:
        parser.error("source is required unless --discover or --feedback-clip is provided")

    result = run_pipeline(
        source=args.source,
        out_dir=args.out,
        platform=args.platform,
        niche=args.niche if args.niche != "all" else "podcast",
        num_clips=args.clips,
        layout=args.layout,
        quality=args.quality,
        encoder=args.encoder,
        srt_path=args.srt,
        whisper_model=args.whisper_model,
        language=args.lang,
        trim_silence=not args.no_silence_cut,
        use_llm=not args.offline,
        auto_layout=args.auto_layout,
        cookies_path=args.cookies,
        playlist_name=args.playlist,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
