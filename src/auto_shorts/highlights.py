"""Highlight detection for Brazilian short-form content (LLM + offline heuristic)."""

import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .config import NICHES, PLATFORMS, NicheProfile, PlatformPreset
from .transcript import format_transcript_for_llm

CHUNK_SIZE_SECONDS = 1200.0
LONG_VIDEO_THRESHOLD = 1800.0
CHUNK_OVERLAP_SECONDS = 60.0

BR_HIGHLIGHT_PROMPT = """Você é um editor especialista em retenção e viralização para {platform_name} no Brasil (nicho: {niche_label}).

Critérios de viralidade (prioridade):
1. HOOK NOS 3 PRIMEIROS SEGUNDOS — afirmação forte, dúvida imediata ou quebra de expectativa.
2. PICOS EMOCIONAIS / OPINIÃO FORTE — declarações polarizadoras ou revelações práticas.
3. HISTÓRIA COMPLETA / VALOR PRÁTICO — começo, meio e clímax sem cortar no meio de uma frase.

Regras obrigatórias:
- Duração alvo de cada corte: entre {min_dur}s e {max_dur}s ({sweet_spot}).
- Retorne no máximo {num_clips} cortes sem sobreposição entre si.
- Crie um "hook_title" curto em PT-BR (máximo 6 palavras em caixa alta) para colocar no topo do vídeo.
- Sugira um "cta_line" curto alinhado ao nicho ({cta_suggestion}).

Responda SOMENTE com JSON válido seguindo exatamente estas chaves (NUNCA copie os nomes das chaves como valor, gere textos reais baseados na transcrição):
{{"highlights":[{{"title":"Titulo curioso em PT-BR com max 65 chars","hook_title":"GANCHO EM 4 PALAVRAS","start_time":12.5,"end_time":54.0,"score":92,"virality_reason":"Motivo real de retencao","cta_line":"Chamada curta para comentarios ou parte 2"}}]}}

Transcrição:
{transcript_text}"""


def _parse_json_loose(raw: str) -> Dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


def chunk_segments(segments: List[Dict], duration: float) -> List[List[Dict]]:
    """Split long transcripts (>30min) into 20-min windows with 60s overlap."""
    if duration <= LONG_VIDEO_THRESHOLD or not segments:
        return [segments]
    chunks: List[List[Dict]] = []
    cursor = 0.0
    step = CHUNK_SIZE_SECONDS - CHUNK_OVERLAP_SECONDS
    while cursor < duration:
        window_end = cursor + CHUNK_SIZE_SECONDS
        window = [s for s in segments if s["end"] >= cursor and s["start"] <= window_end]
        if window:
            chunks.append(window)
        if window_end >= duration:
            break
        cursor += step
    return chunks


def dedupe_highlights(highlights: List[Dict], overlap_ratio: float = 0.35) -> List[Dict]:
    """Keep highest-scoring clips while suppressing overlapping candidates."""
    ranked = sorted(
        highlights,
        key=lambda h: (float(h.get("_raw_rank", h.get("score", 0))), int(h.get("score", 0))),
        reverse=True,
    )
    kept: List[Dict] = []
    for cand in ranked:
        cs, ce = float(cand["start_time"]), float(cand["end_time"])
        c_dur = max(0.1, ce - cs)
        overlaps = False
        for existing in kept:
            es, ee = float(existing["start_time"]), float(existing["end_time"])
            inter = max(0.0, min(ce, ee) - max(cs, es))
            if inter / min(c_dur, max(0.1, ee - es)) > overlap_ratio:
                overlaps = True
                break
        if not overlaps:
            kept.append(cand)
    return kept


_PLACEHOLDER_LITERALS = {
    "",
    "string",
    "string curta",
    "titulo",
    "title",
    "hook",
    "gancho",
    "cta",
    "n/a",
    "...",
    "null",
    "none",
}


def _is_placeholder_text(val: object) -> bool:
    txt = str(val or "").strip().lower()
    return (
        txt in _PLACEHOLDER_LITERALS
        or txt.startswith("titulo curioso")
        or txt.startswith("gancho em ")
        or txt.startswith("motivo real")
        or txt.startswith("chamada curta")
    )


def _ends_complete_sentence(text: str) -> bool:
    """Return True if segment text ends with terminal punctuation (not cut mid-phrase)."""
    stripped = (text or "").strip().rstrip('"\')]}» ')
    return bool(stripped) and stripped[-1] in ".!?…"


def _snap_end_to_sentence(
    segments: List[Dict],
    start: float,
    raw_end: float,
    min_dur: float,
    hard_cap: float,
) -> float:
    """Snap clip end to the nearest clean sentence boundary within [min_dur, hard_cap]."""
    if not segments:
        return min(raw_end, start + hard_cap)
    capped = min(raw_end, start + hard_cap)
    clean_ends = [
        float(s["end"])
        for s in segments
        if (start + min_dur) <= float(s["end"]) <= (start + hard_cap)
        and _ends_complete_sentence(str(s.get("text", "")))
    ]
    if clean_ends:
        # Prefer the clean ending closest to capped without overflowing hard_cap
        before_or_eq = [e for e in clean_ends if e <= capped + 1.5]
        return before_or_eq[-1] if before_or_eq else clean_ends[-1]
    seg_ends = [float(s["end"]) for s in segments if (start + min_dur) <= float(s["end"]) <= (start + hard_cap)]
    return seg_ends[-1] if seg_ends else capped


