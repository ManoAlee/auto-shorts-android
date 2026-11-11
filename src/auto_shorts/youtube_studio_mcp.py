"""MCP Server (stdio JSON-RPC 2.0) unifying claude-youtube creator intelligence & AutoShorts Studio."""

import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .anime_trends import get_releasing_anime_radar
from .config import load_dotenv_file
from .discovery import discover_videos
from .pipeline import run_autopilot, run_pipeline
from .publisher import _refresh_youtube_token, get_youtube_channel_summary, publish_pack_to_youtube
from .team import build_persona_script_brief, generate_channel_planner, list_channel_personas
from .transcript import load_transcript
from .validator import validate_generated_short
from .world_news import fetch_world_news_headlines, produce_world_news_short


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv_file(PROJECT_ROOT / ".env")


def _remote_base() -> str:
    return os.getenv("AUTOSHORT_REMOTE_URL", "").strip().rstrip("/")


def _remote_json(method: str, path: str, payload: Optional[Dict] = None) -> Dict:
    url = f"{_remote_base()}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tool_audit_channel(channel_handle: str = "") -> Dict:
    """Audit authenticated channel (or @handle/URL) using OAuth uploads playlist (~16 quota units)."""
    handle = (channel_handle or "").strip()
    cid = os.getenv("YT_CLIENT_ID", "").strip()
    csec = os.getenv("YT_CLIENT_SECRET", "").strip()
    rtok = os.getenv("YT_REFRESH_TOKEN", "").strip()

    if _remote_base() and not handle and not rtok:
        return _remote_json("GET", "/api/channel")

    if cid and csec and rtok:
        tok = _refresh_youtube_token(cid, csec, rtok)
        if not handle:
            q = "part=snippet,contentDetails,statistics&mine=true"
        elif handle.startswith("UC") and len(handle) == 24:
            q = f"part=snippet,contentDetails,statistics&id={urllib.parse.quote(handle)}"
        else:
            clean_h = handle.lstrip("@")
            if "youtube.com/@" in clean_h:
                clean_h = clean_h.split("youtube.com/@", 1)[1].split("/")[0]
            q = f"part=snippet,contentDetails,statistics&forHandle={urllib.parse.quote(clean_h)}"

        req = urllib.request.Request(
            f"https://www.googleapis.com/youtube/v3/channels?{q}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            ch_data = json.loads(r.read().decode("utf-8"))
        items = ch_data.get("items") or []
        if not items:
            return {"error": f"Canal nao encontrado: {handle or 'mine'}"}

        ch = items[0]
        snip = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        uploads_pl = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        videos: List[Dict] = []
        if uploads_pl:
            pl_req = urllib.request.Request(
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={uploads_pl}&maxResults=12",
                headers={"Authorization": f"Bearer {tok}"},
            )
            with urllib.request.urlopen(pl_req, timeout=20) as r:
                pl_items = json.loads(r.read().decode("utf-8")).get("items", [])
            vid_ids = [it["snippet"]["resourceId"]["videoId"] for it in pl_items if it.get("snippet", {}).get("resourceId", {}).get("videoId")]
            if vid_ids:
                v_req = urllib.request.Request(
                    f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={','.join(vid_ids)}",
                    headers={"Authorization": f"Bearer {tok}"},
                )
                with urllib.request.urlopen(v_req, timeout=20) as r:
                    v_data = json.loads(r.read().decode("utf-8")).get("items", [])
                for v in v_data:
                    vs = v.get("statistics", {})
                    views = int(vs.get("viewCount") or 0)
                    likes = int(vs.get("likeCount") or 0)
                    comments = int(vs.get("commentCount") or 0)
                    videos.append({
                        "video_id": v["id"],
                        "url": f"https://youtube.com/watch?v={v['id']}",
                        "title": v["snippet"]["title"],
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "engagement_pct": round(((likes + comments) / views) * 100.0, 2) if views else 0.0,
                    })

        return {
            "channel_id": ch["id"],
            "title": snip.get("title"),
            "handle": snip.get("customUrl"),
            "subscribers": int(stats.get("subscriberCount") or 0),
            "total_views": int(stats.get("viewCount") or 0),
            "video_count": int(stats.get("videoCount") or 0),
            "recent_videos": videos,
        }

    return get_youtube_channel_summary()


def tool_search_competitors(query: str, limit: int = 8) -> Dict:
    """Zero-quota competitor & viral source discovery via yt-dlp."""
    items = discover_videos(niche="geral", query=query, limit=max(1, min(15, int(limit))))
    return {"query": query, "count": len(items), "videos": items}


def tool_fetch_transcript(url: str, language: str = "pt") -> Dict:
    """Download clean transcript lines (.vtt/.srt) from any YouTube video via yt-dlp."""
    with tempfile.TemporaryDirectory() as td:
        out_tpl = str(Path(td) / "cap.%(ext)s")
        cmd = [
            "yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
            "--sub-langs", f"{language},en", "--sub-format", "vtt/srt",
            "-o", out_tpl, "--no-warnings", url,
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        files = sorted(Path(td).glob("*.vtt")) or sorted(Path(td).glob("*.srt"))
        if not files:
            return {"url": url, "segments": [], "error": "Nenhuma legenda disponivel para este link."}
        parsed = load_transcript(files[0])
        return {"url": url, "duration": parsed.get("duration", 0.0), "segments": parsed.get("segments", [])[:120]}


def tool_anime_radar(limit: int = 8) -> Dict:
    """Live AniList & Jikan currently releasing anime feed + search queries."""
    return {"anime": get_releasing_anime_radar(limit=max(1, min(15, int(limit))))}


def tool_team_planner(topic: str = "", niche: str = "podcast", days: int = 7) -> Dict:
    """Return full 7-persona team roster, optional 3-act brief, and weekly peak-hour planner."""
    out: Dict[str, Any] = {
        "personas": list_channel_personas(),
        "planner": generate_channel_planner(days=days, include_live_anime=True),
    }
    if topic.strip():
        out["script_brief"] = build_persona_script_brief(topic=topic, niche=niche)
    return out


def tool_generate_short(
    niche: str = "podcast",
    platform: str = "youtube_shorts",
    source: str = "",
    query: str = "",
    clips: int = 1,
    playlist: str = "",
    auto_publish: bool = True,
) -> Dict:
    """Run AutoShorts pipeline locally or remotely on the Android Termux studio server."""
    if _remote_base():
        return _remote_json(
            "POST",
            "/api/run",
            {
                "niche": niche,
                "platform": platform,
                "source": source,
                "query": query,
                "clips": clips,
                "playlist": playlist,
                "auto_publish": auto_publish,
            },
        )
    out_dir = PROJECT_ROOT / "output"
    if source.strip():
        return run_pipeline(
            source=source.strip(),
            out_dir=out_dir,
            platform=platform,
            niche=niche,
            num_clips=clips,
            playlist_name=playlist or None,
            auto_publish=auto_publish,
        )
    return run_autopilot(
        out_dir=out_dir,
        platform=platform,
        niche=niche,
        query=query or None,
        num_clips=clips,
        playlist_name=playlist or None,
        auto_publish=auto_publish,
    )


def tool_validate_and_publish(filename: str, publish: bool = False, playlist: str = "") -> Dict:
    """Validate an MP4 Short cleanly and optionally upload to YouTube."""
    if _remote_base():
        val = _remote_json("POST", "/api/validate", {"filename": filename})
        if publish and val.get("valid"):
            pub = _remote_json("POST", "/api/publish", {"filename": filename, "playlist": playlist or None})
            return {"validation": val, "published": pub}
        return {"validation": val}

    target = (PROJECT_ROOT / "output" / Path(filename).name).resolve()
    val = validate_generated_short(target)
    if publish and val.get("valid"):
        pub = publish_pack_to_youtube(target, playlist_name=playlist or None)
        return {"validation": val, "published": pub}
    return {"validation": val}


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "yt_audit_channel": {
        "description": "Audit a YouTube channel (default: authenticated AleplayTV) with stats, video engagement, and recent uploads (claude-youtube execution pattern).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_handle": {"type": "string", "description": "Optional @handle, UC channel ID, or URL; omit for your authenticated channel."}
            },
        },
        "handler": lambda args: tool_audit_channel(str(args.get("channel_handle") or "")),
    },
    "yt_search_competitors": {
        "description": "Search competitor YouTube videos by topic without consuming YouTube API search quota.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'podcast cortes brasil ia')"},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
        "handler": lambda args: tool_search_competitors(str(args["query"]), int(args.get("limit", 8))),
    },
    "yt_fetch_transcript": {
        "description": "Extract timestamped YouTube subtitles/transcript from any public video URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "language": {"type": "string", "default": "pt"},
            },
            "required": ["url"],
        },
        "handler": lambda args: tool_fetch_transcript(str(args["url"]), str(args.get("language", "pt"))),
    },
    "yt_anime_release_radar": {
        "description": "Fetch live currently-releasing top trending anime (AniList GraphQL + Jikan) for instant first-mover Shorts.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 8}},
        },
        "handler": lambda args: tool_anime_radar(int(args.get("limit", 8))),
    },
    "yt_world_news_brazil": {
        "description": "Fetch real international news via zero-key Public APIs (BBC World, The Guardian, Spaceflight News, Wikipedia, Hacker News), translate to PT-BR and optionally render & publish a Short.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "default": "world"},
                "produce": {"type": "boolean", "default": False},
                "auto_publish": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 6},
            },
        },
        "handler": lambda args: (
            produce_world_news_short(
                out_dir=PROJECT_ROOT / "output",
                topic=str(args.get("topic") or "world"),
                auto_publish=bool(args.get("auto_publish", False)),
            )
            if bool(args.get("produce", False))
            else {"headlines": fetch_world_news_headlines(topic=str(args.get("topic") or "world"), limit=int(args.get("limit", 6)))}
        ),
    },
    "yt_team_personas_planner": {
        "description": "Get the full 7-persona channel team, 7-day peak-hour schedule, and optional 3-act retention script brief.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "niche": {"type": "string", "default": "podcast"},
                "days": {"type": "integer", "default": 7},
            },
        },
        "handler": lambda args: tool_team_planner(str(args.get("topic") or ""), str(args.get("niche") or "podcast"), int(args.get("days", 7))),
    },
    "yt_generate_short": {
        "description": "Run automated vertical 9:16 Short extraction/cutting, validation, and YouTube upload (locally or via phone remote URL).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "default": "podcast"},
                "platform": {"type": "string", "default": "youtube_shorts"},
                "source": {"type": "string", "default": ""},
                "query": {"type": "string", "default": ""},
                "clips": {"type": "integer", "default": 1},
                "playlist": {"type": "string", "default": ""},
                "auto_publish": {"type": "boolean", "default": True},
            },
        },
        "handler": lambda args: tool_generate_short(
            niche=str(args.get("niche") or "podcast"),
            platform=str(args.get("platform") or "youtube_shorts"),
            source=str(args.get("source") or ""),
            query=str(args.get("query") or ""),
            clips=int(args.get("clips", 1)),
            playlist=str(args.get("playlist") or ""),
            auto_publish=bool(args.get("auto_publish", True)),
        ),
    },
    "yt_validate_and_publish": {
        "description": "Validate MP4 aspect/audio/subtitles and optionally publish directly to AleplayTV with thumbnail and playlist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "publish": {"type": "boolean", "default": False},
                "playlist": {"type": "string", "default": ""},
            },
            "required": ["filename"],
        },
        "handler": lambda args: tool_validate_and_publish(str(args["filename"]), bool(args.get("publish", False)), str(args.get("playlist") or "")),
    },
}


def handle_mcp_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process one JSON-RPC 2.0 MCP request."""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    if method == "notifications/initialized" or req_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "youtube-studio-mcp", "version": "1.0.0"},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in TOOL_REGISTRY.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        spec = TOOL_REGISTRY.get(name)
        if not spec:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }
        try:
            res = spec["handler"](arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"isError": True, "content": [{"type": "text", "text": f"Error: {exc}"}]},
            }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not supported: {method}"}}


def serve_stdio() -> None:
    """Serve MCP JSON-RPC 2.0 over stdin/stdout (zero external dependencies)."""
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        resp = handle_mcp_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()

