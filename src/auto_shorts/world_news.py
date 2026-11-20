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
from typing import Callable, Dict, List, Optional, Set, Tuple

from .highlights import call_gemini_or_openai
from .mahoraga import MahoragaEngine, clean_word_boundary_hook, immunize_spoken_script
from .team import humanize_ptbr_script, is_llm_configured

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    txt = html.unescape(_HTML_TAG_RE.sub(" ", raw or ""))
    return " ".join(txt.split()).strip()


_SPAM_JUNK_PATTERNS = (
    "não perca nada", "nao perca nada", "adicione o portal", "adicione às fontes",
    "adicione as fontes", "fontes no google", "fonte preferida", "clique aqui e favorite",
    "clique aqui", "página inicial do", "pagina inicial do", "seguir no google",
    "seguir +", "seguir o perfil", "receba as nossas matérias", "receba as nossas materias",
    "no discover", "feed do app google", "google notícias", "google noticias", "google news",
    "siga nos três", "siga nos tres", "siga no perfil", "não perca nenhuma matéria",
    "nao perca nenhuma materia", "compartilhe", "inscreva-se", "leia também", "leia mais",
    "veja também", "veja mais", "redes sociais", "termos de uso", "política de privacidade",
    "todos os direitos reservados", "principais notícias na pesquisa", "principais noticias na pesquisa",
    "adicionar como fonte preferida", "portal viciados", "viciados em gta",
    "veja as notícias", "veja as noticias", "primeiro no seu discover", "toque aqui e siga",
    "toque aqui", "vídeo do nosso parceiro", "video do nosso parceiro", "nosso parceiro",
    "whatsapp", "telegram", "canal no youtube", "quer ser avisado", "grupo vip", "avisos",
    "notícias no seu celular", "noticias no seu celular", "siga o canal", "inscreva-se no canal",
    "ative nossas notificações", "ative nossas notificacoes", "notificações em tempo real",
    "notificacoes em tempo real", "seções notícias", "secoes noticias", "brasil internacional economia",
    "receber notificações", "receber notificacoes", "imagem. gerada por ia",
)


