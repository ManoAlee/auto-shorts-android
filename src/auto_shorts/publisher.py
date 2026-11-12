"""Multi-portal delivery packaging, Meta Graph API Reels publisher, and webhook dispatcher."""

import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import NICHES
from .retention import get_retention_profile


def build_publish_pack(
    clip: Dict,
    platform: str,
    niche: str,
    source_meta: Optional[Dict[str, str]] = None,
) -> Dict:
    """Create platform-ready metadata (real title, rich PT-BR description, hashtags, CTA)."""
    hook = clip.get("hook_title") or clip.get("title") or "Destaque"
    title = clip.get("title") or hook
    summary = str(clip.get("clip_summary") or "").strip()
    retention_cta = get_retention_profile(platform).reels_cta_hint
    cta = clip.get("cta_line") or retention_cta
    niche_tags = {
        "financas": ["#financas", "#investimentos", "#dinheiro", "#educacaofinanceira"],
        "ia_tech": ["#inteligenciaartificial", "#tecnologia", "#ia", "#produtividade"],
        "desenvolvimento_pessoal": ["#mentalidade", "#disciplina", "#desenvolvimentopessoal"],
        "saude_fitness": ["#saude", "#treino", "#fitness", "#bemestar"],
        "concursos": ["#concursos", "#estudos", "#carreira"],
        "entretenimento_animes": ["#anime", "#manga", "#teoria", "#animesbrasil"],
        "podcast": ["#podcast", "#podcastbrasil", "#cortes", "#entrevista"],
        "noticias_mundiais": ["#NoticiasMundiais", "#Mundo", "#Brasil", "#Atualidades"],
        "geral": ["#cortes", "#viral", "#brasil"],
    }
    tags = list(niche_tags.get(niche, ["#cortes"]))
    if platform == "youtube_shorts" and "#Shorts" not in tags:
        tags.append("#Shorts")
    elif platform == "instagram_reels" and "#reels" not in tags:
        tags.extend(["#reels", "#reelsbrasil"])

    meta = source_meta or {}
    parts = [f"{title}"]
    if hook and hook.lower() not in title.lower():
        parts.append(f"Destaque: {hook}")
    if summary:
        parts.append(f"\nSobre este corte:\n{summary}")

    src_title = str(meta.get("title") or "").strip()
    src_channel = str(meta.get("channel") or "").strip()
    src_url = str(meta.get("webpage_url") or meta.get("url") or "").strip()
    if src_title or src_channel or src_url:
        source_lines = ["\nFonte / Referencia:"]
        if src_channel and src_title:
            source_lines.append(f"{src_channel} - {src_title}")
        elif src_title or src_channel:
            source_lines.append(src_title or src_channel)
        if src_url:
            source_lines.append(f"Video original: {src_url}")
        parts.append("\n".join(source_lines))

    cta_clean = cta.strip()
    if "inscrev" in cta_clean.lower():
        parts.append(f"\n{cta_clean}\nComenta sua opiniao ai embaixo!")
    else:
        parts.append(f"\n{cta_clean}\n{retention_cta}\nComenta sua opiniao ai embaixo!")
    parts.append(f"\n{' '.join(tags)}")
    caption = "\n".join(parts).strip()

    return {
        "platform": platform,
        "niche": niche,
        "title": title[:95],
        "hook_title": hook,
        "caption": caption,
        "hashtags": tags,
        "output_path": clip.get("output_path"),
        "clip_id": clip.get("clip_id"),
    }


def export_to_android_gallery(mp4_path: Path, dest_dir: Optional[Path] = None) -> Optional[Path]:
    """Copy finished MP4 to Android shared Movies/AutoShorts when Termux storage is mounted."""
    target_root = dest_dir or (Path.home() / "storage" / "shared" / "Movies" / "AutoShorts")
    if not (Path.home() / "storage" / "shared").exists() and dest_dir is None:
        return None
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / mp4_path.name
    shutil.copy2(mp4_path, target)
    return target