def _sanitize_highlights(
    raw_items: object,
    duration: float,
    platform: PlatformPreset,
    segments: Optional[List[Dict]] = None,
    source_title: str = "",
    niche: Optional[NicheProfile] = None,
) -> List[Dict]:
    if not isinstance(raw_items, list):
        return []
    cleaned: List[Dict] = []
    segs = segments or []
    hard_cap = 57.0 if platform.name in {"youtube_shorts", "instagram_reels"} else float(platform.max_duration)
    min_ok = max(12.0, platform.min_duration * 0.5)
    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        try:
            start = max(0.0, float(item.get("start_time", -1)))
            end = float(item.get("end_time", -1))
            score = int(float(item.get("score", 50)))
        except (TypeError, ValueError):
            continue
        if duration > 0:
            end = min(end, duration)
        dur = end - start
        if dur < min_ok:
            continue
        if segs or dur > hard_cap:
            end = _snap_end_to_sentence(segs, start, end, min_dur=min_ok, hard_cap=hard_cap)

        clip_texts = [s["text"] for s in segs if float(s["end"]) > start and float(s["start"]) < end]
        raw_hook = str(item.get("hook_title") or "").strip()
        if _is_placeholder_text(raw_hook):
            hook_title = _pick_best_hook(clip_texts, source_title, niche or NICHES["geral"])
        else:
            hook_title = raw_hook[:48].upper()

        raw_title = str(item.get("title") or "").strip()
        if _is_placeholder_text(raw_title):
            title = _build_clip_title(source_title, hook_title, idx, niche or NICHES["geral"])
        else:
            title = raw_title[:90]

        raw_reason = str(item.get("virality_reason") or "").strip()
        virality_reason = (
            "Gancho forte nos primeiros segundos e alta densidade de fala."
            if _is_placeholder_text(raw_reason)
            else raw_reason
        )
        raw_cta = str(item.get("cta_line") or "").strip()
        cta_line = (
            (niche.cta_suggestion if niche else "Comenta aqui sua opiniao e siga para a parte 2!")
            if _is_placeholder_text(raw_cta)
            else raw_cta
        )

        cleaned.append({
            "title": title,
            "hook_title": hook_title,
            "start_time": round(start, 2),
            "end_time": round(end, 2),
            "score": max(0, min(100, score)),
            "virality_reason": virality_reason,
            "cta_line": cta_line,
        })
    return cleaned


def _chat_completion_call(base_url: str, api_key: str, model: str, prompt: str, extra_headers: Optional[Dict[str, str]] = None) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 900,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "AutoShorts/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    msg = (body.get("choices") or [{}])[0].get("message") or {}
    text = msg.get("content") or msg.get("reasoning") or ""
    if not str(text).strip():
        raise RuntimeError(f"Empty LLM response for model {model}")
    return str(text)