def sanitize_news_lead_text(raw_text: str) -> str:
    """Strip promotional blog junk, inline nav menus, photo/AI credits, duplicate phrases, and fragments."""
    if not raw_text:
        return ""
    txt = _clean_text(raw_text)
    # Strip raw attention emojis, arrows and variation selectors: ➡️, ▶️, 🔥, ⚡, 🚨, 👉, 👇, 💥, etc.
    txt = re.sub(r"[\u2700-\u27BF\U0001F300-\U0001F9FF\u2190-\u21FF\u2600-\u26FF\uFE00-\uFE0F]", " ", txt)
    # Strip parenthetical photo / AI / agency credits BEFORE sentence splitting
    # (prevents "(imagem. Divulgação/LG)" or "(Imagem. Gerada por IA...)" from splitting mid-credit)
    txt = re.sub(
        r"\([^)]*(?:imagem|foto|cr[eé]dito|reprodu[cç][aã]o|divulga[cç][aã]o|gerada por ia|ag[eê]ncia brasil|reuters|ap photo|afp|getty)[^)]*\)",
        " ",
        txt,
        flags=re.I,
    )
    # Strip inline portal navigation menus (BBC/G1/UOL) concatenated without punctuation
    txt = re.sub(
        r"\b(?:Se[cç][õo]es\s+)?(?:Not[ií]cias\s+)?(?:Brasil|Internacional|Economia|Sa[uú]de|Ci[eê]ncia|Tecnologia|Pol[ií]tica|Esportes|Cultura|Mundo)(?:\s+(?:Brasil|Internacional|Economia|Sa[uú]de|Ci[eê]ncia|Tecnologia|Pol[ií]tica|Esportes|Cultura|Mundo)){2,}",
        " ",
        txt,
        flags=re.I,
    )
    # Strip inline notification banners & photo/credit prefixes concatenated before real text
    txt = re.sub(
        r"(?:\bMenu\s+)?Ative nossas notifica[cç][õo]es\s+Você quer ficar por dentro das not[ií]cias mais importantes e receber notifica[cç][õo]es em tempo real\??",
        " ",
        txt,
        flags=re.I,
    )
    txt = re.sub(
        r"\bCr[eé]dito[,:]\s*[A-ZÀ-ÿ][A-Za-zÀ-ÿ0-9/.\-]{1,30}(?:\s+[A-ZÀ-ÿ][A-Za-zÀ-ÿ0-9/.\-]{1,20}){0,2}(?=\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])",
        " ",
        txt,
    )
    txt = re.sub(
        r"(?:—\s*)?(?:Foto|Imagem)[.:]\s*[^.\n]{2,70}?(?:Arquivo|Divulga[cç][aã]o|Ag[eê]ncia Brasil|Reuters|AFP|AP)\b",
        " ",
        txt,
        flags=re.I,
    )
    # Split promo colons into sentence boundaries ("...vídeo do parceiro SanInPlay : A Rockstar confirmou...")
    txt = re.sub(r":\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])", ". ", txt)
    # Clean irregular spacing around punctuation (e.g., "Nvidia , empresários" -> "Nvidia, empresários")
    txt = re.sub(r"\s+([,.:;!?])", r"\1", txt)
    # Strip author bylines and portal timestamps
    txt = re.sub(r"\bJornalista e comentarista d[aoe]\s+[A-Za-zÀ-ÿ0-9\s]+\.?", " ", txt, flags=re.I)
    txt = re.sub(r"\b\d{2}/\d{2}/\d{4}\s+\d{1,2}h\d{2}(?:\s+Atualizado\s+\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}h\d{2})?)?", " ", txt, flags=re.I)
    # Strip trailing bare publisher tags left by Google News RSS ("...se declara culpado G1", "...vai funcionar UOL")
    txt = re.sub(r"\s+(?:G1|UOL|R7|Folha|Estadão|Terra|CNN Brasil|BBC News Brasil|BBC)\s*$", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    # Collapse adjacent repeated phrases even when no period separates them
    txt = re.sub(r"\b(.{18,120}?)\s+\1\b", r"\1", txt, flags=re.I)
    # Split into discrete sentences and deduplicate
    sentences = re.split(r"(?<=[.!?])\s+", txt)
    clean: List[str] = []
    seen_sent: Set[str] = set()
    for s in sentences:
        s_str = s.strip()
        if len(s_str) < 16:
            continue
        s_low = s_str.lower()
        if s_str.count(" - ") >= 2:
            continue
        if any(pat in s_low for pat in _SPAM_JUNK_PATTERNS):
            continue
        if s_low.startswith(("página inicial", "pagina inicial", "seguir +", "clique aqui", "toque aqui")):
            continue
        if re.search(r":\s*$", s_str):
            continue
        norm_key = re.sub(r"\W+", "", s_low)
        if norm_key in seen_sent:
            continue
        seen_sent.add(norm_key)
        clean.append(s_str)
    res = " ".join(clean).strip()
    return re.sub(r"\s+", " ", res).strip()


def clean_truncate_to_sentence(text: str, max_chars: int = 750) -> str:
    """Truncate article lead strictly at a full stop/sentence boundary before max_chars, never mid-sentence."""
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= max_chars:
        return clean
    clipped = clean[:max_chars]
    # Find last sentence end (. or ! or ?)
    m = re.search(r"^(.*[.!?])(?:\s+.*)?$", clipped)
    if m and len(m.group(1).strip()) >= 40:
        return m.group(1).strip()
    # Fallback to word boundary
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return re.sub(r"[,.:;!?—–-]+$", "", clipped).strip() + "."


_SHOPPING_PROMO_TERMS = (
    "cupom", "desconto", "em oferta", "oferta antecipada", "para comprar",
    "modelos para comprar", "guia de compra", "guia de compras", "black friday",
    "black november", "menor preço em oferta", "menor preco", "menor preço",
    "melhor tv de", "melhores smart tvs", "em até 12x", "em ate 12x", "sem juros",
    "aliexpress", "magalu", "mercado livre", "por menos de r$", "economize ",
    "baixa 2", "baixa 3", "baixa 4", "baixa 5",
)


def _is_commercial_roundup(story: Dict) -> bool:
    """Keep product roundups and affiliate promotions out of the breaking-news feed."""
    text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
    return any(term in text for term in _SHOPPING_PROMO_TERMS)


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

    # 1. Multi-Portal Brazilian & Global RSS Desks (Diversified & Load-Balanced)
    base_sources = [
        ("https://news.google.com/rss/search?q=Microsoft+OR+CrowdStrike+OR+AWS+OR+Cloudflare+OR+apagao+OR+pane+when:2d&hl=pt-BR&gl=BR&ceid=BR:pt-419", "Plantão Tech Global", "tech_ia"),
        ("https://tecnoblog.net/feed/", "Tecnoblog", "tech_ia"),
        ("https://feeds.bbci.co.uk/portuguese/rss.xml", "BBC News Brasil", "mundo"),
        ("https://pt.euronews.com/rss?level=theme&name=news", "Euronews Mundo", "mundo"),
        ("https://olhardigital.com.br/feed/", "Olhar Digital", "tech_ia"),
        ("https://canaltech.com.br/rss/", "Canaltech", "tech_ia"),
        ("https://www.cnnbrasil.com.br/feed/", "CNN Brasil", "mundo"),
        ("https://www.metropoles.com/feed", "Metrópoles", "mundo"),
        ("https://www.infomoney.com.br/feed/", "InfoMoney", "economia"),
        ("https://g1.globo.com/rss/g1/tecnologia/", "G1 Tecnologia", "tech_ia"),
        ("https://g1.globo.com/rss/g1/economia/", "G1 Economia", "economia"),
        ("https://g1.globo.com/rss/g1/mundo/", "G1 Mundo", "mundo"),
        ("https://www.bleepingcomputer.com/feed/", "BleepingComputer", "tech_ia"),
        ("https://viciados.net/feed/", "Viciados.net - GTA 6 & Rockstar", "games"),
        ("https://news.google.com/rss/search?q=GTA+6+OR+Rockstar+Games+OR+PlayStation+when:3d&hl=pt-BR&gl=BR&ceid=BR:pt-419", "Plantão Games & GTA 6", "games"),
        ("https://ign.com/br/feed.xml", "IGN Brasil", "games"),
    ]
    if fetcher is None:
        import random
        # In live production, randomize order so BBC or G1 don't monopolize the headlines
        active_sources = list(base_sources)
        random.shuffle(active_sources)
    else:
        active_sources = base_sources

    for rss_url, src_label, cat_name in active_sources:
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
    topic_aliases = {
        "tech": ("tech", "ia", "tecnologia", "software", "chip", "ai", "cyber", "dados", "digital", "robo", "ciencia"),
        "ia": ("ia", "ai", "inteligencia", "llm", "gpt", "modelo", "chip", "nvidia", "openai", "tech_ia"),
        "financas": ("economia", "mercado", "juros", "banco", "dolar", "inflacao", "invest", "bolsa", "pib"),
        "games": ("game", "games", "gta", "gta 6", "rockstar", "jogo", "jogos", "playstation", "xbox", "gamer", "gameplay"),
    }
    match_terms = topic_aliases.get(q, (q,)) if q else ()
    for row in collected:
        if _is_commercial_roundup(row):
            continue
        key = row["title"].lower()
        if key in seen:
            continue
        haystack = f"{key} {row.get('summary', '').lower()} {row.get('category', '').lower()}"
        if q and q not in {"world", "mundo", "all", ""} and not any(t in haystack for t in match_terms):
            continue
        seen.add(key)
        unique.append(row)

    # Rank stories with real journalistic summaries (summary != title) and images first
    unique.sort(
        key=lambda r: (
            1 if (len(str(r.get("summary") or "")) >= 55 and str(r.get("summary") or "").lower() != str(r.get("title") or "").lower()) else 0,
            1 if str(r.get("image_url") or "").startswith("http") else 0,
        ),
        reverse=True,
    )
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


def _is_valid_hook_banner(hook: str) -> bool:
    """Check if hook title is valid and free of prompt template leaks or instruction placeholders."""
    if not hook or len(hook.strip()) < 4:
        return False
    h_low = hook.lower().strip()
    leak_keywords = (
        "max", "words", "palavras", "uppercase", "maiusculas", "maíusculas",
        "without", "clause", "frase", "chars", "caracteres", "string", "json",
        "destaque", "hook", "prompt", "texto", "exemplo", "placeholder",
    )
    if any(kw in h_low for kw in leak_keywords):
        return False
    if h_low in {"urgente no mundo", "destaque em video"}:
        return False
    return True


def _build_complete_news_hook(pt_title: str, max_chars: int = 32, category: str = "mundo") -> str:
    """Build a punchy uppercase hook without stopping mid-clause on a preposition, article, or transitive verb."""
    t_lower = (pt_title or "").lower()

    # Specialized gaming hooks for GTA 6 & Rockstar
    if any(k in t_lower for k in ("gta 6", "gta vi", "gta", "grand theft auto")):
        if any(k in t_lower for k in ("zerar", "duracao", "duração", "tempo", "horas", "platina", "capitulo", "capítulo")):
            return "DURAÇÃO DO GTA 6!"
        if any(k in t_lower for k in ("data", "quando", "estreia", "lancamento", "lançamento", "horario", "horário")):
            return "DATA DO GTA 6!"
        if any(k in t_lower for k in ("mapa", "tamanho", "vice city", "leonida", "cenario", "cenário")):
            return "MAPA DO GTA 6!"
        if any(k in t_lower for k in ("preco", "preço", "valor", "edicao", "edição", "comprar")):
            return "PREÇO DO GTA 6!"
        if any(k in t_lower for k in ("trailer", "gameplay", "vazamento", "personagens", "lucia", "jason")):
            return "NOVO GTA 6 REVELADO!"
        return "BOMBA NO GTA 6!"

    if any(k in t_lower for k in ("apagao", "apagão", "fora do ar", "pane", "interrupcao", "interrupção", "queda")):
        if "microsoft" in t_lower:
            return "APAGÃO NA MICROSOFT!"
        if "aws" in t_lower or "amazon" in t_lower:
            return "ALERTA NA AMAZON!"
        if "google" in t_lower:
            return "PANE NO GOOGLE!"
        return "APAGÃO GLOBAL NO AR!"

    fallback_label = "DESTAQUE DE GAMES" if category == "games" else "URGENTE NO MUNDO"
    return clean_word_boundary_hook(pt_title, max_chars=max_chars, fallback=fallback_label)


def _clean_seo_title(title: str, max_chars: int = 76, suffix: str = " | Mundo Hoje") -> str:
    """Format SEO title cleanly, trimming without leaving hanging prepositions, conjunctions, or punctuation."""
    clean = re.sub(r"\s+", " ", title or "").strip()

    # Safely strip trailing portal/brand suffix ONLY if at the very end of the string
    # (e.g., " - G1", " - Tecnoblog", " | Viciados.net", " – BBC News Brasil")
    # Never strip internal hyphens or separators inside actual headlines!
    m_brand = re.search(r"\s+[-–|]\s+(?:G1.*|Tecnoblog|Viciados.*|IGN.*|BBC.*|CNN.*|Metrópoles|Canaltech|InfoMoney|Olhar Digital|Euronews.*|[A-Za-z0-9\s]{2,20})$", clean, re.I)
    if m_brand:
        cand = clean[:m_brand.start()].strip()
        if len(cand) >= 20:
            clean = cand

    target_len = max(20, max_chars - len(suffix))
    if len(clean) <= target_len:
        clean = re.sub(r"[,.:;!?—–-]+$", "", clean).strip()
        return f"{clean}{suffix}".strip()

    # Viral Headline Heuristic: If there is a complete question or statement ('?' or '!')
    # within target_len that has at least 25 chars, prioritize keeping that clean complete hook!
    m_punct = re.search(r"^(.*?[\?!])\s+", clean)
    if m_punct and 25 <= len(m_punct.group(1)) <= target_len:
        return f"{m_punct.group(1).strip()}{suffix}".strip()

    clipped = clean[:target_len]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    dangling_words = {
        "e", "ou", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
        "ao", "aos", "pelo", "pela", "pelos", "pelas", "num", "numa", "nuns", "numas",
        "com", "para", "por", "que", "se", "a", "o", "as", "os", "um", "uma", "uns", "umas",
        "sem", "sob", "sobre", "modo", "como", "da?", "de?", "do?", "e?",
        "pede", "diz", "afirma", "revela", "mostra", "faz", "vai", "pode", "quer", "tem",
        "astro", "após", "entre", "contra", "até", "desde", "durante", "enquanto",
        "segundo", "mediante", "perante", "além", "através",
    }
    words = clipped.split()
    while words and (words[-1].lower().strip(",.:;!?—–-") in dangling_words or re.search(r"[,.:;!?—–-]$", words[-1])):
        stripped_w = re.sub(r"[,.:;!?—–-]+$", "", words[-1])
        if stripped_w.lower() in dangling_words:
            words.pop()
        else:
            words[-1] = stripped_w
            break
    clean = " ".join(words)

    clean = re.sub(r"[,.:;!?—–-]+$", "", clean).strip()
    return f"{clean}{suffix}".strip()


_IGNORE_PARA_KEYWORDS = (
    "confira também", "leia também", "veja também", "siga no google", "fonte:",
    "tudo sobre gta", "faça parte da discussão", "login para publicar",
    "compartilhe no whatsapp", "inscreva-se no canal", "deixe seu comentário",
    "política de privacidade", "todos os direitos reservados", "você precisa fazer o login",
    "follow the viciados portal", "ao acompanhar nosso portal", "é grátis e leva um toque",
)


def _clean_alnum(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", "", s.lower())


def _extract_article_lead_from_url(url: str, timeout: float = 4.5) -> Tuple[str, str]:
    """Fetch article meta description / first paragraphs and og:image when RSS/HN only provided a bare title."""
    if not url or not url.startswith(("http://", "https://")) or "news.ycombinator.com" in url:
        return "", ""
    try:
        html_raw = ""
        try:
            html_raw = _http_get_text(url, timeout=timeout)
        except Exception:
            html_raw = ""

        # If direct HTTP failed (e.g. 403 / Cloudflare) or returned thin JS shell, fallback to BrowserSkill (`bsk`)
        if not html_raw or len(re.findall(r"<p[^>]*>", html_raw, re.I)) < 2:
            try:
                from .bsk_bridge import bsk_fetch_rendered_html
                bsk_html = bsk_fetch_rendered_html(url)
                if bsk_html and len(bsk_html) > len(html_raw):
                    html_raw = bsk_html
            except Exception:
                pass
        if not html_raw:
            return "", ""
        img = ""
        m_img = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']', html_raw, re.I)
        if m_img and m_img.group(1).startswith("http"):
            img = m_img.group(1).strip()
        desc = ""
        m_desc = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)["\']', html_raw, re.I)
        if m_desc:
            desc = sanitize_news_lead_text(m_desc.group(1))
        paragraphs: List[str] = []
        for pm in re.finditer(r"<p[^>]*>(.*?)</p>", html_raw, re.I | re.S):
            p_txt = sanitize_news_lead_text(pm.group(1))
            if len(p_txt) < 38 or len(p_txt) > 600:
                continue
            p_lower = p_txt.lower()
            if any(ign in p_lower for ign in _IGNORE_PARA_KEYWORDS):
                continue
            paragraphs.append(p_txt)
            if len(paragraphs) >= 8:
                break

        combined_parts = []
        desc_alnum = _clean_alnum(desc[:40])
        is_dup_desc = any(desc_alnum and desc_alnum in _clean_alnum(p) for p in paragraphs)
        if desc and len(desc) >= 45 and not is_dup_desc:
            combined_parts.append(desc)
        combined_parts.extend(paragraphs)
        combined = sanitize_news_lead_text(" ".join(combined_parts))
        lead = clean_truncate_to_sentence(combined, max_chars=1350)
        return lead, img
    except Exception:
        return "", ""


def build_brazil_news_story_pack(
    story: Dict,
    use_llm: bool = True,
    translator: Optional[Callable[[str], str]] = None,
    target_platform: str = "tiktok_rewards",
) -> Dict:
    """Convert an international headline into an engaging, non-repetitive PT-BR breaking-news Short script."""
    import hashlib
    import os

    tx = translator or translate_en_to_ptbr
    if _is_commercial_roundup(story):
        raise ValueError(f"Notícia descartada por ser oferta/cupom comercial: '{story.get('title', '')}'.")
    source_name = str(story.get("source") or "Imprensa Internacional").strip()
    orig_title = str(story.get("title") or "").strip()
    orig_summary = str(story.get("summary") or "").strip()
    orig_url = str(story.get("url") or "").strip()
    category = str(story.get("category") or "mundo").strip().lower()
    is_already_pt = str(story.get("lang") or "").lower() == "pt"

    # Deep article extraction: if orig_url is available, scrape full article paragraphs
    # to elevate thin 1-sentence RSS feeds (BBC, G1, Tech feeds) with full journalistic context.
    if orig_url and translator is None and "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            fetched_lead, fetched_img = _extract_article_lead_from_url(orig_url)
            if fetched_lead and (not orig_summary or orig_summary.lower() == orig_title.lower() or len(fetched_lead) > len(orig_summary) + 30):
                orig_summary = fetched_lead
            if fetched_img and not story.get("image_url"):
                story["image_url"] = fetched_img
        except Exception:
            pass

    pt_title = orig_title if is_already_pt else tx(orig_title)
    if orig_summary and orig_summary.lower() != orig_title.lower():
        pt_summary = orig_summary if is_already_pt else tx(orig_summary)
    else:
        pt_summary = ""

    # Auto-detect category strictly from headline + category + lead snippet (avoiding article footer false positives)
    title_low = orig_title.lower()
    content_blob = f"{orig_title} {orig_summary[:180]} {category}".lower()
    if category in ("humor", "memes", "humor_memes") or any(re.search(rf"\b{k}\b", content_blob) for k in ("meme", "memes", "engracado", "engraçado", "comedia", "comédia", "piada", "zoeira", "casimiro", "defante", "shitpost")):
        effective_category = "humor_memes"
    elif category in ("games", "jogo", "jogos") or any(re.search(rf"\b{k}\b", content_blob) for k in ("gta", "gta 6", "rockstar", "playstation", "ps5", "xbox", "nintendo", "gamer", "gameplay", "platina")):
        effective_category = "games"
    elif category in ("tech", "ia", "tech_ia") or any(re.search(rf"\b{k}\b", title_low) for k in ("ia", "inteligencia artificial", "inteligência artificial", "openai", "nvidia", "deepseek", "chatgpt", "software", "tecnologia", "google", "microsoft", "apple", "chip", "chips", "robô", "robo")):
        effective_category = "tech_ia"
    elif category in ("economia", "financas") or any(re.search(rf"\b{k}\b", content_blob) for k in ("dolar", "dólar", "inflacao", "inflação", "juros", "selic", "bolsa de valores", "banco central", "pib", "escala 5x2", "stf")):
        effective_category = "economia"
    elif category in ("ciencia", "ciencia_espaco", "espaco") or any(re.search(rf"\b{k}\b", content_blob) for k in ("nasa", "spacex", "foguete", "astronomia", "telescopio", "telescópio", "planeta", "lua", "marte")):
        effective_category = "ciencia_espaco"
    else:
        effective_category = "mundo"

    # Clean comparison: remove source suffixes like " - G1", " - Tecnoblog", or bare " G1" / " UOL"
    clean_t = re.sub(r"\s+(?:[-–|]\s+.*|G1|UOL|R7|Folha|Estadão|Terra|BBC)$", "", pt_title).strip().lower()
    clean_s = re.sub(r"\s+(?:[-–|]\s+.*|G1|UOL|R7|Folha|Estadão|Terra|BBC)$", "", pt_summary).strip().lower()
    if pt_summary:
        pt_summary = sanitize_news_lead_text(pt_summary) or pt_summary

    # Deduplicate if pt_summary repeats pt_title at the start
    clean_pt_title = _clean_alnum(pt_title[:35])
    if pt_summary and clean_pt_title and clean_pt_title in _clean_alnum(pt_summary[:90]):
        m_split = re.search(r"^.*?[.!?]\s+", pt_summary)
        if m_split and len(pt_summary[m_split.end():].strip()) >= 50:
            pt_summary = pt_summary[m_split.end():].strip()
        elif pt_summary.lower().startswith(pt_title.lower()):
            pt_summary = pt_summary[len(pt_title):].lstrip(" .,:;-—")

    # A headline alone (or a 1-sentence Google News RSS stub) is NEVER enough for a news Short.
    if (
        not pt_summary
        or clean_s == clean_t
        or len(pt_summary) < 85
        or len(pt_summary.split()) < 14
        or pt_summary.lower() == pt_title.lower()
    ):
        raise ValueError(
            f"Notícia descartada: {source_name} forneceu apenas manchete/stub insuficiente para '{pt_title}'."
        )

    cat_meta_map = {
        "humor_memes": {
            "niche": "humor_memes",
            "seo_suffix": " | Plantão Humor",
            "hashtags": ["#Shorts", "#MemesBrasil", "#HumorBR", "#Comedia", "#Engracado"],
            "cta": "Manda pro amigo que precisa rir hoje e segue para mais memes!",
        },
        "games": {
            "niche": "games",
            "seo_suffix": " | Plantão Games",
            "hashtags": ["#Shorts", "#GTA6", "#Games", "#GamerBrasil", "#Gameplay"],
            "cta": "Comente sua expectativa sobre o jogo e siga o canal para mais novidades dos games!",
        },
        "tech_ia": {
            "niche": "tech_ia",
            "seo_suffix": " | Plantão Tech",
            "hashtags": ["#Shorts", "#Tecnologia", "#InteligenciaArtificial", "#Inovacao", "#TechBR"],
            "cta": "Comente o que achou dessa inovação e siga o canal para mais novidades de tecnologia e IA!",
        },
        "economia": {
            "niche": "economia",
            "seo_suffix": " | Plantão Economia",
            "hashtags": ["#Shorts", "#Economia", "#Financas", "#Brasil", "#MercadoFinanceiro"],
            "cta": "Comente sua visão sobre o mercado e siga o canal para alertas econômicos diários!",
        },
        "ciencia_espaco": {
            "niche": "ciencia_espaco",
            "seo_suffix": " | Plantão Ciência",
            "hashtags": ["#Ciencia", "#Espaco", "#Astronomia", "#NASA", "#Curiosidades", "#Shorts"],
            "cta": "Curtiu essa descoberta? Deixe seu like e siga o canal para mais explorações científicas!",
        },
        "mundo": {
            "niche": "noticias_mundiais",
            "seo_suffix": " | Mundo Hoje",
            "hashtags": ["#NoticiasMundiais", "#Mundo", "#Brasil", "#Atualidades", "#Shorts"],
            "cta": "Comente sua opinião e siga o canal para ficar atualizado sobre os principais fatos do mundo!",
        },
    }
    cat_meta = cat_meta_map.get(effective_category, cat_meta_map["mundo"])

    hook_banner = _build_complete_news_hook(pt_title, category=effective_category)
    seo_title = _clean_seo_title(pt_title, max_chars=76, suffix=cat_meta["seo_suffix"])

    # Mahoraga 8-Spoke Adaptive Narrative Engine: rotates across 8 distinct journalistic cadences in SQLite
    # so consecutive videos NEVER share the same speech formula or repeat title==summary.
    mahoraga = MahoragaEngine()
    raw_script, spoke = mahoraga.compose_news_narrative(
        pt_title=pt_title,
        pt_summary=pt_summary,
        source_name=source_name,
        category=effective_category,
    )
    script = humanize_ptbr_script(immunize_spoken_script(raw_script, title=pt_title, summary=pt_summary))

    is_tiktok_rewards = str(target_platform or "").strip().lower() == "tiktok_rewards"
    if use_llm and is_llm_configured():
        dur_hint = "62-72s (OBRIGATÓRIO >= 61s para TikTok Creator Rewards)" if is_tiktok_rewards else "35-45s"
        word_hint = "150 a 185 palavras" if is_tiktok_rewards else "70 a 100 palavras"
        min_words, max_words = (115, 210) if is_tiktok_rewards else (35, 105)
        prompt = (
            f"Você é um jornalista de plantão internacional adaptando notícias reais para Shorts dinâmicos no Brasil ({dur_hint}).\n"
            f"Fonte: {source_name}\nManchete: {pt_title}\nResumo completo dos fatos: {pt_summary}\n\n"
            "ESTRUTURA OBRIGATÓRIA DO ROTEIRO (4 ATOS):\n"
            "1. GANCHO (0-3s): Chame a atenção imediatamente com o fato principal ou contraste.\n"
            "2. O FATO: Explique objetivamente o que aconteceu com dados concretos da matéria.\n"
            "3. O MOTIVO / CONTEXTO: Explique O PORQUÊ do fato, repercussões e o que especialistas/autoridades declararam (NUNCA pare em suspense!).\n"
            "4. CONCLUSÃO & CTA POLARIZADOR: Dê o desfecho claro e faça uma pergunta específica que gere debate nos comentários.\n\n"
            "Regras: Português brasileiro natural e direto; use os fatos fornecidos sem alucinações; NUNCA corte frase no meio.\n"
            "Responda SOMENTE JSON válido:\n"
            f'{{"seo_title":"max 80 chars","hook_banner":"MAX 4 PALAVRAS MAIUSCULAS","roteiro":"texto falado {word_hint} completo com explicacao e conclusao"}}'
        )
        try:
            raw = call_gemini_or_openai(prompt)
            m_start, m_end = raw.find("{"), raw.rfind("}")
            if m_start != -1 and m_end > m_start:
                data = json.loads(raw[m_start:m_end + 1])
                if isinstance(data, dict) and data.get("roteiro") and min_words <= len(str(data["roteiro"]).split()) <= max_words:
                    script = humanize_ptbr_script(str(data["roteiro"]))
                if data.get("seo_title") and str(data["seo_title"]).strip().lower() not in {"string", "max 80 chars"}:
                    seo_title = _clean_seo_title(str(data["seo_title"]).strip(), max_chars=80, suffix=cat_meta["seo_suffix"])
                if data.get("hook_banner") and _is_valid_hook_banner(str(data["hook_banner"])):
                    hook_banner = clean_word_boundary_hook(str(data["hook_banner"]), max_chars=32)
        except Exception:
            pass

    caption = (
        f"{seo_title}\n"
        f"Destaque: {hook_banner}\n\n"
        f"Resumo da noticia internacional:\n{pt_summary}\n\n"
        f"Fonte original ({source_name}): {orig_url}\n"
        f"{cat_meta['cta']}\n\n"
        f"{' '.join(cat_meta['hashtags'])}"
    )
    from .cross_platform_adapter import adapt_short_for_all_platforms

    multi_platform = adapt_short_for_all_platforms(
        title=seo_title,
        body_text=pt_summary,
        niche=cat_meta["niche"],
        hook_banner=hook_banner,
        source_attribution=source_name,
        source_url=orig_url,
    )

    return {
        "title": seo_title,
        "hook_title": hook_banner,
        "script": script,
        "caption": caption,
        "hashtags": cat_meta["hashtags"],
        "niche": cat_meta["niche"],
        "category": effective_category,
        "source_name": source_name,
        "source_url": orig_url,
        "pt_title": pt_title,
        "pt_summary": pt_summary,
        "multi_platform": multi_platform,
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


def _wrap_news_headline(text: str, line_chars: int = 34, max_lines: int = 3) -> str:
    words = " ".join((text or "").split()).split()
    lines: List[str] = []
    cur: List[str] = []
    truncated = False
    for idx, w in enumerate(words):
        cand = " ".join([*cur, w])
        if len(cand) > line_chars and cur:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                truncated = True
                break
        else:
            cur.append(w)
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    elif cur and len(lines) >= max_lines:
        truncated = True
    # Avoid ending a truncated headline on a dangling PT-BR preposition/article
    if truncated and lines:
        dangling = {
            "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
            "a", "o", "as", "os", "e", "ou", "com", "sem", "para", "por",
            "pelo", "pela", "que", "um", "uma", "durante", "após", "entre",
            "contra", "sobre", "até", "desde", "segundo", "enquanto",
        }
        last_words = lines[-1].split()
        while len(last_words) > 1 and last_words[-1].lower().strip(",.:;!?—–-") in dangling:
            last_words.pop()
        lines[-1] = " ".join(last_words).rstrip(",.:;—–-")
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
            is_img = (
                raw.startswith(b"\xff\xd8\xff")
                or raw.startswith(b"\x89PNG\r\n\x1a\n")
                or (raw.startswith(b"RIFF") and b"WEBP" in raw[:16])
                or raw.startswith(b"GIF8")
            )
            if len(raw) > 2048 and is_img:
                raw_path = work_dir / "news_card_raw"
                raw_path.write_bytes(raw)
                conv = subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_path), "-frames:v", "1", str(img_path)],
                    check=False,
                    timeout=15,
                )
                has_thumb = conv.returncode == 0 and img_path.is_file() and img_path.stat().st_size > 512
        except Exception:
            has_thumb = False

    font_path = find_default_font()
    safe_font = escape_ffmpeg_filter_path(font_path) if font_path else ""
    src_badge = _escape_dt(f"MUNDO HOJE • {source_name}".upper()[:32])
    headline = _escape_dt(_wrap_news_headline(pt_title, line_chars=30 if has_thumb else 42, max_lines=3))
    text_x = 224 if has_thumb else 44

    card_filters = [
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,eq=brightness=-0.05:contrast=1.08",
        # Safe zone: symmetric centered card strictly below phone notch, status bar & TikTok/Reels top bar
        "drawbox=x=28:y=138:w=664:h=156:color=0x0B0F19@0.90:t=fill",
        "drawbox=x=28:y=138:w=664:h=4:color=0xCC0000:t=fill",
    ]
    if safe_font:
        card_filters.append(
            f"drawtext=fontfile='{safe_font}':text='{src_badge}':"
            f"fontsize=16:fontcolor=white:box=1:boxcolor=0xCC0000@0.95:boxborderw=6:x={text_x}:y=154"
        )
        card_filters.append(
            f"drawtext=fontfile='{safe_font}':text='{headline}':"
            f"fontsize=19:fontcolor=white:borderw=2:bordercolor=black:line_spacing=5:x={text_x}:y=188"
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
            f"[3:v]scale=172:112:force_original_aspect_ratio=increase,crop=172:112[mini];"
            f"[card_bg][mini]overlay=x=38:y=154[with_thumb];"
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
    try:
        if subprocess.run(cmd, check=False, timeout=180).returncode == 0 and out_bg.is_file():
            return out_bg
    except subprocess.TimeoutExpired:
        return None
    return None


def produce_world_news_short(
    out_dir: str | Path = "output",
    topic: str = "world",
    bg_video: str = "auto",
    style: str = "podcast_female",
    auto_publish: bool = False,
    playlist_name: Optional[str] = "Noticias Mundiais no Brasil - Shorts",
    use_llm: bool = True,
    target_platform: str = "tiktok_rewards",
) -> Dict:
    """Fetch an unseen international news story, adapt to PT-BR, narrate, validate & optionally publish."""
    from .narrator import build_narrated_short

    from .deduplication import ContentRegistry

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    registry = ContentRegistry(out_dir=out_root)

    headlines = fetch_world_news_headlines(topic=topic, limit=16)
    if not headlines:
        raise RuntimeError("Nenhuma noticia mundial retornada pelas Public APIs neste momento.")

    # Strictly filter out any duplicate URL, title, or semantic overlap with past stories
    candidates: List[Dict] = []
    for h in headlines:
        is_dup, _ = registry.is_duplicate(h)
        if not is_dup:
            candidates.append(h)

    # If all items in this batch were produced, fetch a broader batch of 32
    if not candidates:
        broader_headlines = fetch_world_news_headlines(topic=topic, limit=32)
        for h in broader_headlines:
            is_dup, _ = registry.is_duplicate(h)
            if not is_dup:
                candidates.append(h)

    if not candidates:
        raise RuntimeError(
            f"Todas as manchetes capturadas para '{topic}' já foram produzidas no acervo. "
            "Aguardando novas notícias para garantir 100% zero repetição."
        )

    pack = None
    rejected: List[str] = []
    for picked in candidates:
        try:
            pack = build_brazil_news_story_pack(picked, use_llm=use_llm, target_platform=target_platform)
            break
        except ValueError as exc:
            rejected.append(str(exc))
    if pack is None:
        detail = " ".join(rejected[:2])
        raise RuntimeError(f"Nenhuma notícia tinha resumo suficiente para narrar com segurança. {detail}")

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_mp4 = out_root / f"mundo_br_{ts}.mp4"
    resolved_bg = bg_video
    burned_card = False
    is_auto = str(bg_video or "auto").strip().lower() in {"auto", "gameplay"}
    bg_style_used = ""
    if is_auto:
        import os
        from .gameplay import pick_evolving_background
        from .semantic_visual_engine import build_semantic_visual_sequence

        bg_dir = out_root / f"_news_bg_{ts}"
        bg_dir.mkdir(parents=True, exist_ok=True)
        detected_niche = "games_gta6" if (topic == "games" or any(k in (pack.get("pt_title", "") + " " + topic).lower() for k in ("gta", "rockstar", "jogo", "games", "gameplay", "playstation", "xbox"))) else ("ia_tech" if topic in ("tech", "ia") else "noticias_mundiais")

        comp = None
        if os.getenv("AUTOSHORTS_SEMANTIC_VISUALS", "1") in {"1", "true"}:
            semantic_bg = build_semantic_visual_sequence(
                pt_title=pack.get("pt_title", ""),
                summary=str(picked.get("summary") or pack.get("spoken_script", "")),
                category=detected_niche,
                target_duration=48.0,
                work_dir=bg_dir / "_semantic",
                thumb_url=str(picked.get("image_url") or ""),
            )
            if semantic_bg is not None and semantic_bg.is_file():
                bg_style_used = "semantic_topic_broll"
                comp = _build_news_over_gameplay_video(
                    semantic_bg, 0.0,
                    str(picked.get("image_url") or ""),
                    pack["pt_title"],
                    pack["source_name"],
                    bg_dir,
                )

        if comp is None:
            gp = pick_evolving_background(
                out_root,
                niche=detected_niche,
                topic=pack.get("pt_title") or topic,
                min_duration=52.0,
                auto_download=True,
            )
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

    target_niche = pack.get("niche") or ("games" if "games" in str(topic).lower() else "noticias_mundiais")
    res = build_narrated_short(
        bg_video=resolved_bg,
        script_text=pack["script"],
        out_mp4=out_mp4,
        hook_title=pack["hook_title"],
        style_key=style,
        layout="center_crop" if burned_card else ("blur_bg" if is_auto else "center_crop"),
        humanize=True,
        niche=target_niche,
        burn_hook=not burned_card,
    )
    if is_auto:
        shutil.rmtree(out_root / f"_news_bg_{ts}", ignore_errors=True)

    res["title"] = pack["title"]
    res["hook_title"] = pack["hook_title"]
    # Enrich generated publish JSON with exact journalism citation, niche hashtags & 3-platform bundle
    publish_json = out_mp4.with_suffix(".publish.json")
    if publish_json.is_file():
        try:
            saved = json.loads(publish_json.read_text(encoding="utf-8"))
            saved["niche"] = target_niche
            saved["title"] = pack["title"]
            saved["hook_title"] = pack["hook_title"]
            saved["caption"] = pack["caption"]
            saved["hashtags"] = pack["hashtags"]
            saved["source_news"] = {"source": pack["source_name"], "url": pack["source_url"]}
            if pack.get("multi_platform"):
                saved["multi_platform"] = pack["multi_platform"]
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

    # Auto-backup rendered news short to corresponding Google Drive niche subfolder
    try:
        from .downloader import build_drive_niche_folder, upload_to_rclone
        target_niche = str(picked.get("category") or "noticias_mundiais").lower()
        drive_folder = build_drive_niche_folder(target_niche)
        upload_to_rclone(out_mp4, drive_folder)
    except Exception:
        pass

    # Permanently register URL and title in ContentRegistry to guarantee zero repetition
    try:
        registry.record_produced_story(
            url=picked.get("url") or picked.get("id") or "",
            title=pack.get("title") or pack.get("pt_title") or "",
        )
    except Exception:
        pass

    return {**res, "news": pack, "picked_headline": picked}
