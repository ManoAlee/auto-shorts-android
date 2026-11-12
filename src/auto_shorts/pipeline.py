"""End-to-end automated mobile shorts pipeline."""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import NICHES, QUALITY_PRESETS, get_niche_badge
from .discovery import discover_videos
from .downloader import download_video_and_subs, is_url, load_source_metadata, transcribe_with_whisper_cpp
from .evolution import EvolutionStore
from .highlights import detect_highlights, heal_proper_nouns_and_asr
from .publisher import (
    add_video_to_playlist,
    build_publish_pack,
    dispatch_webhook,
    ensure_youtube_playlist,
    export_to_android_gallery,
    publish_instagram_reel,
    publish_pack_to_tiktok,
    publish_youtube_short,
    set_youtube_thumbnail,
)
from .renderer import cut_segment_temp, render_clip, trim_silence_concat
from .retention import get_retention_profile
from .silence import detect_speech_intervals, remap_transcript_segments
from .subtitles import generate_ass_subtitles
from .thumbnail import generate_advanced_thumbnail
from .transcript import load_transcript
from .validator import validate_generated_short
from .yt_algorithm import score_short_for_youtube_algorithm


def _heal_segments(segments: List[Dict]) -> List[Dict]:
    healed: List[Dict] = []
    for seg in segments:
        copy_seg = dict(seg)
        copy_seg["text"] = heal_proper_nouns_and_asr(str(seg.get("text") or ""))
        if isinstance(seg.get("words"), list):
            copy_seg["words"] = [
                {**w, "word": heal_proper_nouns_and_asr(str(w.get("word") or ""))}
                for w in seg["words"]
            ]
        healed.append(copy_seg)
    return healed


def _build_clip_subtitles_and_summary(
    render_src: Path,
    render_dur: float,
    fallback_segments: List[Dict],
    fallback_start: float,
    fallback_end: float,
    ass_file: Path,
    width: int,
    height: int,
    work_dir: Path,
    whisper_model: Optional[str],
    language: str,
    relative_to_clip: bool,
) -> Optional[str]:
    """Use clean healed source subtitles when available; fall back to clip-level whisper.cpp when needed."""
    healed_fallback = _heal_segments(fallback_segments)
    win_segs = [
        s for s in healed_fallback
        if float(s.get("end", 0.0)) > fallback_start and float(s.get("start", 0.0)) < fallback_end
    ]
    has_rich_fallback = len(win_segs) >= 3 and any(isinstance(s.get("words"), list) and s.get("words") for s in win_segs)

    if not has_rich_fallback and os.getenv("USE_CLIP_WHISPER", "1") == "1" and (shutil.which("whisper-cli") or shutil.which("main")):
        try:
            asr_dir = work_dir / f"_asr_{ass_file.stem}"
            asr_dir.mkdir(parents=True, exist_ok=True)
            sub_path = transcribe_with_whisper_cpp(
                render_src, asr_dir, model_path=whisper_model, language=language
            )
            tr = load_transcript(sub_path)
            segs = _heal_segments(tr.get("segments") or [])
            if segs:
                generate_ass_subtitles(
                    segs, 0.0, render_dur, ass_file, width=width, height=height, relative_to_clip=True
                )
                return " ".join(s.get("text", "").strip() for s in segs if s.get("text")).strip()[:340]
        except Exception:
            pass

    generate_ass_subtitles(
        healed_fallback,
        fallback_start,
        fallback_end,
        ass_file,
        width=width,
        height=height,
        relative_to_clip=relative_to_clip,
    )
    if win_segs:
        return " ".join(s.get("text", "").strip() for s in win_segs if s.get("text")).strip()[:340]
    return None


def _probe_duration(video_path: Path) -> float:
    import subprocess

    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float((proc.stdout or "0").strip())
    except ValueError:
        return 0.0