def call_gemini_or_openai(prompt: str) -> str:
    """Resilient stdlib LLM cascade: OpenRouter (:free) -> Gemini -> Local llama-server/OpenAI."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not openrouter_key and (openai_key.startswith("sk-or-") or "openrouter.ai" in base_url):
        openrouter_key = openai_key

    last_err: Optional[Exception] = None
    if openrouter_key:
        cfg_model = os.getenv("OPENROUTER_MODEL", os.getenv("OPENAI_MODEL", "")).strip()
        free_candidates = [
            *( [cfg_model] if cfg_model and (cfg_model == "openrouter/free" or cfg_model.endswith(":free")) else [] ),
            "openrouter/free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3.5-lightning:free",
            "liquid/lfm-2.5-2.6b:free",
        ]
        seen = set()
        for m in free_candidates:
            if m in seen:
                continue
            seen.add(m)
            try:
                return _chat_completion_call(
                    "https://openrouter.ai/api/v1",
                    openrouter_key,
                    m,
                    prompt,
                    extra_headers={"HTTP-Referer": "https://github.com/AleplayTV/auto-shorts"},
                )
            except Exception as exc:
                last_err = exc

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            last_err = exc

    local_or_openai_url = os.getenv("LOCAL_LLM_URL", "").strip() or (base_url if "openrouter.ai" not in base_url else "")
    local_or_openai_key = "local" if (local_or_openai_url and "127.0.0.1" in local_or_openai_url) else (openai_key if not openai_key.startswith("sk-or-") else "")
    if local_or_openai_url and local_or_openai_key:
        model = os.getenv("OPENAI_MODEL", "qwen2.5-1.5b-instruct").strip()
        try:
            from .offline_llm import strip_reasoning_tags

            return strip_reasoning_tags(_chat_completion_call(local_or_openai_url, local_or_openai_key, model, prompt))
        except Exception as exc:
            if last_err is None:
                last_err = exc

    # On-demand 1-shot Termux fallback using Qwen2.5-1.5B GGUF without idle daemon RAM pressure
    llama_bin = shutil.which("llama-cli")
    gguf_cand = next(
        iter(sorted((Path.home() / "models" / "llm").glob("*.gguf"))),
        None,
    ) if (Path.home() / "models" / "llm").is_dir() else None
    if llama_bin and gguf_cand and gguf_cand.is_file():
        from .offline_llm import strip_reasoning_tags

        chatml_prompt = f"<|im_start|>system\nVoce responde apenas o texto final pedido em PT-BR, sem explicacoes ou meta-comentarios.<|im_end|>\n<|im_start|>user\n{prompt[:2800]}<|im_end|>\n<|im_start|>assistant\n"
        try:
            proc = subprocess.run(
                [
                    llama_bin, "-m", str(gguf_cand),
                    "-t", "4", "-c", "1536", "-n", "260", "--temp", "0.25",
                    "--single-turn", "--no-display-prompt", "--log-disable", "-p", chatml_prompt,
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            raw_out = proc.stdout or ""
            if "<|im_start|>assistant" in raw_out:
                raw_out = raw_out.rsplit("<|im_start|>assistant", 1)[-1]
            raw_out = re.sub(r"\[ Prompt:.*?\]|Exiting\.\.\.|<\|im_end\|>", "", raw_out, flags=re.S)
            raw_out = strip_reasoning_tags(raw_out)
            clean_lines = [
                ln for ln in raw_out.splitlines()
                if not any(m in ln.lower() for m in (".gguf", "/data/data/", "files/home", "llama_", "common_", "sampler", "build:", "model :", "modalities", "available commands", "▄▄", "██"))
                and not ln.lstrip().startswith((">", "/"))
            ]
            out_txt = "\n".join(clean_lines).strip()
            if out_txt and len(out_txt) >= 12:
                return out_txt
        except Exception as exc:
            if last_err is None:
                last_err = exc

    if last_err is not None:
        raise last_err
    raise RuntimeError("No OPENROUTER_API_KEY, GEMINI_API_KEY, or local llama-server configured.")


_PROTECTED_PROPER_NOUNS: Tuple[str, ...] = (
    "ChatGPT",
    "OpenAI",
    "DeepSeek",
    "Claude",
    "Gemini",
    "Nvidia",
    "SpaceX",
    "James Webb",
    "Starlink",
    "Bitcoin",
    "Ethereum",
    "Wall Street",
    "Nasdaq",
    "Ibovespa",
    "Selic",
    "Flow Podcast",
    "Podpah",
    "Inteligência Ltda",
    "PrimoCast",
    "Os Sócios",
    "One Piece",
    "Jujutsu Kaisen",
    "Solo Leveling",
    "Black Clover",
    "Dragon Ball",
    "Demon Slayer",
    "Kimetsu no Yaiba",
    "Shingeki no Kyojin",
    "Attack on Titan",
    "Hunter x Hunter",
    "My Hero Academia",
    "Boku no Hero",
    "Chainsaw Man",
    "Blue Lock",
    "Dandadan",
    "Sakamoto Days",
    "Sousou no Frieren",
    "Bleach",
    "Naruto",
    "Boruto",
    "Gear 5",
    "Akuma no Mi",
    "GTA 6",
)

_ASR_AND_TRANSLATION_HEAL_RULES: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bxat\s*gpt\b|\bchat\s*g\s*p\s*t\b", re.IGNORECASE), "ChatGPT"),
    (re.compile(r"\bopen\s*a\s*i\b|\bopen\s*ai\b", re.IGNORECASE), "OpenAI"),
    (re.compile(r"\bdip\s*sik\b|\bdeep\s*seek\b", re.IGNORECASE), "DeepSeek"),
    (re.compile(r"\bbit\s*c[óo]in\b|\bbit\s*coim\b", re.IGNORECASE), "Bitcoin"),
    (re.compile(r"\btaixa\s+selic\b|\bselique\b", re.IGNORECASE), "Selic"),
    (re.compile(r"\bibov[ée]spa\b", re.IGNORECASE), "Ibovespa"),
    (re.compile(r"\bp[óo]d\s*p[áa]\b", re.IGNORECASE), "Podpah"),
    (re.compile(r"\buma\s+pe[çc]a\b", re.IGNORECASE), "One Piece"),
    (re.compile(r"\btrevo\s+negro\b", re.IGNORECASE), "Black Clover"),
    (re.compile(r"\bbruke\b|\bbruk\b", re.IGNORECASE), "Brook"),
    (re.compile(r"\bluf+i\b", re.IGNORECASE), "Luffy"),
    (re.compile(r"\bzouro\b", re.IGNORECASE), "Zoro"),
    (re.compile(r"\bfach[íi]dico\b", re.IGNORECASE), "fatídico"),
    (re.compile(r"\barpan[áa]lise\b|\bbora\s+pran[áa]lise\b", re.IGNORECASE), "bora pra análise"),
    (re.compile(r"\bhak[íi]\b", re.IGNORECASE), "Haki"),
    (re.compile(r"\bimu\s+sama\b", re.IGNORECASE), "Imu-sama"),
    (re.compile(r"\bsidente\b|\bcidente\b", re.IGNORECASE), "acidente"),
    (re.compile(r"\bsukuna\b|\bsucuna\b", re.IGNORECASE), "Sukuna"),
    (re.compile(r"\bgoj[oô]\b|\bgoujo\b", re.IGNORECASE), "Gojo"),
    (re.compile(r"\btanjir[oô]\b", re.IGNORECASE), "Tanjiro"),
    (re.compile(r"\bjutsu\b", re.IGNORECASE), "Jujutsu"),
    (re.compile(r"\byusuk[ei]\b", re.IGNORECASE), "Yusuke"),
    (re.compile(r"\bjin\s*woo\b|\bgin\s*wu\b", re.IGNORECASE), "Jin-woo"),
)

_INTRO_BOILERPLATE_PHRASES: Tuple[str, ...] = (
    "salve galera",
    "salve, salve",
    "sem mais delongas",
    "bora pra análise",
    "bora pra analise",
    "bora para a análise",
    "deixa o like",
    "deixe o seu like",
    "se inscreve no canal",
    "inscreva-se no canal",
    "ativa o sininho",
    "bem-vindos a mais um vídeo",
    "no vídeo de hoje",
)


def heal_proper_nouns_and_asr(text: str) -> str:
    """Restore anime/pop-culture proper nouns and repair Whisper-tiny PT-BR phonetic hallucinations."""
    out = str(text or "")
    if not out:
        return ""
    for pat, repl in _ASR_AND_TRANSLATION_HEAL_RULES:
        out = pat.sub(repl, out)
    return out


def _clean_source_title(raw_title: str) -> str:
    cleaned = (raw_title or "").replace("&gt;", ">").replace("&quot;", '"')
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(
        r"\b(?:assistir|ep\.?\s*\d+|epis[óo]dio\s*\d+|dublado|legendado|full\s*hd|1080p|720p|480p|hd|mp4|x264|animesonline\w*|animesdigital\w*)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[>»]{1,3}", " ", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|:\"'“”")
    return heal_proper_nouns_and_asr(cleaned)


def sanitize_repetitive_text(text: str) -> str:
    """Strip Whisper decoding repetition loops (e.g. 'O que e isso? O que e isso? ...')."""
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    raw_words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", cleaned.lower())
    if len(raw_words) >= 10 and (len(set(raw_words)) / len(raw_words)) < 0.35:
        return ""
    # Collapse consecutive repeated phrases of 1-10 words repeated 3+ times
    cleaned = re.sub(
        r"(?i)\b((?:\S+\s+){0,9}\S+?)(?:\s+\1){2,}\b",
        r"\1",
        cleaned,
    )
    # Also collapse punctuation-separated repeated clauses (e.g. "O que é isso? O que é isso? ...")
    cleaned = re.sub(
        r"(?i)(.{4,40}?[.!?]+)\s*(?:\1\s*){2,}",
        r"\1",
        cleaned,
    )
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", cleaned.lower())
    if len(words) >= 10 and (len(set(words)) / len(words)) < 0.35:
        return ""
    return cleaned.strip()


def _build_clip_summary(texts: List[str], max_chars: int = 340) -> str:
    """Join clip transcript lines into a clean, readable PT-BR summary."""
    seen = set()
    ordered: List[str] = []
    for raw in texts:
        line = sanitize_repetitive_text(heal_proper_nouns_and_asr(" ".join(str(raw).split()).strip()))
        if not line or line.lower() in seen:
            continue
        seen.add(line.lower())
        ordered.append(line)
    joined = sanitize_repetitive_text(" ".join(ordered))
    if joined and joined[0].islower():
        joined = joined[0].upper() + joined[1:]
    if len(joined) <= max_chars:
        return joined
    cut = joined[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}..."


def _looks_english_title(title: str) -> bool:
    t = f" {re.sub(r'[^a-zA-ZÀ-ÿ0-9 ]+', ' ', (title or '').lower())} "
    if not t.strip():
        return False
    pt_hits = sum(
        1
        for m in (
            " de ", " do ", " da ", " dos ", " das ", " para ", " com ", " como ",
            " por ", " nao ", " não ", " que ", " voce ", " você ", " em ", " no ",
            " na ", " nos ", " nas ", " sobre ", " mais ", " tudo ", " vai ",
        )
        if m in t
    )
    en_hits = sum(
        1
        for m in (
            " the ", " of ", " those ", " guys ", " how ", " to ", " get ", " rich ",
            " fast ", " why ", " what ", " when ", " this ", " wealth ", " unlocking ",
            " went ", " criticize ", " got ", " reality ", " check ", " most ",
            " devastating ", " punch ", " revealed ", " reaching ", " level ",
            " broke ", " internet ", " new ", " king ", " form ", " god ", " and ",
            " with ", " from ", " into ", " s ", " in ", " on ", " has ", " more ",
            " than ", " people ", " elderly ", " young ", " news ", " responds ",
            " accusation ", " parallel ", " federal ", " police ", " was ", " created ",
            " explains ", " says ", " warns ",
        )
        if m in t
    )
    return (en_hits >= 2 and pt_hits == 0) or (en_hits >= 3 and pt_hits <= 1)


def _translate_title_to_ptbr(title: str) -> str:
    """Translate auto-translated/English source titles back into clean PT-BR while protecting proper nouns."""
    clean = _clean_source_title(title)
    if not clean or not _looks_english_title(clean):
        return clean
    try:
        protected_map: Dict[str, str] = {}
        masked = clean
        for idx, pn in enumerate(_PROTECTED_PROPER_NOUNS):
            pat = re.compile(re.escape(pn), re.IGNORECASE)
            if pat.search(masked):
                token = f"ZXPN{idx}ZX"
                protected_map[token] = pn
                masked = pat.sub(token, masked)
        q = urllib.parse.quote(masked[:180])
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=pt&dt=t&q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "AutoShorts/2.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        translated = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0]).strip()
        for token, orig_pn in protected_map.items():
            translated = re.sub(re.escape(token), orig_pn, translated, flags=re.IGNORECASE)
        if translated and len(translated) >= 6:
            return _clean_source_title(translated)
    except Exception:
        pass
    return ""


_GENERIC_HOOK_BANNED = {
    "finalmente vemos",
    "entao vemos",
    "então vemos",
    "vamos ver",
    "olha so",
    "olha só",
    "bora pra",
    "nesse video",
    "nesse vídeo",
    "como voces",
    "como vocês",
    "a gente ve",
    "a gente vê",
    "sem mais delongas",
    "salve galera",
}


def _polish_hook_phrase(words: List[str] | str, max_chars: int = 28) -> str:
    """Format a crisp 2-5 word uppercase hook without greetings, artifacts, or dangling words."""
    if isinstance(words, str):
        words = words.split()
    weak_starts = {
        "dele", "dela", "disso", "nisso", "entao", "então", "tipo", "mano", "cara",
        "mas", "e", "aí", "ai", "afirma", "disse", "diz", "conta", "explica",
        "usou", "fez", "teve", "foi", "era", "esta", "está", "falou", "fala",
        "porque", "que", "se", "o", "a", "os", "as", "um", "uma", "no", "na",
        "salve", "ola", "olá", "fala", "agora", "bem", "já", "ja", "tá", "ta",
        "eu", "ele", "ela", "isso", "isto", "finalmente", "vemos", "vamos",
        "gente", "pessoal", "voce", "você", "aconteceu", "nada", "tudo", "aqui", "ali",
    }
    dangling_ends = {
        "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
        "em", "na", "no", "e", "ou", "para", "por", "com", "que", "se", "maior",
        "melhor", "pior", "consegue", "nao", "não", "vai", "tem", "sao", "são", "muito",
        "hip", "toda", "todo", "alguns", "algumas", "grande", "essa", "esse", "ainda",
        "bem", "fala", "autoshorts", "foi", "era", "tá", "ta", "está", "gente", "coisa",
        "vemos", "ver", "disse", "falou", "tentando", "mesmo", "entao", "então", "quando",
        "como", "onde", "sobre", "contra", "entre", "quase", "outro", "outra",
    }
    cleaned_words: List[str] = []
    for raw_w in words:
        w = re.sub(r'^[>"\'“”»]+|[<"\'“”«]+$', "", str(raw_w or "")).strip()
        if w:
            cleaned_words.append(heal_proper_nouns_and_asr(w))
    trimmed = list(cleaned_words)
    while len(trimmed) > 2 and trimmed[0].lower().strip(",.:;!?") in weak_starts:
        trimmed.pop(0)
    chosen: List[str] = []
    for w in trimmed[:5]:
        cand = " ".join([*chosen, w])
        if len(cand) > max_chars and len(chosen) >= 2:
            break
        chosen.append(w)
    while len(chosen) > 2 and chosen[-1].lower().strip(",.:;!?") in dangling_ends:
        chosen.pop()
    while chosen and chosen[-1].lower().strip(",.:;!?") in dangling_ends and len(chosen) >= 2:
        if len([w for w in chosen[:-1] if len(w.strip(",.:;!?")) >= 4]) >= 1:
            chosen.pop()
        else:
            break
    out = " ".join(chosen).upper().strip(" ,;:-.\"'")
    if out.lower() in _GENERIC_HOOK_BANNED:
        return ""
    return out


def _pick_best_hook(texts: List[str], source_title: str, niche: NicheProfile) -> str:
    """Choose a clean, high-signal 2-5 word hook with concrete subjects instead of raw ASR filler."""
    filler = {
        "eh", "ah", "entao", "então", "tipo", "mano", "cara", "bom", "galera",
        "ola", "oi", "la", "lá", "sei", "aí", "ai", "salve", "delongas", "inscreve", "like",
    }
    best_line = ""
    best_score = -1
    best_has_kw = False
    _fragment_starts = ("a gente ", "eu ", "voce ", "você ", "pessoal ", "aconteceu ", "o que ", "nao ", "não ")

    clean_src = _clean_source_title(source_title)
    src_hook = ""
    if clean_src and not _looks_english_title(clean_src):
        first_clause = re.split(r"[!?:|—\-]+", clean_src)[0].strip()
        src_cand = _polish_hook_phrase(first_clause.split(), max_chars=28)
        if src_cand and len(src_cand.split()) >= 2:
            src_hook = src_cand

    for idx, raw in enumerate(texts[:12]):
        healed_raw = heal_proper_nouns_and_asr(str(raw))
        raw_low = healed_raw.lower()
        if any(bp in raw_low for bp in _INTRO_BOILERPLATE_PHRASES) or healed_raw.lstrip().startswith((">>", '"')):
            continue
        clauses = [c.strip() for c in re.split(r"[.!?]+", healed_raw) if len(c.split()) >= 3] or [healed_raw]
        clause_txt = clauses[0]
        words = [w for w in clause_txt.split() if (len(w) > 1 or w.lower() in {"e", "a", "o"}) and not w.isdigit()]
        if len(words) < 3:
            continue
        lowered = " ".join(words).lower()
        if lowered.startswith(_fragment_starts):
            continue
        kw_hits = sum(3 for kw in niche.hook_keywords if kw in lowered)
        score = kw_hits
        score += 2 if ("?" in healed_raw or "!" in healed_raw) else 0
        score -= sum(4 for w in words if w.lower().strip(",.?!") in filler)
        score += max(0, 2 - idx)
        if score > best_score:
            cand = _polish_hook_phrase(words)
            strong_tokens = [w for w in cand.split() if len(w.strip(",.:;!?")) >= 4]
            if cand and len(cand.split()) >= 2 and len(strong_tokens) >= 2:
                best_score = score
                best_line = cand
                best_has_kw = kw_hits > 0

    if src_hook and (best_score < 6 or not best_has_kw):
        return src_hook
    if best_line and best_score > 0 and best_has_kw:
        return best_line
    if src_hook:
        return src_hook

    pt_src = _translate_title_to_ptbr(source_title)
    if pt_src:
        cand = _polish_hook_phrase(pt_src.split())
        if cand and len(cand.split()) >= 2:
            return cand
    return "PRESTA ATENCAO NISSO"


def _build_clip_title(source_title: str, hook_title: str, part_num: int, niche: NicheProfile) -> str:
    clean_src = _clean_source_title(source_title)
    is_anime = "anime" in niche.label.lower() or "entretenimento_animes" in str(getattr(niche, "key", "")).lower()
    suffix = f" (Parte {part_num})" if part_num > 1 else ""
    if is_anime and clean_src and not _looks_english_title(clean_src):
        if hook_title and hook_title != "PRESTA ATENCAO NISSO" and len(hook_title) >= 6:
            hook_pretty = hook_title.title()
            if hook_pretty.lower() not in clean_src.lower():
                combo = f"{clean_src}: {hook_pretty}!{suffix}"
                return combo[:90]
        return f"{clean_src} — Cena Épica Dublada!{suffix}"[:90]

    if clean_src and not _looks_english_title(clean_src):
        base = clean_src[: 90 - len(suffix)].rstrip(" -|:")
        return f"{base}{suffix}"
    pt_translated = _translate_title_to_ptbr(clean_src)
    if pt_translated:
        if pt_translated.isupper():
            pt_translated = pt_translated.title()
        base = pt_translated[: 90 - len(suffix)].rstrip(" -|:")
        return f"{base}{suffix}"
    if hook_title and hook_title != "PRESTA ATENCAO NISSO":
        return f"{hook_title.title()} — {niche.label.split(',')[0]}"[:90]
    return f"Corte Imperdivel de {niche.label.split(',')[0]}"[:90]


def _heatmap_peak_for_window(heatmap: Optional[List[Dict]], start: float, end: float) -> float:
    """Return peak YouTube 'Most Replayed' intensity (0.0-1.0) overlapping [start, end]."""
    if not heatmap:
        return 0.0
    best = 0.0
    for pt in heatmap:
        hs = float(pt.get("start_time", 0.0))
        he = float(pt.get("end_time", 0.0))
        if he > start and hs < end:
            best = max(best, float(pt.get("value", 0.0)))
    return min(1.0, max(0.0, best))


def generate_action_climax_highlights(
    duration: float,
    platform: PlatformPreset,
    niche: NicheProfile,
    num_clips: int = 3,
    source_title: str = "",
    heatmap: Optional[List[Dict]] = None,
    video_path: Optional[Path] = None,
) -> List[Dict]:
    """Generate intelligent action/climax cuts for full anime episodes or videos lacking rich transcripts."""
    dur = float(duration or 0.0)
    if dur <= 10.0 and video_path and Path(video_path).is_file():
        try:
            import subprocess
            proc = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video_path)],
                capture_output=True, text=True, check=False, timeout=5,
            )
            dur = float((proc.stdout or "0").strip())
        except Exception:
            dur = 60.0
    if dur <= 10.0:
        dur = 60.0

    hard_cap = 57.0 if platform.name in {"youtube_shorts", "instagram_reels"} else float(platform.max_duration)
    target_dur = min(hard_cap, max(float(platform.min_duration), (float(platform.min_duration) + float(platform.max_duration)) / 2.0))
    if target_dur <= 0:
        target_dur = 45.0

    candidates: List[Dict] = []

    # If YouTube Most Replayed heatmap points exist, center around peak viewership moments
    if heatmap:
        sorted_peaks = sorted(heatmap, key=lambda p: float(p.get("value", 0.0)), reverse=True)
        for pk in sorted_peaks:
            s_peak = float(pk.get("start_time", 0.0))
            s0 = max(15.0 if dur > 60.0 else 0.0, s_peak - (target_dur * 0.35))
            s1 = min(dur, s0 + target_dur)
            s0 = max(0.0, s1 - target_dur)
            candidates.append({
                "title": "",
                "hook_title": "CLIMAX DO EPISODIO",
                "clip_summary": f"Pico de retencao e acao com som original dos dubladores aos {int(s0)}s.",
                "start_time": round(s0, 2),
                "end_time": round(s1, 2),
                "score": min(99, int(round(float(pk.get("value", 0.8)) * 100))),
                "virality_reason": f"Momento mais revisto (pico {int(float(pk.get('value', 0.8))*100)}%) no video original.",
                "cta_line": niche.cta_suggestion,
            })
            if len(candidates) >= num_clips * 2:
                break

    # If no heatmap or not enough clips, distribute across anime dramatic arc (avoiding 90s intro/outro)
    if len(candidates) < num_clips:
        start_bound = 90.0 if dur >= 300.0 else (15.0 if dur >= 60.0 else 0.0)
        end_bound = max(start_bound + target_dur, dur - (90.0 if dur >= 420.0 else 10.0))
        usable_span = max(target_dur, end_bound - start_bound)

        climax_hooks = [
            "MOMENTO EPICO",
            "A GRANDE REVELACAO",
            "PODER MAXIMO",
            "LUTA INCRIVEL",
            "NINGUEM ESPERAVA",
            "O CLIMAX DO EPISODIO",
            "CENA IMPACTANTE",
            "GOLPE DECISIVO",
        ]

        step = usable_span / max(1, num_clips + 1)
        for i in range(1, num_clips + 1):
            center = start_bound + (i * step)
            s0 = max(start_bound, center - (target_dur / 2.0))
            s1 = min(dur, s0 + target_dur)
            s0 = max(0.0, s1 - target_dur)
            hook = climax_hooks[(i - 1) % len(climax_hooks)]
            candidates.append({
                "title": "",
                "hook_title": hook,
                "clip_summary": f"Corte do arco #{i} preservando audio original dos dubladores e trilha nativa.",
                "start_time": round(s0, 2),
                "end_time": round(s1, 2),
                "score": 85 + (i * 3),
                "virality_reason": f"Arco de tensao cinematografica #{i} com audio nativo dos dubladores.",
                "cta_line": niche.cta_suggestion,
            })

    picked = dedupe_highlights(candidates)[:num_clips]
    for idx, clip in enumerate(picked, start=1):
        clip["title"] = _build_clip_title(source_title, clip["hook_title"], idx, niche)
    return picked


def score_segments_offline(
    transcript: Dict,
    platform: PlatformPreset,
    niche: NicheProfile,
    num_clips: int,
    source_title: str = "",
    heatmap: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Zero-cost heuristic + YouTube Most-Replayed heatmap clipper when no LLM is used."""
    segments = transcript.get("segments", [])
    if not segments:
        return generate_action_climax_highlights(
            duration=float(transcript.get("duration", 0.0)),
            platform=platform,
            niche=niche,
            num_clips=num_clips,
            source_title=source_title,
            heatmap=heatmap,
        )

    hard_cap = 57.0 if platform.name in {"youtube_shorts", "instagram_reels"} else float(platform.max_duration)
    target_dur = (platform.min_duration + platform.max_duration) / 2.0
    total_video_dur = max(float(transcript.get("duration") or 0.0), float(segments[-1].get("end", 0.0)))
    candidates: List[Dict] = []

    for i, first in enumerate(segments):
        # Prefer starting right after a concluded previous sentence rather than mid-clause
        if i > 0 and not _ends_complete_sentence(str(segments[i - 1].get("text", ""))):
            first_txt = str(first.get("text", "")).lstrip()
            if first_txt and first_txt[0].islower():
                continue

        start = float(first["start"])
        texts: List[str] = []
        end = start
        last_clean_idx = -1
        for offset, seg in enumerate(segments[i:]):
            seg_end = float(seg["end"])
            if seg_end - start > hard_cap and texts:
                break
            texts.append(seg["text"])
            end = seg_end
            if (end - start) >= platform.min_duration and _ends_complete_sentence(str(seg.get("text", ""))):
                last_clean_idx = offset
                if (end - start) >= target_dur - 4.0:
                    break
        if last_clean_idx >= 0 and last_clean_idx + 1 < len(texts):
            texts = texts[: last_clean_idx + 1]
            end = float(segments[i + last_clean_idx]["end"])

        dur = end - start
        if dur < platform.min_duration and i > 0:
            continue
        if dur <= 5.0:
            continue

        joined = heal_proper_nouns_and_asr(" ".join(texts))
        lowered = joined.lower()
        keyword_hits = sum(1 for kw in niche.hook_keywords if kw in lowered)
        first_lower = heal_proper_nouns_and_asr(texts[0]).lower()
        first_line_bonus = 15 if any(kw in first_lower for kw in niche.hook_keywords) else 0
        # Reward clips whose opening line mentions a key subject word from the video's title
        title_words = {
            w.lower().strip("[]():,.-!?")
            for w in (source_title or "").split()
            if len(w.strip("[]():,.-!?")) >= 5
        }
        topic_opener_bonus = 10 if any(tw in first_lower for tw in title_words) else 0
        opener_energy_bonus = 6 if ("!" in texts[0] or "?" in texts[0]) else 0
        punctuation_hits = min(36, joined.count("?") * 6 + joined.count("!") * 4)
        closure_bonus = 12 if texts[-1].strip().endswith("?") else (10 if _ends_complete_sentence(texts[-1]) else 0)
        words_per_sec = len(joined.split()) / max(1.0, dur)
        pace_score = min(25, int(words_per_sec * 8))
        heat_peak = _heatmap_peak_for_window(heatmap, start, end)
        heat_bonus = int(round(heat_peak * 28)) if heat_peak >= 0.40 else 0

        # Anti-Intro & Climax Arc Discipline: avoid 0.0s YouTuber greeting intros on full-length videos
        intro_penalty = 0
        if total_video_dur >= 150.0 and start < 25.0:
            intro_penalty += 38
        if any(bp in lowered[:220] for bp in _INTRO_BOILERPLATE_PHRASES):
            intro_penalty += 32

        climax_bonus = 0
        if total_video_dur >= 120.0:
            rel_pos = start / max(1.0, total_video_dur)
            if 0.12 <= rel_pos <= 0.85:
                climax_bonus = 14

        unclamped_rank = (
            38.0
            + keyword_hits * 8.0
            + first_line_bonus
            + topic_opener_bonus
            + opener_energy_bonus
            + punctuation_hits
            + closure_bonus
            + pace_score
            + heat_bonus
            + climax_bonus
            - intro_penalty
            + (heat_peak * 5.0)
        )
        raw_score = max(40, min(99, int(round(unclamped_rank))))
        hook = _pick_best_hook(texts, source_title, niche)
        heat_note = f", Most Replayed {int(heat_peak * 100)}%" if heat_bonus > 0 else ""
        candidates.append({
            "title": "",
            "hook_title": hook,
            "clip_summary": _build_clip_summary(texts),
            "start_time": round(start, 2),
            "end_time": round(min(end, start + platform.max_duration), 2),
            "score": raw_score,
            "_raw_rank": round(unclamped_rank, 3),
            "virality_reason": f"Heuristica offline: {keyword_hits} gatilhos de nicho, ritmo {words_per_sec:.1f} pal/s{heat_note}.",
            "cta_line": niche.cta_suggestion,
        })

    if not candidates and segments:
        end = min(float(segments[-1]["end"]), float(segments[0]["start"]) + platform.max_duration)
        texts = [s["text"] for s in segments]
        hook = _pick_best_hook(texts, source_title, niche)
        candidates.append({
            "title": "",
            "hook_title": hook,
            "clip_summary": _build_clip_summary(texts),
            "start_time": round(float(segments[0]["start"]), 2),
            "end_time": round(end, 2),
            "score": 60,
            "virality_reason": "Janela unica disponivel no video.",
            "cta_line": niche.cta_suggestion,
        })

    picked = dedupe_highlights(candidates)[:num_clips]
    for idx, clip in enumerate(picked, start=1):
        clip["title"] = _build_clip_title(source_title, clip["hook_title"], idx, niche)
    return picked


