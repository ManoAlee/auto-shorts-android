"""World journalism & international news-to-Brazil adapter using zero-key Public APIs."""

import datetime as _dt
import html
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .highlights import call_gemini_or_openai
from .team import humanize_ptbr_script, is_llm_configured

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    txt = html.unescape(_HTML_TAG_RE.sub(" ", raw or ""))
    return " ".join(txt.split()).strip()


def _http_get_text(url: str, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AutoShorts-WorldNews/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_rss_image(item: ET.Element) -> str:
    best = ""
    for el in item.iter():
        if el.tag.endswith(("thumbnail", "content", "enclosure")):
            u = (el.attrib.get("url") or "").strip()
            if u.startswith("http"):
                best = u.replace("/ace/ws/240/", "/ace/ws/800/").replace("/ace/standard/240/", "/ace/standard/800/")
                break
    return best


def _parse_rss_items(xml_text: str, source_name: str, category: str, limit: int, lang: str = "en") -> List[Dict]:
    items: List[Dict] = []
    root = ET.fromstring(xml_text)
    for item in root.findall(".//item")[:limit]:
        title = _clean_text(item.findtext("title") or "")
        desc = _clean_text(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        img = _extract_rss_image(item)
        if title and link:
            items.append({
                "id": link,
                "title": title,
                "summary": desc[:420],
                "source": source_name,
                "url": link,
                "image_url": img,
                "published_at": pub,
                "category": category,
                "lang": lang,
            })
    return items


def fetch_world_news_headlines(
    topic: str = "world",
    limit: int = 8,
    fetcher: Optional[Callable[[str], str]] = None,
) -> List[Dict]:
    """Fetch real international journalism from native PT-BR global desks & zero-auth Public APIs."""
    get = fetcher or _http_get_text
    collected: List[Dict] = []

    # 1. BBC News Brasil, Euronews PT & G1 (global/BR journalism natively in Portuguese)
    for rss_url, src_label, cat_name in (
        ("https://feeds.bbci.co.uk/portuguese/rss.xml", "BBC News Brasil", "mundo"),
        ("https://pt.euronews.com/rss?level=theme&name=news", "Euronews Mundo", "mundo"),
        ("https://g1.globo.com/rss/g1/tecnologia/", "G1 Tecnologia", "tech_ia"),
        ("https://g1.globo.com/rss/g1/economia/", "G1 Economia", "economia"),
        ("https://g1.globo.com/rss/g1/mundo/", "G1 Mundo", "mundo"),
    ):
        try:
            collected.extend(_parse_rss_items(
                get(rss_url),
                src_label,
                cat_name,
                max(3, limit // 2),
                lang="pt",
            ))
        except Exception:
            pass

    # 2. BBC World News RSS (English international press)
    try:
        collected.extend(_parse_rss_items(
            get("https://feeds.bbci.co.uk/news/world/rss.xml"),
            "BBC World News",
            "mundo",
            max(2, limit // 3),
            lang="en",
        ))
    except Exception:
        pass

    # 3. The Guardian World RSS
    try:
        collected.extend(_parse_rss_items(
            get("https://www.theguardian.com/world/rss"),
            "The Guardian",
            "mundo",
            max(2, limit // 3),
            lang="en",
        ))
    except Exception:
        pass

    # 3. Spaceflight News API v4 (from github.com/public-apis/public-apis, Auth: No)
    try:
        sf = json.loads(get("https://api.spaceflightnewsapi.net/v4/articles/?limit=6"))
        for art in sf.get("results", []):
            if art.get("title") and art.get("url"):
                collected.append({
                    "id": str(art["url"]),
                    "title": _clean_text(art["title"]),
                    "summary": _clean_text(art.get("summary") or "")[:420],
                    "source": str(art.get("news_site") or "Spaceflight News"),
                    "url": str(art["url"]),
                    "image_url": str(art.get("image_url") or ""),
                    "published_at": str(art.get("published_at") or ""),
                    "category": "ciencia_espaco",
                    "lang": "en",
                })
    except Exception:
        pass

    # 4. Wikipedia "In the news" Featured Feed (zero-auth encyclopedic current events)
    try:
        today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y/%m/%d")
        wiki = json.loads(get(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{today}"))
        for entry in (wiki.get("news") or [])[:3]:
            story_txt = _clean_text(entry.get("story") or "")
            links = entry.get("links") or []
            url = (
                links[0].get("content_urls", {}).get("desktop", {}).get("page")
                if links and isinstance(links[0], dict)
                else "https://en.wikipedia.org/wiki/Portal:Current_events"
            )
            if story_txt:
                collected.append({
                    "id": f"wiki:{story_txt[:60]}",
                    "title": story_txt[:110],
                    "summary": story_txt[:420],
                    "source": "Wikipedia Current Events",
                    "url": str(url or "https://en.wikipedia.org/wiki/Portal:Current_events"),
                    "published_at": today,
                    "category": "atualidades",
                })
    except Exception:
        pass

    # 5. Hacker News Top Stories (global tech & AI breakthroughs, zero-auth)
    if topic in ("world", "tech", "ia"):
        try:
            ids = json.loads(get("https://hacker-news.firebaseio.com/v0/topstories.json"))[:4]
            for sid in ids:
                item = json.loads(get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"))
                if isinstance(item, dict) and item.get("title"):
                    collected.append({
                        "id": f"hn:{sid}",
                        "title": _clean_text(item["title"]),
                        "summary": _clean_text(item.get("title") or ""),
                        "source": "Hacker News",
                        "url": str(item.get("url") or f"https://news.ycombinator.com/item?id={sid}"),
                        "published_at": "",
                        "category": "tech_ia",
                    })
        except Exception:
            pass

    # Deduplicate & optionally filter by topic keyword
    seen = set()
    unique: List[Dict] = []
    q = (topic or "").strip().lower()
    for row in collected:
        key = row["title"].lower()
        if key in seen:
            continue
        if q and q not in {"world", "mundo", "all", ""} and q not in f"{key} {row['summary'].lower()} {row['category']}":
            continue
        seen.add(key)
        unique.append(row)
    return unique[:limit]


def translate_en_to_ptbr(
    text: str,
    fetcher: Optional[Callable[[str], str]] = None,
) -> str:
    """Translate foreign journalism text to natural PT-BR (Google GTX -> MyMemory fallback)."""
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return ""
    get = fetcher or _http_get_text
    q = urllib.parse.quote(clean[:500])

    # 1. Google GTX zero-auth endpoint
    try:
        raw = json.loads(get(f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=pt&dt=t&q={q}"))
        parts = [seg[0] for seg in raw[0] if isinstance(seg, list) and seg and seg[0]]
        translated = " ".join(parts).strip()
        if translated:
            return translated
    except Exception:
        pass

    # 2. MyMemory zero-auth fallback
    try:
        mm = json.loads(get(f"https://api.mymemory.translated.net/get?q={q}&langpair=en|pt-BR"))
        translated = str((mm.get("responseData") or {}).get("translatedText") or "").strip()
        if translated and "MYMEMORY WARNING" not in translated.upper():
            return translated
    except Exception:
        pass

    return clean


def _build_complete_news_hook(pt_title: str, max_chars: int = 30) -> str:
    """Build a punchy uppercase hook without stopping mid-clause on a preposition/article."""
    clean = re.sub(r"\s+", " ", (pt_title or "").strip()).strip(" .,:;-|")
    if not clean:
        return "URGENTE NO MUNDO"
    words = clean.split()
    dangling = {
        "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
        "em", "na", "no", "e", "ou", "para", "por", "com", "que", "se", "mas",
        "nao", "não", "aumentar", "dizer", "diz", "ser", "ter", "vai",
    }
    chosen: List[str] = []
    for word in words:
        cand = " ".join(chosen + [word])
        if len(cand) > max_chars and len(chosen) >= 2:
            break
        chosen.append(word)
        if len(chosen) >= 5 and word.lower().strip(",.:;!?") not in dangling:
            break
    while len(chosen) > 2 and chosen[-1].lower().strip(",.:;!?") in dangling:
        # If ending cleanly on a complete noun is possible by taking one short word ahead
        idx = len(chosen)
        if idx < len(words):
            extended = " ".join(chosen + [words[idx]])
            if len(extended) <= max_chars + 4:
                chosen.append(words[idx])
                continue
        chosen.pop()
    res = " ".join(chosen).strip(" ,:;").upper()
    return (res[:max_chars].rsplit(" ", 1)[0] if len(res) > max_chars else res) or "URGENTE NO MUNDO"


def build_brazil_news_story_pack(
    story: Dict,
    use_llm: bool = True,
    translator: Optional[Callable[[str], str]] = None,
) -> Dict:
    """Convert an international headline into an engaging PT-BR breaking-news Short script."""
    tx = translator or translate_en_to_ptbr
    source_name = str(story.get("source") or "Imprensa Internacional").strip()
    orig_title = str(story.get("title") or "").strip()
    orig_summary = str(story.get("summary") or orig_title).strip()
    orig_url = str(story.get("url") or "").strip()
    is_already_pt = str(story.get("lang") or "").lower() == "pt"

    pt_title = orig_title if is_already_pt else tx(orig_title)
    pt_summary = orig_summary if is_already_pt else (tx(orig_summary) if orig_summary != orig_title else pt_title)

    hook_banner = _build_complete_news_hook(pt_title)
    short_title = pt_title[:76].rsplit(" ", 1)[0] if len(pt_title) > 76 else pt_title
    seo_title = f"{short_title} | Mundo Hoje".strip()[:90]
    script = humanize_ptbr_script(
        f"Atenção para o que acabou de sair na imprensa internacional via {source_name}! "
        f"{pt_title}. {pt_summary} "
        f"Esse tipo de movimento lá fora costuma impactar diretamente tecnologia, mercado e decisões aqui no Brasil também. "
        f"A fonte completa está na descrição — comenta o que você acha e siga para receber as notícias do mundo traduzidas todos os dias!"
    )

    if use_llm and is_llm_configured():
        prompt = (
            "Você é jornalista de plantão internacional adaptando notícias reais para o público do Brasil em Shorts (35-45s).\n"
            f"Fonte: {source_name}\nManchete em PT-BR: {pt_title}\nResumo em PT-BR: {pt_summary}\n"
            "Regras: fale como brasileiro natural, ritmo urgente e claro, explique em 1 frase por que isso importa para o Brasil, ZERO invenção de fatos.\n"
            "Responda SOMENTE JSON válido:\n"
            '{"seo_title":"max 80 chars","hook_banner":"MAX 4 PALAVRAS MAIUSCULAS SEM CORTAR FRASE","roteiro":"texto falado 70 a 105 palavras"}'
        )
        try:
            raw = call_gemini_or_openai(prompt)
            m_start, m_end = raw.find("{"), raw.rfind("}")
            if m_start != -1 and m_end > m_start:
                data = json.loads(raw[m_start:m_end + 1])
                if isinstance(data, dict) and data.get("roteiro") and len(str(data["roteiro"]).split()) >= 25:
                    script = humanize_ptbr_script(str(data["roteiro"]))
                if data.get("seo_title") and str(data["seo_title"]).strip().lower() not in {"string", "max 80 chars"}:
                    seo_title = str(data["seo_title"]).strip()[:90]
                if data.get("hook_banner") and str(data["hook_banner"]).strip().lower() not in {"string", "max 4 palavras maiusculas", "max 4 palavras maiusculas sem cortar frase"}:
                    hook_banner = str(data["hook_banner"]).strip().upper()[:30]
        except Exception:
            pass

    caption = (
        f"{seo_title}\n"
        f"Destaque: {hook_banner}\n\n"
        f"Resumo da noticia internacional:\n{pt_summary}\n\n"
        f"Fonte original ({source_name}): {orig_url}\n"
        "Comenta sua opiniao e siga o canal para ficar atualizado sobre o mundo no Brasil!\n\n"
        "#NoticiasMundiais #Mundo #Brasil #Atualidades #Shorts"
    )
    return {
        "title": seo_title,
        "hook_title": hook_banner,
        "script": script,
        "caption": caption,
        "hashtags": ["#NoticiasMundiais", "#Mundo", "#Brasil", "#Atualidades", "#Shorts"],
        "source_name": source_name,
        "source_url": orig_url,
        "pt_title": pt_title,
        "pt_summary": pt_summary,
    }


def _probe_image_dimensions(img_path: Path) -> Tuple[int, int]:
    """Read pixel width/height of a downloaded article image via ffprobe."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                str(img_path),
            ],
            text=True,
            timeout=5,
        ).strip()
        w_s, h_s = out.splitlines()[0].split("x", 1)
        return max(1, int(w_s)), max(1, int(h_s))
    except Exception:
        return 1280, 720


def _build_news_backdrop_video(image_url: str, work_dir: Path, duration_sec: float = 55.0) -> Path:
    """Create a 9:16 journalism backdrop with Ken-Burns push-in motion and red progress bar."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_bg = work_dir / "news_backdrop.mp4"
    img_path = work_dir / "news_hero.jpg"

    downloaded = False
    if image_url and image_url.startswith("http"):
        try:
            req = urllib.request.Request(image_url, headers={"User-Agent": "AutoShorts-WorldNews/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            if len(raw) > 2048:
                img_path.write_bytes(raw)
                downloaded = True
        except Exception:
            downloaded = False

    if downloaded:
        src_w, src_h = _probe_image_dimensions(img_path)
        fg_h = max(320, min(900, (int(720 * src_h / src_w) // 2) * 2))
        pan_h = max(fg_h + 2, ((int(920 * src_h / src_w)) // 2) * 2)
        bg_blur_jpg = work_dir / "bg_blur.jpg"
        fg_pan_jpg = work_dir / "fg_pan.jpg"
        # Pre-blur background and pre-scale foreground ONCE (25x faster than per-frame boxblur on ARM64)
        p_bg = subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(img_path),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=22:3,eq=brightness=-0.20:saturation=0.95",
            "-frames:v", "1", str(bg_blur_jpg),
        ], check=False)
        p_fg = subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(img_path),
            "-vf", f"scale=920:{pan_h}", "-frames:v", "1", str(fg_pan_jpg),
        ], check=False)
        if p_bg.returncode == 0 and p_fg.returncode == 0 and bg_blur_jpg.is_file() and fg_pan_jpg.is_file():
            vf = (
                f"[1:v]crop=w=720:h={fg_h}:x='(iw-720)*0.5*(1+sin(t*0.30))':y='(ih-{fg_h})/2'[fg_z];"
                f"[0:v][fg_z]overlay=(W-w)/2:(H-h)/2[canvas];"
                f"[canvas][2:v]overlay=x='-W+W*(t/{duration_sec:.2f})':y=H-6:shortest=1,format=yuv420p[vout];"
                f"[3:a]lowpass=f=340,volume=0.14[amb_a]"
            )
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-loop", "1", "-r", "24", "-t", f"{duration_sec:.1f}", "-i", str(bg_blur_jpg),
                "-loop", "1", "-r", "24", "-t", f"{duration_sec:.1f}", "-i", str(fg_pan_jpg),
                "-f", "lavfi", "-t", f"{duration_sec:.1f}", "-i", f"color=c=0xCC0000:s=720x6:r=24:d={duration_sec:.1f}",
                "-f", "lavfi", "-t", f"{duration_sec:.1f}", "-i", "aevalsrc=0.35*sin(2*PI*110*t)+0.25*sin(2*PI*164.81*t)+0.20*sin(2*PI*220*t):s=44100",
                "-filter_complex", vf,
                "-map", "[vout]", "-map", "[amb_a]",
                "-t", f"{duration_sec:.1f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                "-c:a", "aac", "-b:a", "96k", "-ar", "44100",
                str(out_bg),
            ]
            if subprocess.run(cmd, check=False).returncode == 0 and out_bg.is_file():
                return out_bg

    # Fallback clean dark broadcast slate (no unrelated anime background)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=0x0F172A:s=720x1280:r=24:d={duration_sec:.1f}",
        "-vf", "drawbox=x=0:y=0:w=720:h=14:color=0xCC0000:t=fill,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast",
        str(out_bg),
    ]
    subprocess.run(cmd, check=True)
    return out_bg


def _wrap_news_headline(text: str, line_chars: int = 34, max_lines: int = 2) -> str:
    words = " ".join((text or "").split()).split()
    lines: List[str] = []
    cur: List[str] = []
    for w in words:
        cand = " ".join([*cur, w])
        if len(cand) > line_chars and cur:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                break
        else:
            cur.append(w)
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    return "\n".join(lines)


def _escape_dt(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "").replace("%", "\\%")


def _build_news_over_gameplay_video(
    gameplay_path: Path,
    bg_start: float,
    image_url: str,
    pt_title: str,
    source_name: str,
    work_dir: Path,
    duration_sec: float = 55.0,
) -> Optional[Path]:
    """Composite live parkour/subway gameplay with top News Portal card & progress bar."""
    from .renderer import find_default_font
    from .subtitles import escape_ffmpeg_filter_path

    work_dir.mkdir(parents=True, exist_ok=True)
    out_bg = work_dir / "news_gameplay_bg.mp4"
    img_path = work_dir / "news_card_thumb.jpg"
    has_thumb = False
    if image_url and image_url.startswith("http"):
        try:
            req = urllib.request.Request(image_url, headers={"User-Agent": "AutoShorts-WorldNews/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            if len(raw) > 2048:
                img_path.write_bytes(raw)
                has_thumb = True
        except Exception:
            has_thumb = False

    font_path = find_default_font()
    safe_font = escape_ffmpeg_filter_path(font_path) if font_path else ""
    src_badge = _escape_dt(f"MUNDO HOJE • {source_name}".upper()[:32])
    headline = _escape_dt(_wrap_news_headline(pt_title, line_chars=30 if has_thumb else 40, max_lines=2))
    text_x = 224 if has_thumb else 44

    card_filters = [
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,eq=brightness=-0.05:contrast=1.08",
        "drawbox=x=24:y=56:w=672:h=136:color=0x0B0F19@0.86:t=fill",
        "drawbox=x=24:y=56:w=672:h=4:color=0xCC0000:t=fill",
    ]
    if safe_font:
        card_filters.append(
            f"drawtext=fontfile='{safe_font}':text='{src_badge}':"
            f"fontsize=17:fontcolor=white:box=1:boxcolor=0xCC0000@0.95:boxborderw=6:x={text_x}:y=72"
        )
        card_filters.append(
            f"drawtext=fontfile='{safe_font}':text='{headline}':"
            f"fontsize=21:fontcolor=white:borderw=2:bordercolor=black:line_spacing=6:x={text_x}:y=108"
        )

    base_chain = ",".join(card_filters)
    cmd: List[str] = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", "-1", "-ss", f"{bg_start:.2f}", "-t", f"{duration_sec:.1f}", "-i", str(gameplay_path),
        "-f", "lavfi", "-t", f"{duration_sec:.1f}", "-i", f"color=c=0xCC0000:s=720x5:r=30:d={duration_sec:.1f}",
        "-f", "lavfi", "-t", f"{duration_sec:.1f}", "-i", "aevalsrc=0.35*sin(2*PI*110*t)+0.25*sin(2*PI*164.81*t)+0.20*sin(2*PI*220*t):s=44100",
    ]
    if has_thumb:
        cmd.extend(["-loop", "1", "-r", "30", "-t", f"{duration_sec:.1f}", "-i", str(img_path)])
        vf = (
            f"[0:v]{base_chain}[card_bg];"
            f"[3:v]scale=172:108:force_original_aspect_ratio=increase,crop=172:108[mini];"
            f"[card_bg][mini]overlay=x=38:y=70[with_thumb];"
            f"[with_thumb][1:v]overlay=x='-W+W*(t/{duration_sec:.2f})':y=H-5:shortest=1,format=yuv420p[vout];"
            f"[2:a]lowpass=f=340,volume=0.14[amb_a]"
        )
    else:
        vf = (
            f"[0:v]{base_chain}[card_bg];"
            f"[card_bg][1:v]overlay=x='-W+W*(t/{duration_sec:.2f})':y=H-5:shortest=1,format=yuv420p[vout];"
            f"[2:a]lowpass=f=340,volume=0.14[amb_a]"
        )

    cmd.extend([
        "-filter_complex", vf,
        "-map", "[vout]", "-map", "[amb_a]",
        "-t", f"{duration_sec:.1f}", "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "96k", "-ar", "44100",
        str(out_bg),
    ])
    if subprocess.run(cmd, check=False).returncode == 0 and out_bg.is_file():
        return out_bg
    return None


def produce_world_news_short(
    out_dir: str | Path = "output",
    topic: str = "world",
    bg_video: str = "auto",
    style: str = "podcast_female",
    auto_publish: bool = False,
    playlist_name: Optional[str] = "Noticias Mundiais no Brasil - Shorts",
    use_llm: bool = True,
) -> Dict:
    """Fetch an unseen international news story, adapt to PT-BR, narrate, validate & optionally publish."""
    from .narrator import build_narrated_short

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    seen_path = out_root / ".world_news_seen.json"
    seen_ids: List[str] = []
    if seen_path.is_file():
        try:
            seen_ids = list(json.loads(seen_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            seen_ids = []

    headlines = fetch_world_news_headlines(topic=topic, limit=12)
    if not headlines:
        raise RuntimeError("Nenhuma noticia mundial retornada pelas Public APIs neste momento.")

    picked = next((h for h in headlines if h["id"] not in seen_ids), headlines[0])
    pack = build_brazil_news_story_pack(picked, use_llm=use_llm)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_mp4 = out_root / f"mundo_br_{ts}.mp4"
    resolved_bg = bg_video
    burned_card = False
    is_auto = str(bg_video or "auto").strip().lower() in {"auto", "gameplay"}
    bg_style_used = ""
    if is_auto:
        from .gameplay import pick_evolving_background

        bg_dir = out_root / f"_news_bg_{ts}"
        gp = pick_evolving_background(
            out_root,
            niche="noticias_mundiais",
            topic=pack.get("pt_title") or topic,
            min_duration=52.0,
            auto_download=True,
        )
        comp = None
        if gp is not None:
            bg_style_used = gp[2]
            comp = _build_news_over_gameplay_video(
                gp[0], gp[1],
                str(picked.get("image_url") or ""),
                pack["pt_title"],
                pack["source_name"],
                bg_dir,
            )
        if comp is not None:
            resolved_bg = str(comp)
            burned_card = True
        else:
            resolved_bg = str(_build_news_backdrop_video(str(picked.get("image_url") or ""), bg_dir))

    res = build_narrated_short(
        bg_video=resolved_bg,
        script_text=pack["script"],
        out_mp4=out_mp4,
        hook_title=pack["hook_title"],
        style_key=style,
        layout="center_crop" if burned_card else ("blur_bg" if is_auto else "center_crop"),
        humanize=True,
        niche="noticias_mundiais",
        burn_hook=not burned_card,
    )
    if is_auto:
        shutil.rmtree(out_root / f"_news_bg_{ts}", ignore_errors=True)

    res["title"] = pack["title"]
    res["hook_title"] = pack["hook_title"]
    # Enrich generated publish JSON with exact journalism citation & world-news hashtags
    publish_json = out_mp4.with_suffix(".publish.json")
    if publish_json.is_file():
        try:
            saved = json.loads(publish_json.read_text(encoding="utf-8"))
            saved["niche"] = "noticias_mundiais"
            saved["title"] = pack["title"]
            saved["hook_title"] = pack["hook_title"]
            saved["caption"] = pack["caption"]
            saved["hashtags"] = pack["hashtags"]
            saved["source_news"] = {"source": pack["source_name"], "url": pack["source_url"]}
            publish_json.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    from .validator import audit_short_end_to_end
    saved_pack = {}
    if publish_json.is_file():
        try:
            saved_pack = json.loads(publish_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved_pack = {}

    audit = audit_short_end_to_end(out_mp4, pack=saved_pack or pack, vision_check=True)
    res["visual_audit"] = audit
    approved = bool(audit.get("approved"))
    if publish_json.is_file():
        try:
            saved_pack["visual_audit"] = audit
            if bg_style_used:
                saved_pack["background_style"] = bg_style_used
            saved_pack["queued_for_auto_publish"] = approved
            saved_pack["delivery_status"] = "approved_queued" if approved else "rejected_auto_audit"
            publish_json.write_text(json.dumps(saved_pack, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    delivery_status = "approved_queued" if approved else f"rejected_auto_audit: {'; '.join(audit.get('reject_reasons') or [])[:160]}"
    if auto_publish and approved:
        from .publisher import publish_pack_to_youtube
        try:
            res["youtube"] = publish_pack_to_youtube(out_mp4, playlist_name=playlist_name)
            delivery_status = f"published_youtube_api:{res['youtube'].get('video_id')}"
        except Exception as exc:
            msg = str(exc)
            delivery_status = f"queued_quota_limit: {msg[:180]}" if "uploadLimitExceeded" in msg else f"delivery_error: {msg[:180]}"
            res["publish_error"] = msg

    res["delivery_status"] = delivery_status

    if picked["id"] not in seen_ids:
        seen_ids.append(picked["id"])
        seen_path.write_text(json.dumps(seen_ids[-100:], indent=2), encoding="utf-8")

    return {**res, "news": pack, "picked_headline": picked}