def run_pipeline(
    source: str,
    out_dir: str | Path = "output",
    platform: str = "tiktok_rewards",
    niche: str = "geral",
    num_clips: int = 3,
    layout: str = "blur_bg",
    quality: str = "mobile",
    encoder: str = "libx264",
    srt_path: Optional[str] = None,
    whisper_model: Optional[str] = None,
    language: str = "pt",
    trim_silence: bool = True,
    use_llm: bool = True,
    auto_layout: bool = False,
    cookies_path: Optional[str] = None,
    file_prefix: str = "",
    source_meta: Optional[Dict[str, str]] = None,
    playlist_name: Optional[str] = None,
    auto_publish: bool = True,
) -> Dict:
    """Execute ingest -> transcribe -> highlight ranking -> silence cut -> 9:16 render."""
    out_root = Path(out_dir)
    run_tag = "".join(ch for ch in (file_prefix or "") if ch.isalnum() or ch in "_-") or str(int(time.time() * 1000))
    work_dir = out_root / f"_work_{run_tag}"
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    store = EvolutionStore(out_root / "shorts_evolution.db")
    chosen_layout = store.recommend_layout(niche) if auto_layout else layout
    learning_context = store.build_learning_context(niche)
    resolved_meta: Dict = dict(source_meta or {})

    detected_sub: Optional[Path] = Path(srt_path) if srt_path else None
    from .downloader import is_gdrive_url, is_rclone_target, download_from_gdrive, download_from_rclone

    if is_gdrive_url(source):
        video_path = download_from_gdrive(source, work_dir)
        if not resolved_meta.get("title"):
            resolved_meta["title"] = video_path.stem.replace("_", " ").title()
    elif is_rclone_target(source):
        video_path = download_from_rclone(source, work_dir)
        if not resolved_meta.get("title"):
            resolved_meta["title"] = video_path.stem.replace("_", " ").title()
    elif is_url(source):
        max_h = 1080 if quality == "high" else 720
        video_path, yt_sub = download_video_and_subs(
            source, work_dir, max_height=max_h, cookies_path=cookies_path
        )
        info_meta = load_source_metadata(work_dir)
        for k, v in info_meta.items():
            if v and not resolved_meta.get(k):
                resolved_meta[k] = v
        if not resolved_meta.get("webpage_url"):
            resolved_meta["webpage_url"] = source
        if detected_sub is None:
            detected_sub = yt_sub
    else:
        if not str(source or "").strip():
            raise ValueError("Source video URL or file path cannot be empty")
        video_path = Path(source)
        if not video_path.is_file():
            raise FileNotFoundError(f"Source video not found: {video_path}")
        if detected_sub is None:
            for ext in (".srt", ".vtt", ".json"):
                sibling = video_path.with_suffix(ext)
                if sibling.exists():
                    detected_sub = sibling
                    break

    if detected_sub is None:
        detected_sub = transcribe_with_whisper_cpp(video_path, work_dir, model_path=whisper_model, language=language)

    transcript = load_transcript(detected_sub)
    if transcript["duration"] <= 0:
        transcript["duration"] = _probe_duration(video_path)

    highlights = detect_highlights(
        transcript=transcript,
        platform_key=platform,
        niche_key=niche,
        num_clips=num_clips,
        use_llm=use_llm,
        learning_context=learning_context,
        source_title=str(resolved_meta.get("title") or ""),
        heatmap=resolved_meta.get("heatmap") if isinstance(resolved_meta.get("heatmap"), list) else None,
    )

    q_cfg = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["mobile"])
    width, height = int(q_cfg["width"]), int(q_cfg["height"])
    retention = get_retention_profile(platform)
    punch_zoom = retention.punch_zoom

    rendered: List[Dict] = []
    for idx, clip in enumerate(highlights, start=1):
        start = float(clip["start_time"])
        end = float(clip["end_time"])
        # Safe filename with NO apostrophes (openshorts filtergraph lesson).
        prefix = f"{file_prefix}_" if file_prefix else ""
        out_mp4 = out_root / f"{prefix}short_{idx:02d}_{platform}.mp4"
        ass_file = work_dir / f"subs_{idx:02d}.ass"

        if trim_silence:
            raw_cut = cut_segment_temp(video_path, start, end, work_dir / f"raw_{idx:02d}.mp4")
            clip_dur = max(0.1, end - start)
            speech_ranges = detect_speech_intervals(
                str(raw_cut),
                total_duration=clip_dur,
                min_silence=max(0.85, retention.min_silence_sec),
            )
            if len(speech_ranges) > 1 or (speech_ranges and (speech_ranges[0][0] > 0.2 or speech_ranges[-1][1] < clip_dur - 0.3)):
                jump_cut = trim_silence_concat(raw_cut, speech_ranges, work_dir / f"jump_{idx:02d}.mp4")
                rel_segs = [
                    {
                        "start": max(0.0, float(s["start"]) - start),
                        "end": min(clip_dur, float(s["end"]) - start),
                        "text": s["text"],
                        **(
                            {
                                "words": [
                                    {
                                        "word": w["word"],
                                        "start": max(0.0, float(w["start"]) - start),
                                        "end": min(clip_dur, float(w["end"]) - start),
                                    }
                                    for w in s["words"]
                                    if float(w["end"]) > start and float(w["start"]) < end
                                ]
                            }
                            if isinstance(s.get("words"), list)
                            else {}
                        ),
                    }
                    for s in transcript["segments"]
                    if float(s["end"]) > start and float(s["start"]) < end
                ]
                remapped = remap_transcript_segments(rel_segs, speech_ranges)
                new_dur = sum(e - s for s, e in speech_ranges)
                clean_sum = _build_clip_subtitles_and_summary(
                    jump_cut, new_dur, remapped, 0.0, new_dur,
                    ass_file, width, height, work_dir, whisper_model, language, True,
                )
                if clean_sum:
                    clip["clip_summary"] = clean_sum
                render_clip(
                    source_path=jump_cut,
                    out_path=out_mp4,
                    start_time=0.0,
                    end_time=new_dur,
                    layout=chosen_layout,
                    quality=quality,
                    ass_path=ass_file,
                    hook_title=clip.get("hook_title", ""),
                    encoder=encoder,
                    punch_zoom=punch_zoom,
                )
            else:
                clean_sum = _build_clip_subtitles_and_summary(
                    raw_cut, clip_dur, transcript["segments"], start, end,
                    ass_file, width, height, work_dir, whisper_model, language, True,
                )
                if clean_sum:
                    clip["clip_summary"] = clean_sum
                render_clip(
                    source_path=raw_cut,
                    out_path=out_mp4,
                    start_time=0.0,
                    end_time=clip_dur,
                    layout=chosen_layout,
                    quality=quality,
                    ass_path=ass_file,
                    hook_title=clip.get("hook_title", ""),
                    encoder=encoder,
                    punch_zoom=punch_zoom,
                )
        else:
            generate_ass_subtitles(
                transcript["segments"], start, end, ass_file, width=width, height=height
            )
            render_clip(
                source_path=video_path,
                out_path=out_mp4,
                start_time=start,
                end_time=end,
                layout=chosen_layout,
                quality=quality,
                ass_path=ass_file,
                hook_title=clip.get("hook_title", ""),
                encoder=encoder,
                punch_zoom=punch_zoom,
            )

        clip_id = store.record_clip(
            source=source,
            platform=platform,
            niche=niche,
            layout=chosen_layout,
            duration_sec=max(0.1, end - start),
            hook_title=clip.get("hook_title", ""),
            predicted_score=int(clip.get("score", 50)),
            output_path=str(out_mp4),
        )
        export_to_android_gallery(out_mp4)
        badge = get_niche_badge(niche)
        thumb_ts = max(1.0, min(8.0, (end - start) * 0.20))
        thumb_16x9 = out_mp4.with_name(f"{out_mp4.stem}_thumb_16x9.jpg")
        cover_9x16 = out_mp4.with_name(f"{out_mp4.stem}_cover_9x16.jpg")
        try:
            generate_advanced_thumbnail(out_mp4, thumb_16x9, clip.get("hook_title", ""), badge=badge, timestamp_sec=thumb_ts, vertical_cover=False)
            generate_advanced_thumbnail(out_mp4, cover_9x16, clip.get("hook_title", ""), badge=badge, timestamp_sec=thumb_ts, vertical_cover=True)
        except Exception:
            thumb_16x9 = None
            cover_9x16 = None

        if ass_file.is_file():
            try:
                shutil.copy2(ass_file, out_mp4.with_suffix(".ass"))
            except OSError:
                pass

        max_dur_val = 180.0 if "tiktok" in str(platform).lower() else 60.0
        validation = validate_generated_short(out_mp4, ass_path=ass_file, max_duration=max_dur_val)
        pack = build_publish_pack(
            {**clip, "output_path": str(out_mp4), "clip_id": clip_id},
            platform,
            niche,
            source_meta=resolved_meta,
        )
        if thumb_16x9 and thumb_16x9.exists():
            pack["thumbnail_16x9"] = str(thumb_16x9)
        if cover_9x16 and cover_9x16.exists():
            pack["cover_9x16"] = str(cover_9x16)
        from .validator import audit_short_end_to_end

        visual_audit = audit_short_end_to_end(out_mp4, pack=pack, ass_path=ass_file if ass_file.is_file() else None, vision_check=False)
        pack["validation"] = validation
        pack["visual_audit"] = visual_audit
        pack["algorithm"] = score_short_for_youtube_algorithm(pack, validation, out_mp4.name)
        pack["queued_for_auto_publish"] = bool(visual_audit.get("approved"))
        pack["delivery_status"] = "approved_queued" if visual_audit.get("approved") else "rejected_auto_audit"
        pack_json = out_mp4.with_suffix(".publish.json")
        pack_json.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")

        delivery_status = pack["delivery_status"]
        playlist_id = None
        if not auto_publish:
            delivery_status = "approved_queued" if visual_audit.get("approved") else "rejected_auto_audit"
        elif not visual_audit.get("approved"):
            delivery_status = f"rejected_auto_audit: {'; '.join(visual_audit.get('reject_reasons') or [])}"
        elif not validation["valid"]:
            delivery_status = f"validation_blocked: {'; '.join(validation['errors'])}"
        else:
            try:
                if dispatch_webhook(pack) is not None:
                    delivery_status = "dispatched_webhook"
                elif platform == "instagram_reels" and os.getenv("IG_USER_ID") and os.getenv("IG_ACCESS_TOKEN") and os.getenv("REELS_PUBLIC_BASE_URL"):
                    pub_url = f"{os.getenv('REELS_PUBLIC_BASE_URL').rstrip('/')}/{out_mp4.name}"
                    publish_instagram_reel(pub_url, pack["caption"])
                    delivery_status = "published_instagram_api"
                elif platform == "tiktok_rewards" and (os.getenv("TIKTOK_ACCESS_TOKEN") or (os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_CLIENT_SECRET") and os.getenv("TIKTOK_REFRESH_TOKEN"))):
                    tt_res = publish_pack_to_tiktok(out_mp4)
                    delivery_status = f"published_tiktok_api:{tt_res.get('publish_id', '')}"
                elif platform == "youtube_shorts" and os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and os.getenv("YT_REFRESH_TOKEN"):
                    yt_res = publish_youtube_short(out_mp4, pack["title"], pack["caption"], tags=pack["hashtags"])
                    vid = yt_res.get("video_id")
                    delivery_status = f"published_youtube_api:{vid}"
                    if vid:
                        pl_title = playlist_name or f"{NICHES.get(niche, NICHES['geral']).label} - Shorts"
                        try:
                            playlist_id = ensure_youtube_playlist(pl_title, description=f"Cortes automaticos de {niche}")
                            add_video_to_playlist(playlist_id, vid)
                        except Exception:
                            pass
                        if thumb_16x9 and thumb_16x9.exists():
                            try:
                                set_youtube_thumbnail(vid, thumb_16x9)
                            except Exception:
                                pass
                        pack["youtube"] = {
                            "video_id": vid,
                            "url": yt_res.get("url"),
                            "privacy": yt_res.get("privacy"),
                            "playlist_id": playlist_id,
                        }
                        pack_json.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                msg = str(exc)
                if "uploadLimitExceeded" in msg:
                    delivery_status = f"queued_quota_limit: {msg[:180]}"
                    pack["queued_for_auto_publish"] = True
                    pack["delivery_status"] = delivery_status
                    pack_json.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
                else:
                    delivery_status = f"delivery_error: {msg}"

        # Auto-backup rendered shorts to Google Drive 5TB (if configured)
        from .downloader import upload_to_rclone
        uploaded_ok = False
        try:
            uploaded_ok = upload_to_rclone(out_mp4, "gdrive:Shorts_Finalizados")
            if thumb_16x9 and thumb_16x9.is_file():
                upload_to_rclone(thumb_16x9, "gdrive:Shorts_Finalizados")
            if cover_9x16 and cover_9x16.is_file():
                upload_to_rclone(cover_9x16, "gdrive:Shorts_Finalizados")
        except Exception:
            pass

        if uploaded_ok and os.getenv("AUTO_PURGE_LOCAL_AFTER_DRIVE", "1") == "1":
            try:
                keep_n = max(1, int(os.getenv("MAX_LOCAL_MP4_KEEP", "3")))
                mp4s = sorted(out_root.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
                for old_mp4 in mp4s[keep_n:]:
                    if old_mp4 != out_mp4 and old_mp4.is_file():
                        old_mp4.unlink(missing_ok=True)
            except Exception:
                pass

        rendered.append({
            **clip,
            "clip_id": clip_id,
            "output_path": str(out_mp4),
            "thumbnail_16x9": str(thumb_16x9) if thumb_16x9 else None,
            "cover_9x16": str(cover_9x16) if cover_9x16 else None,
            "playlist_id": playlist_id,
            "validation": validation,
            "publish_pack": pack,
            "delivery_status": delivery_status,
        })

    manifest_path = out_root / "manifest.json"
    manifest = {
        "source": source,
        "platform": platform,
        "niche": niche,
        "layout": chosen_layout,
        "quality": quality,
        "clips": rendered,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work_dir, ignore_errors=True)
    return manifest


def run_autopilot(
    out_dir: str | Path = "output",
    platform: str = "tiktok_rewards",
    niche: str = "geral",
    query: Optional[str] = None,
    channel_url: Optional[str] = None,
    search_limit: int = 8,
    auto_count: int = 1,
    num_clips: int = 3,
    layout: str = "blur_bg",
    quality: str = "mobile",
    encoder: str = "libx264",
    whisper_model: Optional[str] = None,
    language: str = "pt",
    trim_silence: bool = True,
    use_llm: bool = True,
    auto_layout: bool = True,
    cookies_path: Optional[str] = None,
    dry_run: bool = False,
    playlist_name: Optional[str] = None,
    auto_publish: bool = True,
) -> Dict:
    """Discover real unprocessed videos for the niche (or 'all' rotating) and run pipeline."""
    out_root = Path(out_dir)
    store = EvolutionStore(out_root / "shorts_evolution.db")
    seen_ids = set(store.get_processed_ids())
    if out_root.is_dir():
        for existing_mp4 in out_root.glob("*_short_*.mp4"):
            vid_prefix = existing_mp4.name.split("_short_", 1)[0]
            if vid_prefix:
                seen_ids.add(vid_prefix)

    target_niches = (
        ["podcast", "financas", "ia_tech", "desenvolvimento_pessoal", "saude_fitness", "concursos", "entretenimento_animes"]
        if niche == "all"
        else [niche]
    )

    # Prioridade 1: Se houver vídeos pendentes no Google Drive na pasta Animes_Para_Cortar
    from .downloader import list_gdrive_episodes
    gdrive_items = []
    if niche in {"entretenimento_animes", "all"}:
        try:
            gdrive_files = list_gdrive_episodes("gdrive:Animes_Para_Cortar")
            for gf in gdrive_files:
                gf_name = Path(gf).name
                if gf_name not in seen_ids:
                    gdrive_items.append({
                        "id": gf_name,
                        "url": gf,
                        "title": Path(gf_name).stem.replace("_", " ").title(),
                        "channel": "Google Drive 5TB",
                        "_niche": "entretenimento_animes",
                    })
        except Exception:
            pass

    all_candidates: List[Dict] = list(gdrive_items)
    for active_niche in target_niches:
        found = discover_videos(
            niche=active_niche,
            query=query,
            source_url=channel_url,
            limit=search_limit,
            seen_ids=seen_ids,
            cookies_path=cookies_path,
        )
        for cand in found:
            cand["_niche"] = active_niche
        if found:
            all_candidates.extend(found[: (1 if niche == "all" else max(1, auto_count))])

    selected = all_candidates[:max(1, auto_count if niche != "all" else len(all_candidates))]

    if dry_run:
        return {
            "mode": "discover_dry_run",
            "niche": niche,
            "discovered_count": len(all_candidates),
            "candidates": all_candidates,
        }

    runs: List[Dict] = []
    for item in selected:
        item_niche = item.get("_niche", niche)
        res = run_pipeline(
            source=item["url"],
            out_dir=out_root,
            platform=platform,
            niche=item_niche,
            num_clips=num_clips,
            layout=layout,
            quality=quality,
            encoder=encoder,
            whisper_model=whisper_model,
            language=language,
            trim_silence=trim_silence,
            use_llm=use_llm,
            auto_layout=auto_layout,
            cookies_path=cookies_path,
            file_prefix=item["id"],
            playlist_name=playlist_name,
            auto_publish=auto_publish,
            source_meta={
                "title": item.get("title", ""),
                "channel": item.get("channel", ""),
                "webpage_url": item.get("url", ""),
            },
        )
        store.mark_source_processed(item["id"], item["url"], item["title"], item_niche)
        runs.append({"video": item, "niche": item_niche, "result": res})

    return {
        "mode": "autopilot",
        "niche": niche,
        "processed_count": len(runs),
        "runs": runs,
    }