def detect_highlights(
    transcript: Dict,
    platform_key: str = "tiktok_rewards",
    niche_key: str = "geral",
    num_clips: int = 3,
    llm_fn: Optional[Callable[[str], str]] = None,
    use_llm: bool = True,
    learning_context: str = "",
    source_title: str = "",
    heatmap: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Select ranked viral clip intervals for the chosen platform and Brazilian niche."""
    platform = PLATFORMS.get(platform_key, PLATFORMS["tiktok_rewards"])
    niche = NICHES.get(niche_key, NICHES["geral"])
    segments = transcript.get("segments", [])
    duration = float(transcript.get("duration", 0.0))

    if not segments:
        return generate_action_climax_highlights(
            duration=duration,
            platform=platform,
            niche=niche,
            num_clips=num_clips,
            source_title=source_title,
            heatmap=heatmap,
        )

    has_api = bool(
        llm_fn
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("LOCAL_LLM_URL")
        or os.getenv("OPENAI_API_KEY")
    )
    if not use_llm or not has_api:
        return score_segments_offline(
            transcript, platform, niche, num_clips, source_title=source_title, heatmap=heatmap
        )

    caller = llm_fn or call_gemini_or_openai
    all_candidates: List[Dict] = []
    for chunk in chunk_segments(segments, duration):
        prompt = BR_HIGHLIGHT_PROMPT.format(
            platform_name=platform.name,
            niche_label=niche.label,
            min_dur=platform.min_duration,
            max_dur=platform.max_duration,
            sweet_spot=platform.sweet_spot,
            num_clips=num_clips,
            cta_suggestion=niche.cta_suggestion,
            transcript_text=format_transcript_for_llm(chunk),
        )
        if source_title:
            prompt = f"Titulo original do video: {source_title}\n\n{prompt}"
        if learning_context:
            prompt = f"{prompt}\n\n{learning_context}"
        try:
            raw = caller(prompt)
            parsed = _parse_json_loose(raw)
            all_candidates.extend(
                _sanitize_highlights(
                    parsed.get("highlights"),
                    duration,
                    platform,
                    segments=chunk,
                    source_title=source_title,
                    niche=niche,
                )
            )
        except Exception:
            continue

    deduped = dedupe_highlights(all_candidates)
    if not deduped:
        off = score_segments_offline(
            transcript, platform, niche, num_clips, source_title=source_title, heatmap=heatmap
        )
        return off or generate_action_climax_highlights(
            duration=duration,
            platform=platform,
            niche=niche,
            num_clips=num_clips,
            source_title=source_title,
            heatmap=heatmap,
        )
    for clip in deduped:
        if not clip.get("clip_summary"):
            s0, s1 = float(clip["start_time"]), float(clip["end_time"])
            clip["clip_summary"] = _build_clip_summary(
                [s["text"] for s in segments if float(s["end"]) > s0 and float(s["start"]) < s1]
            )
    return deduped[:num_clips]