def dispatch_webhook(pack: Dict, webhook_url: Optional[str] = None) -> Optional[Dict]:
    """Send publish pack metadata to an external n8n/Postiz/Upload-Post orchestration webhook."""
    url = (webhook_url or os.getenv("PUBLISH_WEBHOOK_URL", "")).strip()
    if not url:
        return None
    payload = json.dumps(pack, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return {"status": resp.status, "response": raw}


def publish_instagram_reel(
    video_public_url: str,
    caption: str,
    ig_user_id: Optional[str] = None,
    access_token: Optional[str] = None,
    graph_version: str = "v21.0",
    poll_timeout: int = 120,
) -> Dict:
    """Publish a Reel via Meta Graph API (requires Professional IG account + public HTTPS video URL)."""
    uid = (ig_user_id or os.getenv("IG_USER_ID", "")).strip()
    token = (access_token or os.getenv("IG_ACCESS_TOKEN", "")).strip()
    if not uid or not token:
        raise RuntimeError("IG_USER_ID and IG_ACCESS_TOKEN environment variables are required for Instagram Graph API.")
    if not video_public_url.startswith("https://"):
        raise ValueError("Instagram Graph API requires an HTTPS public video_url.")

    create_url = f"https://graph.facebook.com/{graph_version}/{uid}/media"
    create_data = urllib.parse.urlencode({
        "media_type": "REELS",
        "video_url": video_public_url,
        "caption": caption[:2200],
        "share_to_feed": "true",
        "access_token": token,
    }).encode("utf-8")
    req = urllib.request.Request(create_url, data=create_data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        container = json.loads(resp.read().decode("utf-8"))
    creation_id = container["id"]

    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        status_url = (
            f"https://graph.facebook.com/{graph_version}/{creation_id}"
            f"?fields=status_code&access_token={urllib.parse.quote(token)}"
        )
        with urllib.request.urlopen(status_url, timeout=20) as resp:
            status_body = json.loads(resp.read().decode("utf-8"))
        code = status_body.get("status_code")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram media container failed: {status_body}")
        time.sleep(4)

    publish_url = f"https://graph.facebook.com/{graph_version}/{uid}/media_publish"
    publish_data = urllib.parse.urlencode({
        "creation_id": creation_id,
        "access_token": token,
    }).encode("utf-8")
    pub_req = urllib.request.Request(publish_url, data=publish_data, method="POST")
    with urllib.request.urlopen(pub_req, timeout=30) as resp:
        published = json.loads(resp.read().decode("utf-8"))
    return {"creation_id": creation_id, "media_id": published.get("id")}


def _refresh_youtube_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Failed to refresh YouTube OAuth token: {body}")
    return str(token)


def publish_youtube_short(
    video_path: str | Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Dict:
    """Upload a vertical Short MP4 via YouTube Data API v3 resumable upload."""
    cid = (client_id or os.getenv("YT_CLIENT_ID", "")).strip()
    csec = (client_secret or os.getenv("YT_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.getenv("YT_REFRESH_TOKEN", "")).strip()
    if not cid or not csec or not rtok:
        raise RuntimeError("YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN are required for YouTube upload.")

    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"Video file not found for YouTube upload: {mp4}")

    access_token = _refresh_youtube_token(cid, csec, rtok)
    privacy = (privacy_status or os.getenv("YT_PRIVACY_STATUS", "private")).strip() or "private"
    clean_title = title.replace("<", "").replace(">", "").strip()[:95] or "Corte Viral"
    clean_desc = description.replace("<", "").replace(">", "").strip()
    if "#Shorts" not in clean_desc:
        clean_desc = f"{clean_desc}\n\n#Shorts".strip()

    metadata = json.dumps({
        "snippet": {
            "title": clean_title,
            "description": clean_desc[:4900],
            "tags": [t.lstrip("#").replace("<", "").replace(">", "") for t in (tags or ["Shorts"]) if t.strip()][:15],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }).encode("utf-8")

    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=metadata,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(mp4.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(init_req, timeout=30) as resp:
            upload_url = resp.headers.get("Location")
    except urllib.error.HTTPError as exc:
        err_detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"YouTube recusou os metadados ({exc.code}): {err_detail or exc.reason}") from exc
    if not upload_url:
        raise RuntimeError("YouTube resumable upload did not return a Location header.")

    video_bytes = mp4.read_bytes()
    put_req = urllib.request.Request(
        upload_url,
        data=video_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_bytes)),
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(put_req, timeout=300) as resp:
            uploaded = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"Falha no upload YouTube ({exc.code}): {err_detail or exc.reason}") from exc
    vid = uploaded.get("id")
    return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}" if vid else None, "privacy": privacy}


def update_youtube_video_metadata(
    video_id: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Dict:
    """Update title, description, and optional privacyStatus of an existing YouTube video."""
    cid = (client_id or os.getenv("YT_CLIENT_ID", "")).strip()
    csec = (client_secret or os.getenv("YT_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.getenv("YT_REFRESH_TOKEN", "")).strip()
    if not cid or not csec or not rtok:
        raise RuntimeError("YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN are required.")

    access_token = _refresh_youtube_token(cid, csec, rtok)
    if "#Shorts" not in description:
        description = f"{description.strip()}\n\n#Shorts"
    body_obj: Dict = {
        "id": video_id,
        "snippet": {
            "title": title.strip()[:95],
            "description": description[:4900],
            "tags": [t.lstrip("#") for t in (tags or ["Shorts"])][:15],
            "categoryId": "22",
        },
    }
    part = "snippet"
    if privacy_status:
        body_obj["status"] = {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False}
        part = "snippet,status"

    payload = json.dumps(body_obj).encode("utf-8")
    req = urllib.request.Request(
        f"https://www.googleapis.com/youtube/v3/videos?part={part}",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        updated = json.loads(resp.read().decode("utf-8"))
    return {
        "video_id": updated.get("id"),
        "title": updated.get("snippet", {}).get("title"),
        "privacy": updated.get("status", {}).get("privacyStatus"),
    }


def ensure_youtube_playlist(
    title: str,
    description: str = "",
    privacy_status: str = "public",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> str:
    """Find an existing playlist by exact title or create a new one."""
    cid = (client_id or os.getenv("YT_CLIENT_ID", "")).strip()
    csec = (client_secret or os.getenv("YT_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.getenv("YT_REFRESH_TOKEN", "")).strip()
    if not cid or not csec or not rtok:
        raise RuntimeError("YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN are required.")

    access_token = _refresh_youtube_token(cid, csec, rtok)
    list_req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(list_req, timeout=30) as resp:
        listed = json.loads(resp.read().decode("utf-8"))
    for item in listed.get("items", []):
        if item.get("snippet", {}).get("title", "").strip().lower() == title.strip().lower():
            return str(item["id"])

    payload = json.dumps({
        "snippet": {"title": title.strip()[:150], "description": description[:4900]},
        "status": {"privacyStatus": privacy_status},
    }).encode("utf-8")
    create_req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/playlists?part=snippet,status",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(create_req, timeout=30) as resp:
        created = json.loads(resp.read().decode("utf-8"))
    return str(created["id"])


def add_video_to_playlist(
    playlist_id: str,
    video_id: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Dict:
    """Insert an uploaded video into a YouTube playlist."""
    cid = (client_id or os.getenv("YT_CLIENT_ID", "")).strip()
    csec = (client_secret or os.getenv("YT_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.getenv("YT_REFRESH_TOKEN", "")).strip()
    access_token = _refresh_youtube_token(cid, csec, rtok)
    payload = json.dumps({
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        added = json.loads(resp.read().decode("utf-8"))
    return {"playlist_item_id": added.get("id"), "playlist_id": playlist_id, "video_id": video_id}


def set_youtube_thumbnail(
    video_id: str,
    thumbnail_path: str | Path,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Dict:
    """Upload a custom JPG thumbnail (<2MB) to a YouTube video."""
    thumb = Path(thumbnail_path)
    if not thumb.is_file():
        raise FileNotFoundError(f"Thumbnail not found: {thumb}")
    cid = (client_id or os.getenv("YT_CLIENT_ID", "")).strip()
    csec = (client_secret or os.getenv("YT_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.getenv("YT_REFRESH_TOKEN", "")).strip()
    access_token = _refresh_youtube_token(cid, csec, rtok)
    img_bytes = thumb.read_bytes()
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={urllib.parse.quote(video_id)}",
        data=img_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(img_bytes)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    return {"video_id": video_id, "items": len(res.get("items", []))}


def get_youtube_channel_summary() -> Dict:
    """Fetch authenticated YouTube channel identity & live stats."""
    cid = os.getenv("YT_CLIENT_ID", "").strip()
    csec = os.getenv("YT_CLIENT_SECRET", "").strip()
    rtok = os.getenv("YT_REFRESH_TOKEN", "").strip()
    if not cid or not csec or not rtok:
        return {"connected": False, "reason": "Credenciais YT_* ausentes"}
    try:
        token = _refresh_youtube_token(cid, csec, rtok)
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items") or []
        if not items:
            return {"connected": False, "reason": "Nenhum canal encontrado"}
        ch = items[0]
        snip = ch.get("snippet") or {}
        stats = ch.get("statistics") or {}
        return {
            "connected": True,
            "channel_id": ch.get("id"),
            "title": snip.get("title", ""),
            "handle": snip.get("customUrl", ""),
            "views": int(stats.get("viewCount") or 0),
            "subscribers": int(stats.get("subscriberCount") or 0),
            "videos": int(stats.get("videoCount") or 0),
            "privacy_default": os.getenv("YT_PRIVACY_STATUS", "public").strip() or "public",
        }
    except Exception as exc:
        return {"connected": False, "reason": str(exc)}


def publish_pack_to_youtube(
    video_path: str | Path,
    playlist_name: Optional[str] = None,
    privacy_status: Optional[str] = None,
) -> Dict:
    """Validate an MP4 Short, upload to YouTube, attach thumbnail, add to playlist, and update .publish.json."""
    from .validator import validate_generated_short

    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"Video nao encontrado: {mp4}")

    pack_path = mp4.with_suffix(".publish.json")
    pack: Dict = {}
    if pack_path.is_file():
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pack = {}

    ass_cand = mp4.parent / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass"
    from .validator import audit_short_end_to_end

    audit = audit_short_end_to_end(
        mp4,
        pack=pack,
        ass_path=ass_cand if ass_cand.is_file() else None,
        vision_check=True,
    )
    validation = audit["media"]
    pack["visual_audit"] = audit
    if not audit["approved"]:
        pack["queued_for_auto_publish"] = False
        pack["delivery_status"] = f"rejected_auto_audit: {'; '.join(audit['reject_reasons'])}"
        pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        raise RuntimeError(f"Video reprovado na validacao e auto-auditoria visual: {'; '.join(audit['reject_reasons'])}")

    title = str(pack.get("title") or mp4.stem.replace("_", " ").title()).strip()[:95]
    caption = str(pack.get("caption") or f"{title}\n\n#Shorts #Brasil").strip()
    tags = pack.get("hashtags") or ["#Shorts", "#Brasil"]

    yt_res = publish_youtube_short(
        mp4,
        title=title,
        description=caption,
        tags=tags,
        privacy_status=privacy_status,
    )
    vid = yt_res.get("video_id")
    playlist_id = None
    thumb_uploaded = False

    if vid:
        pl_title = (playlist_name or "").strip()
        if not pl_title:
            niche = pack.get("niche", "geral")
            pl_title = f"{NICHES.get(niche, NICHES['geral']).label} - Shorts"
        try:
            playlist_id = ensure_youtube_playlist(pl_title, description=f"Cortes automaticos: {pl_title}")
            add_video_to_playlist(playlist_id, vid)
        except Exception:
            playlist_id = None

        thumb_16 = mp4.with_name(f"{mp4.stem}_thumb_16x9.jpg")
        if thumb_16.is_file():
            try:
                set_youtube_thumbnail(vid, thumb_16)
                thumb_uploaded = True
            except Exception:
                thumb_uploaded = False

    yt_record = {
        "video_id": vid,
        "url": yt_res.get("url"),
        "privacy": yt_res.get("privacy"),
        "playlist_id": playlist_id,
        "thumbnail_uploaded": thumb_uploaded,
    }
    pack["validation"] = validation
    pack["youtube"] = yt_record
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**yt_record, "title": title, "validation": validation}


def optimize_existing_publish_pack(mp4_path: str | Path, ass_path: Optional[Path] = None) -> Dict:
    """Validate and self-heal an existing MP4's .publish.json (titles, hooks, 3-5 tags, algorithm score)."""
    from .config import get_niche_badge
    from .highlights import _clean_source_title, _looks_english_title, _polish_hook_phrase, _translate_title_to_ptbr
    from .re_engine import score_short_opus_runbook
    from .thumbnail import generate_advanced_thumbnail
    from .validator import validate_generated_short
    from .yt_algorithm import score_short_for_youtube_algorithm

    mp4 = Path(mp4_path)
    if ass_path is None:
        for cand in (
            mp4.parent / f"_narrate_{mp4.stem}" / f"{mp4.stem}.ass",
            mp4.with_suffix(".ass"),
            mp4.with_suffix(".srt"),
        ):
            if cand.is_file():
                ass_path = cand
                break
    pack_path = mp4.with_suffix(".publish.json")
    pack: Dict = {}
    if pack_path.is_file():
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pack = {}

    if not pack.get("niche"):
        stem_low = mp4.stem.lower()
        pack["niche"] = "noticias_mundiais" if stem_low.startswith("mundo_br_") else "podcast"
    niche = str(pack.get("niche") or "podcast")
    platform = str(pack.get("platform") or "youtube_shorts")

    # Heal title (recover missing, sanitize greetings/quotes/>> markers, or translate English clickbait to clean PT-BR)
    title = _clean_source_title(str(pack.get("title") or ""))
    bad_title_markers = (
        not title,
        title == mp4.name,
        title.endswith(".mp4"),
        "destaque podcast" in title.lower(),
        "salve, salve" in title.lower(),
        title.lower().startswith(("senado.", "isso foi uma grande")),
        len(title.split()) < 3,
    )
    if any(bad_title_markers):
        cap_lines = [
            _clean_source_title(ln) for ln in str(pack.get("caption") or "").splitlines()
            if ln.strip() and not ln.strip().startswith("#") and not ln.lower().startswith("destaque:")
        ]
        good_cap = next(
            (
                ln for ln in cap_lines
                if len(ln.split()) >= 4 and "salve, salve" not in ln.lower() and "destaque podcast" not in ln.lower()
                and "autoshorts" not in ln.lower()
            ),
            "",
        )
        title = good_cap or title or f"Corte Viral de {get_niche_badge(niche).title()}"
    if _looks_english_title(title):
        pt = _translate_title_to_ptbr(title)
        if pt:
            title = pt.title() if pt.isupper() else pt
        else:
            title = f"Corte Especial de {get_niche_badge(niche).title()}"
    pack["title"] = _clean_source_title(title)[:95]

    # Heal hook banner (concise, complete phrase <= 30 chars, never cut mid-word or retain '>>' / greeting)
    raw_hook = _clean_source_title(str(pack.get("hook_title") or ""))
    bad_hook = (
        not raw_hook
        or len(raw_hook) > 34
        or raw_hook.endswith(".MP4")
        or ">>" in str(pack.get("hook_title") or "")
        or "salve, salve" in raw_hook.lower()
        or "autoshorts" in raw_hook.lower()
        or raw_hook.lower().endswith((" hip", " toda", " alguns", " grande", " ainda", " bem"))
    )
    if bad_hook:
        seed_words = [w for w in pack["title"].replace("|", " ").split() if len(w) > 1]
        hook = _polish_hook_phrase(seed_words, max_chars=28) or "DESTAQUE DE HOJE"
    else:
        hook = _polish_hook_phrase(raw_hook.split(), max_chars=30) or raw_hook[:28].upper()
    pack["hook_title"] = hook

    # Enforce 3-5 clean segmented hashtags (fixes 6-tag algorithm warning)
    tags = [t for t in list(pack.get("hashtags") or []) if str(t).startswith("#")]
    if not tags:
        tags = ["#podcast", "#podcastbrasil", "#cortes", "#Shorts"]
    if "#Shorts" not in tags:
        tags.append("#Shorts")
    while len(tags) > 5:
        drop_idx = next((i for i, t in enumerate(tags) if t != "#Shorts"), 0)
        tags.pop(drop_idx)
    pack["hashtags"] = tags

    if not pack.get("caption") or len(str(pack.get("caption"))) < 45:
        pack["caption"] = (
            f"{pack['title']}\nDestaque: {pack['hook_title']}\n\n"
            "Corte vertical otimizado em ritmo alto e legendas dinamicas em PT-BR.\n"
            "Comenta sua opiniao e se inscreva para os proximos!\n\n"
            + " ".join(tags)
        )
    else:
        # Replace old trailing hashtag line so caption matches healed 3-5 tags
        cap_lines = [ln for ln in str(pack["caption"]).splitlines()]
        if cap_lines and cap_lines[-1].strip().startswith("#"):
            cap_lines[-1] = " ".join(tags)
            pack["caption"] = "\n".join(cap_lines)

    prev_cues = int((pack.get("validation") or {}).get("subtitle_cues") or 0)
    is_tt = "tiktok" in (str(pack.get("platform") or platform) + " " + mp4.name).lower()
    if is_tt and platform == "youtube_shorts":
        platform = "tiktok_rewards"
    max_dur = 180.0 if is_tt else 60.0
    val_kwargs = {"ass_path": ass_path, **({"max_duration": max_dur} if max_dur != 60.0 else {})}
    validation = validate_generated_short(mp4, **val_kwargs)
    if prev_cues > 0 and int(validation.get("subtitle_cues") or 0) == 0:
        validation["subtitle_cues"] = prev_cues
        validation["subtitle_overlaps"] = int((pack.get("validation") or {}).get("subtitle_overlaps") or 0)
    pack["validation"] = validation
    pack["platform"] = platform
    pack["output_path"] = str(mp4)

    # Regenerate clean 16:9 / 9:16 thumbnails with healed badge & hook if missing
    thumb_16 = mp4.with_name(f"{mp4.stem}_thumb_16x9.jpg")
    cover_9 = mp4.with_name(f"{mp4.stem}_cover_9x16.jpg")
    if validation.get("valid") and (not thumb_16.is_file() or not cover_9.is_file()):
        try:
            dur = float(validation.get("duration") or 15.0)
            ts = max(1.0, min(8.0, dur * 0.22))
            badge = get_niche_badge(niche)
            if not thumb_16.is_file():
                generate_advanced_thumbnail(mp4, thumb_16, pack["hook_title"], badge=badge, timestamp_sec=ts, vertical_cover=False)
            if not cover_9.is_file():
                generate_advanced_thumbnail(mp4, cover_9, pack["hook_title"], badge=badge, timestamp_sec=ts, vertical_cover=True)
            if thumb_16.is_file():
                pack["thumbnail_16x9"] = str(thumb_16)
            if cover_9.is_file():
                pack["cover_9x16"] = str(cover_9)
        except Exception:
            pass

    from .validator import audit_short_end_to_end

    visual_audit = audit_short_end_to_end(mp4, pack=pack, ass_path=ass_path, vision_check=True, media_val=validation)
    pack["visual_audit"] = visual_audit
    pack["queued_for_auto_publish"] = bool(visual_audit.get("approved") and not (pack.get("youtube") or {}).get("video_id"))
    if (pack.get("youtube") or {}).get("video_id"):
        pack["delivery_status"] = f"published_youtube_api:{pack['youtube']['video_id']}"
    else:
        pack["delivery_status"] = "approved_queued" if visual_audit.get("approved") else "rejected_auto_audit"
    pack["algorithm"] = score_short_for_youtube_algorithm(pack, validation, mp4.name)
    pack["opus_scorecard"] = score_short_opus_runbook(pack, validation=validation, duration=float(validation.get("duration") or 0.0))
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return pack


def publish_pack_to_instagram_reels(
    video_path: str | Path,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict:
    """Publish a validated vertical Short as an Instagram Reel via instagrapi when credentials exist."""
    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4}")

    ig_user = (username or os.getenv("IG_USERNAME", "")).strip()
    ig_pass = (password or os.getenv("IG_PASSWORD", "")).strip()
    if not ig_user or not ig_pass:
        return {"status": "skipped_unconfigured", "reason": "IG_USERNAME/IG_PASSWORD nao configurados no .env"}

    pack_path = mp4.with_suffix(".publish.json")
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.is_file() else {}
    caption = str(pack.get("caption") or pack.get("title") or mp4.stem)[:2000]

    from instagrapi import Client  # type: ignore

    cl = Client()
    sess_file = mp4.parent / ".ig_session.json"
    if sess_file.is_file():
        try:
            cl.load_settings(str(sess_file))
        except Exception:
            pass
    cl.login(ig_user, ig_pass)
    try:
        cl.dump_settings(str(sess_file))
    except Exception:
        pass
    media = cl.clip_upload(mp4, caption)
    code = getattr(media, "code", "") or ""
    ig_url = f"https://www.instagram.com/reel/{code}/" if code else ""
    ig_info = {"media_pk": str(getattr(media, "pk", "")), "code": code, "url": ig_url}
    pack["instagram"] = ig_info
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "published_instagram", **ig_info}


TIKTOK_SINGLE_CHUNK_MAX_BYTES = 64 * 1024 * 1024
TIKTOK_DEFAULT_CHUNK_BYTES = 10 * 1024 * 1024
TIKTOK_INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
TIKTOK_DIRECT_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def compute_tiktok_chunk_plan(video_size: int) -> Tuple[int, int]:
    """Compute TikTok Content Posting API v2 (chunk_size, total_chunk_count) using floor semantics."""
    if video_size <= 0:
        raise ValueError("Video file is empty.")
    if video_size <= TIKTOK_SINGLE_CHUNK_MAX_BYTES:
        return video_size, 1
    chunk_size = TIKTOK_DEFAULT_CHUNK_BYTES
    # TikTok v2 requires floor(video_size / chunk_size); trailing bytes merge into the final chunk.
    return chunk_size, video_size // chunk_size


def refresh_tiktok_access_token(client_key: str, client_secret: str, refresh_token: str) -> Dict:
    """Exchange a TikTok OAuth2 refresh_token for a fresh access_token."""
    form = urllib.parse.urlencode({
        "client_key": client_key.strip(),
        "client_secret": client_secret.strip(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token.strip(),
    }).encode("utf-8")
    req = urllib.request.Request(
        TIKTOK_OAUTH_TOKEN_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("access_token"):
        raise RuntimeError(f"TikTok token refresh failed: {data}")
    return data


def _tiktok_json_post(url: str, access_token: str, payload: Dict) -> Dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tiktok_upload_chunks(upload_url: str, mp4_path: Path, video_size: int, chunk_size: int, total_chunks: int) -> None:
    """Stream video slices sequentially to TikTok upload_url with Content-Range headers."""
    with mp4_path.open("rb") as fh:
        for idx in range(total_chunks):
            start = idx * chunk_size
            end = (video_size - 1) if idx == total_chunks - 1 else ((idx + 1) * chunk_size - 1)
            fh.seek(start)
            data = fh.read(end - start + 1)
            req = urllib.request.Request(
                upload_url,
                data=data,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(data)),
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                },
                method="PUT",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                if getattr(resp, "status", 200) not in (200, 201, 206):
                    raise RuntimeError(f"TikTok chunk {idx + 1}/{total_chunks} failed with HTTP {resp.status}")


def _resolve_tiktok_access_token(explicit_token: Optional[str]) -> str:
    token = (explicit_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")).strip()
    if token:
        return token
    ckey = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    csec = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    rtok = os.getenv("TIKTOK_REFRESH_TOKEN", "").strip()
    if ckey and csec and rtok:
        refreshed = refresh_tiktok_access_token(ckey, csec, rtok)
        return str(refreshed.get("access_token") or "").strip()
    return ""


def publish_pack_to_tiktok(
    video_path: Path,
    mode: Optional[str] = None,
    access_token: Optional[str] = None,
    privacy_level: Optional[str] = None,
) -> Dict:
    """Upload a generated MP4 to TikTok via Content Posting API v2 (inbox draft or direct post)."""
    mp4 = Path(video_path)
    if not mp4.is_file():
        raise FileNotFoundError(f"Video not found: {mp4}")

    token = _resolve_tiktok_access_token(access_token)
    if not token:
        return {
            "status": "skipped_unconfigured",
            "reason": "Defina TIKTOK_ACCESS_TOKEN ou rode scripts/tiktok_auth.py para publicar no TikTok.",
        }

    pack_path = mp4.with_suffix(".publish.json")
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
    target_mode = (mode or os.getenv("TIKTOK_PUBLISH_MODE", "inbox") or "inbox").strip().lower()
    if target_mode not in ("inbox", "direct"):
        target_mode = "inbox"

    video_size = mp4.stat().st_size
    chunk_size, total_chunks = compute_tiktok_chunk_plan(video_size)
    source_info = {
        "source": "FILE_UPLOAD",
        "video_size": video_size,
        "chunk_size": chunk_size,
        "total_chunk_count": total_chunks,
    }

    if target_mode == "direct":
        endpoint = TIKTOK_DIRECT_INIT_URL
        caption = (pack.get("caption") or pack.get("title") or mp4.stem).strip()[:2200]
        priv = (privacy_level or os.getenv("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY") or "SELF_ONLY").strip()
        payload = {
            "post_info": {
                "title": caption,
                "privacy_level": priv,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": source_info,
        }
    else:
        endpoint = TIKTOK_INBOX_INIT_URL
        payload = {"source_info": source_info}

    try:
        init_res = _tiktok_json_post(endpoint, token, payload)
    except urllib.error.HTTPError as exc:
        ckey = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
        csec = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
        rtok = os.getenv("TIKTOK_REFRESH_TOKEN", "").strip()
        if exc.code == 401 and ckey and csec and rtok:
            refreshed = refresh_tiktok_access_token(ckey, csec, rtok)
            token = str(refreshed["access_token"])
            init_res = _tiktok_json_post(endpoint, token, payload)
        else:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"TikTok API init error ({exc.code}): {detail or exc.reason}") from exc

    err = init_res.get("error") or {}
    if err.get("code") and err.get("code") != "ok":
        raise RuntimeError(f"TikTok API rejected upload ({err.get('code')}): {err.get('message', '')}")

    data = init_res.get("data") or {}
    publish_id = str(data.get("publish_id") or "").strip()
    upload_url = str(data.get("upload_url") or "").strip()
    if not publish_id or not upload_url:
        raise RuntimeError(f"Unexpected TikTok init response: {init_res}")

    _tiktok_upload_chunks(upload_url, mp4, video_size, chunk_size, total_chunks)
    tt_info = {
        "publish_id": publish_id,
        "mode": target_mode,
        "chunks": total_chunks,
        "size_bytes": video_size,
    }
    pack["tiktok"] = tt_info
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": f"published_tiktok_{target_mode}", **tt_info}


