"""Multi-Horizon Viral Radar — opens creator reach beyond single-niche anime into high-RPM trends."""

import concurrent.futures
import re
import time
from typing import Callable, Dict, List, Optional

from .anime_trends import get_releasing_anime_radar
from .mahoraga import MahoragaEngine, immunize_spoken_script
from .world_news import fetch_world_news_headlines, translate_en_to_ptbr

_TITLE_TX_CACHE: Dict[str, str] = {}
_YT_RADAR_CACHE: Dict[str, tuple[float, List[Dict]]] = {}
_HORIZON_CACHE: Dict[tuple, tuple[float, Dict]] = {}


HORIZON_CATALOG: Dict[str, Dict] = {
    "podcast_debates": {
        "label": "Podcasts, Debates & Cortes",
        "niche": "podcast",
        "playlist": "Podcasts & Debates Virais - Shorts",
        "cards": [
            {
                "title_pt": "Cortes quentes de podcasts (Flow, Podpah, Inteligência Ltda)",
                "hook_suggestion": "NINGUÉM ESPERAVA ESSA RESPOSTA",
                "why_viral": "Gatilho de Conflito & Curiosidade — cortes de opinião polarizadora seguram 75%+ nos primeiros 3s.",
                "youtube_query": "corte podcast polemica revelacao brasil",
                "source": "Radar Podcasts BR",
                "niche": "podcast",
            },
            {
                "title_pt": "Histórias reais de virada financeira e bastidores",
                "hook_suggestion": "ELE PERDEU TUDO ANTES DISSO",
                "why_viral": "Storytelling em 3 atos com quebra de expectativa e identificação emocional.",
                "youtube_query": "podcast historia superacao dinheiro brasil",
                "source": "Radar Storytelling",
                "niche": "podcast",
            },
        ],
    },
    "dinheiro_ia": {
        "label": "Dinheiro, Negócios & IA",
        "niche": "ia_tech",
        "playlist": "IA, Dinheiro & Futuro - Shorts",
        "cards": [
            {
                "title_pt": "Ferramentas novas de IA que substituem tarefas manuais hoje",
                "hook_suggestion": "ISSO ECONOMIZA HORAS NO DIA",
                "why_viral": "Alto RPM e alto índice de Salvamentos/Compartilhamentos.",
                "youtube_query": "inteligencia artificial ferramenta gratis brasil",
                "source": "Radar IA & SaaS",
                "niche": "ia_tech",
            },
            {
                "title_pt": "Erros invisíveis que corroem salário, juros e investimentos",
                "hook_suggestion": "O ERRO QUE CUSTA SEU SALÁRIO",
                "why_viral": "Aversão à perda — o cérebro presta atenção imediata quando sente risco financeiro.",
                "youtube_query": "erro financeiro juros investimentos brasil podcast",
                "source": "Radar Finanças BR",
                "niche": "financas",
            },
        ],
    },
    "psicologia_misterios": {
        "label": "Psicologia, Mente & Mistérios",
        "niche": "desenvolvimento_pessoal",
        "playlist": "Psicologia, Mente & Mistérios - Shorts",
        "cards": [
            {
                "title_pt": "Viés cognitivo e sinais silenciosos de linguagem corporal",
                "hook_suggestion": "SEU CÉREBRO CAI NESSE TRUQUE",
                "why_viral": "Efeito Mentalista — o espectador testa em si mesmo durante o vídeo e assiste até o loop.",
                "youtube_query": "psicologia manipulacao linguagem corporal podcast brasil",
                "source": "Radar Mentalista",
                "niche": "desenvolvimento_pessoal",
            },
            {
                "title_pt": "Fatos históricos e mistérios pouco contados na escola",
                "hook_suggestion": "ESCONDERAM ISSO NOS LIVROS",
                "why_viral": "Lacuna de curiosidade — retém audiência curiosa com conclusão surpreendente.",
                "youtube_query": "curiosidade historia misterio pouco conhecido brasil",
                "source": "Radar Curiosidades",
                "niche": "geral",
            },
        ],
    },
    "saude_treino": {
        "label": "Saúde, Neurociência & Treino",
        "niche": "saude_fitness",
        "playlist": "Saúde, Neurociência & Treino - Shorts",
        "cards": [
            {
                "title_pt": "Sono, dopamina, energia e hábitos práticos explicados por médicos",
                "hook_suggestion": "MUDE ISSO HOJE AO ACORDAR",
                "why_viral": "Utilidade imediata — gera compartilhamento direto no WhatsApp/Instagram.",
                "youtube_query": "neurociencia sono dopamina podcast medico brasil",
                "source": "Radar Saúde & Mente",
                "niche": "saude_fitness",
            },
        ],
    },
    "ciencia_espaco": {
        "label": "Ciência, Espaço & Mundo Hoje",
        "niche": "noticias_mundiais",
        "playlist": "Noticias Mundiais & Ciência - Shorts",
        "cards": [],
    },
    "entretenimento_cultura": {
        "label": "Cinema, Séries, Games & Animes",
        "niche": "entretenimento_animes",
        "playlist": "Cinema, Games & Animes - Shorts",
        "cards": [
            {
                "title_pt": "Easter eggs, finais explicados e teorias virais de filmes/games",
                "hook_suggestion": "NINGUÉM NOTOU ESSE DETALHE",
                "why_viral": "Fandom engajado gera comentários discutindo teorias (sinal forte para Exploit).",
                "youtube_query": "final explicado easter egg filme serie game brasil",
                "source": "Radar Cultura Pop",
                "niche": "entretenimento_animes",
            },
        ],
    },
}


def _ptbr_headline(title: str, lang: str = "") -> str:
    clean = " ".join((title or "").split()).strip()
    if not clean:
        return ""
    if str(lang or "").lower() == "pt":
        return clean
    from .highlights import _looks_english_title
    if str(lang or "").lower() == "en" or _looks_english_title(clean):
        cached = _TITLE_TX_CACHE.get(clean)
        if cached:
            return cached
        try:
            pt = translate_en_to_ptbr(clean)
            if pt:
                _TITLE_TX_CACHE[clean] = pt
                return pt
        except Exception:
            pass
    return clean


def _fetch_youtube_trend_cards(horizon_key: str, query: str, kind: str, label: str, niche: str, playlist: str, limit: int = 2) -> List[Dict]:
    now = time.time()
    cached = _YT_RADAR_CACHE.get(horizon_key)
    if cached and (now - cached[0]) < 360:
        return cached[1][:limit]
    rows: List[Dict] = []
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "no_warnings": True, "socket_timeout": 5, "extractor_retries": 0}) as ydl:
            info = ydl.extract_info(f"ytsearch4:{query}", download=False) or {}
            for e in (info.get("entries") or []):
                vid = str(e.get("id") or "").strip()
                dur = float(e.get("duration") or 0)
                if not vid or dur < 75 or dur > 3600:
                    continue
                views = int(e.get("view_count") or 0)
                dur_min = f"{int(dur // 60)}:{int(dur % 60):02d}"
                v_label = f"{views // 1000}k views" if views >= 1000 else f"{dur_min} min"
                rows.append({
                    "horizon": horizon_key,
                    "category_kind": kind,
                    "kind_label": f"{label} • Em alta",
                    "badge": label,
                    "title_pt": str(e.get("title") or query).strip(),
                    "hook_suggestion": " ".join(str(e.get("title") or "").split()[:4]).upper()[:28] or "CORTE QUENTE",
                    "why_viral": f"Video real pronto para corte • Canal: {e.get('uploader') or e.get('channel') or 'YouTube'}",
                    "metric_badge": f"{v_label} • {dur_min}",
                    "rpm_hint": "Cortes reais + Legenda 30px",
                    "youtube_query": f"https://www.youtube.com/watch?v={vid}",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "image_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "source": str(e.get("uploader") or e.get("channel") or "YouTube"),
                    "niche": niche,
                    "playlist": playlist,
                    "mode": "video_cut",
                })
                if len(rows) >= limit:
                    break
        if rows:
            _YT_RADAR_CACHE[horizon_key] = (now, rows)
    except Exception:
        pass
    return rows


def fetch_horizon_trends(
    horizon: str = "todos",
    limit: int = 24,
    news_fetcher: Optional[Callable[[str, int], List[Dict]]] = None,
    anime_fetcher: Optional[Callable[[int], List[Dict]]] = None,
    include_live_youtube: bool = False,
) -> Dict:
    """Return enriched multi-horizon trend cards with real covers, live stats, news & anime data."""
    key = (horizon or "todos").strip().lower()
    use_cache = (news_fetcher is None and anime_fetcher is None)
    cache_k = (key, limit, bool(include_live_youtube))
    if use_cache:
        hit = _HORIZON_CACHE.get(cache_k)
        if hit and (time.time() - hit[0]) < 240:
            return hit[1]

    items: List[Dict] = []

    def _add_card(c: Dict) -> None:
        if len(items) < limit:
            items.append(c)

    target_keys = list(HORIZON_CATALOG.keys()) if key in {"todos", "all", ""} else ([key] if key in HORIZON_CATALOG else list(HORIZON_CATALOG.keys()))
    kind_map = {
        "podcast_debates": ("podcast", "Podcast & Cortes", "Alto compartilhamento"),
        "dinheiro_ia": ("financas", "Dinheiro & IA", "RPM Premium (Financas/SaaS)"),
        "psicologia_misterios": ("psicologia", "Psicologia & Mente", "Loop alto (75%+ Viewed)"),
        "saude_treino": ("saude", "Saude & Neuro", "Salvamentos WhatsApp/IG"),
        "entretenimento_cultura": ("cultura", "Cultura Pop", "Comentarios & Teorias"),
        "ciencia_espaco": ("ciencia", "Ciencia & Mundo", "Curiosidade global"),
    }

    want_news = key in {"todos", "all", "", "ciencia_espaco", "dinheiro_ia", "noticias_mundiais"}
    want_anime = key in {"todos", "all", "", "entretenimento_cultura"}
    yt_keys = target_keys[:3] if (include_live_youtube and key in {"todos", "all", ""}) else (target_keys if include_live_youtube else [])

    news_rows: List[Dict] = []
    anime_rows: List[Dict] = []
    yt_rows_by_hk: Dict[str, List[Dict]] = {}

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        fut_news = None
        fut_anime = None
        fut_yts: Dict[str, concurrent.futures.Future] = {}
        wait_list: List[concurrent.futures.Future] = []
        if want_news:
            topic_map = {"dinheiro_ia": "tech", "ciencia_espaco": "world"}.get(key, "world")
            news_cap = 10 if key in {"ciencia_espaco", "noticias_mundiais"} else 8
            get_news = news_fetcher or (lambda t, l: fetch_world_news_headlines(topic=t, limit=l))
            fut_news = pool.submit(get_news, topic_map, news_cap)
            wait_list.append(fut_news)
        if want_anime:
            anime_cap = 16 if key == "entretenimento_cultura" else 8
            get_anime = anime_fetcher or (lambda l: get_releasing_anime_radar(limit=l, category="all"))
            fut_anime = pool.submit(get_anime, anime_cap)
            wait_list.append(fut_anime)
        for hk in yt_keys:
            meta = HORIZON_CATALOG[hk]
            if meta.get("cards"):
                ckind, klabel, _ = kind_map.get(hk, ("geral", meta["label"], "Multi-nicho"))
                f_yt = pool.submit(
                    _fetch_youtube_trend_cards,
                    hk,
                    meta["cards"][0]["youtube_query"],
                    ckind,
                    klabel,
                    meta["niche"],
                    meta["playlist"],
                    2 if key in {"todos", "all", ""} else 4,
                )
                fut_yts[hk] = f_yt
                wait_list.append(f_yt)

        concurrent.futures.wait(wait_list, timeout=9.0)

        if fut_news is not None and fut_news.done():
            try:
                news_rows = fut_news.result() or []
            except Exception:
                news_rows = []
        if fut_anime is not None and fut_anime.done():
            try:
                anime_rows = fut_anime.result() or []
            except Exception:
                anime_rows = []
        for hk, f in fut_yts.items():
            if f.done():
                try:
                    yt_rows_by_hk[hk] = f.result() or []
                except Exception:
                    yt_rows_by_hk[hk] = []
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # 1. Live global journalism / Economy / Tech / Space headlines (translated to clean PT-BR)
    for h in news_rows:
        raw_title = str(h.get("title") or "").strip()
        if not raw_title:
            continue
        pt_title = _ptbr_headline(raw_title, str(h.get("lang") or ""))
        pt_sum = _ptbr_headline(str(h.get("summary") or "")[:180], str(h.get("lang") or ""))
        cat_lbl = "Ciencia & Espaco" if h.get("category") == "ciencia_espaco" else ("Tech & Economia" if h.get("category") in {"tech_ia", "economia"} else "Noticia ao vivo")
        _add_card({
            "horizon": "ciencia_espaco",
            "category_kind": "noticia",
            "kind_label": cat_lbl,
            "badge": "Mundo & Ciencia",
            "title_pt": pt_title,
            "hook_suggestion": " ".join(pt_title.split()[:4]).upper()[:28],
            "why_viral": pt_sum or "Manchete real traduzida com foto original para narração Kokoro.",
            "metric_badge": str(h.get("source") or "Imprensa"),
            "rpm_hint": "Alta retenção informativa",
            "youtube_query": pt_title[:60],
            "url": h.get("url", ""),
            "image_url": h.get("image_url", ""),
            "source": h.get("source", "Imprensa Global"),
            "niche": "noticias_mundiais",
            "mode": "news_narrated",
        })

    # 2. Live multi-category Anime radar: airing, famous of year, top-liked season & next-year releases
    for a in anime_rows:
        sc = int(a.get("score") or 0)
        pop = int(a.get("popularity") or 0)
        fav = int(a.get("favourites") or 0)
        ep = a.get("next_episode")
        hrs = a.get("hours_until_next")
        genres = ", ".join((a.get("genres") or [])[:3])
        stats_parts = []
        if sc > 0:
            stats_parts.append(f"Nota {sc}%")
        if fav > 0:
            stats_parts.append(f"{fav // 1000}k curtidas" if fav >= 1000 else f"{fav} curtidas")
        if ep:
            stats_parts.append(f"Ep {ep}")
        if isinstance(hrs, (int, float)) and hrs > 0:
            stats_parts.append(f"em {int(hrs)}h")
        elif pop > 0:
            stats_parts.append(f"{pop // 1000}k fas")
        cat_lbl = str(a.get("anime_category_label") or "Anime & Teorias")
        _add_card({
            "horizon": "entretenimento_cultura",
            "category_kind": "anime",
            "anime_category": a.get("anime_category", "em_exibicao"),
            "kind_label": cat_lbl,
            "badge": "Anime & Teorias",
            "title_pt": a.get("title", ""),
            "hook_suggestion": f"EPISODIO {ep} MUDOU TUDO" if ep else f"TEORIA SECRETA: {str(a.get('title') or '').upper()[:18]}",
            "why_viral": (f"Generos: {genres}. " if genres else "") + "Teorias, explicacoes finais, curiosidades e busca alta.",
            "metric_badge": " • ".join(stats_parts) or "Tendencia AniList",
            "rpm_hint": "Teorias & Animes (Alta Retencao)",
            "youtube_query": a.get("youtube_query", ""),
            "image_url": a.get("image_url", ""),
            "source": str(a.get("source") or "AniList").upper(),
            "niche": "entretenimento_animes",
            "playlist": "Cinema, Games & Animes - Shorts",
            "mode": "video_cut",
        })

    # 3. Real YouTube trending videos + Curated Mentalist angles across niches
    for hk in target_keys:
        meta = HORIZON_CATALOG[hk]
        ckind, klabel, rpm_lbl = kind_map.get(hk, ("geral", meta["label"], "Multi-nicho"))
        for ycard in yt_rows_by_hk.get(hk, []):
            _add_card(ycard)
        for card in meta.get("cards", []):
            _add_card({
                "horizon": hk,
                "category_kind": ckind,
                "kind_label": klabel,
                "badge": meta["label"],
                "title_pt": card["title_pt"],
                "hook_suggestion": card["hook_suggestion"],
                "why_viral": card["why_viral"],
                "metric_badge": card["source"],
                "rpm_hint": rpm_lbl,
                "youtube_query": card["youtube_query"],
                "source": card["source"],
                "niche": card.get("niche") or meta["niche"],
                "playlist": meta["playlist"],
                "mode": "video_cut",
            })

    horizons_meta = [{"key": "todos", "label": "Todos os Horizontes"}] + [
        {"key": k, "label": v["label"]} for k, v in HORIZON_CATALOG.items()
    ]
    result = {"horizon": key, "horizons": horizons_meta, "items": items[:limit]}
    if use_cache and result["items"]:
        _HORIZON_CACHE[cache_k] = (time.time(), result)
    return result


def _clamp_script_at_sentence(text: str, max_words: int = 105) -> str:
    """Keep spoken scripts safely under Shorts 55s cap ending on a complete sentence."""
    words = text.split()
    if len(words) <= max_words:
        return text
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    kept: List[str] = []
    count = 0
    for s in sentences:
        sw = len(s.split())
        if kept and count + sw > max_words:
            break
        kept.append(s)
        count += sw
    if kept and count <= max_words + 8:
        return " ".join(kept)
    trimmed = " ".join(words[:max_words]).rstrip(",;:")
    return trimmed if trimmed.endswith((".", "!", "?")) else f"{trimmed}."


def build_horizon_spoken_script(item: Dict, use_llm: bool = True) -> str:
    """Build a natural 85-110 word PT-BR spoken Shorts script (38-45s), never reading why_viral notes."""
    from .highlights import call_gemini_or_openai
    from .team import humanize_ptbr_script, is_llm_configured

    title = str(item.get("title_pt") or item.get("title") or "Curiosidade de hoje").strip()
    hook = str(item.get("hook_suggestion") or item.get("hook_title") or "Presta atenção nisso").strip()
    source = str(item.get("source") or "Radar AutoShorts").strip()
    horizon = str(item.get("horizon") or "").strip().lower()

    if use_llm and is_llm_configured():
        prompt = (
            "Voce e roteirista profissional de Shorts/TikTok de altissima retencao no Brasil.\n"
            f"Tema: {title}\nGancho sugerido: {hook}\nCategoria: {horizon or 'geral'}\n"
            "Escreva SOMENTE o texto falado pelo narrador em PT-BR natural, ESTRITAMENTE entre 75 e 100 palavras (maximo absoluto 45 segundos).\n"
            "Estrutura: 1) Frase de choque nos primeiros 3s, 2) Explicacao clara com exemplo pratico do dia a dia, "
            "3) Virada surpreendente, 4) Chamada curta pra comentar.\n"
            "NAO inclua instrucoes tecnicas, aspas, asteriscos, hashtags ou marcacoes como [corte]."
        )
        try:
            from .offline_llm import strip_reasoning_tags

            raw = strip_reasoning_tags(call_gemini_or_openai(prompt))
            cleaned = re.sub(r"\[[^\]]*\]|\*", "", raw, flags=re.S).strip()
            low = f" {cleaned.lower()} "
            meta_or_en = (
                "/data/", ".gguf", "files/home", "llama_", "sampler", "build:",
                "they ask", "need craft", "narrador em pt", "texto falado", "frase de choque",
                "estrutura:", "roteiro:", " the ", " spoken ", " write ", " you should ",
            )
            en_tokens = sum(1 for tok in (" the ", " and ", " they ", " ask ", " with ", " craft ", " spoken ", " about ") if tok in low)
            if any(bad in low for bad in meta_or_en) or en_tokens >= 2:
                cleaned = ""
            cleaned = _clamp_script_at_sentence(cleaned, max_words=105) if cleaned else ""
            if len(cleaned.split()) >= 55:
                return humanize_ptbr_script(cleaned)
        except Exception:
            pass

    topic_low = f" {title.lower()} "
    is_tech_ai = any(k in topic_low for k in (" ia ", "arm", "celular", "offline", "modelo", "nuvem", "chip", "tecnologia", "app", "software"))
    is_finance = (not is_tech_ai) and ("dinheiro" in horizon or "finan" in horizon or any(k in topic_low for k in ("salario", "juros", "taxa", "invest", "dinheiro")))

    mahoraga = MahoragaEngine()
    niche_key = "ia_tech" if is_tech_ai else ("financas" if is_finance else (horizon or "geral"))
    spoke_idx, spoke = mahoraga.select_adaptive_spoke(niche_key, title)

    if is_tech_ai:
        variants = [
            (
                f"Muita gente ainda acha que inteligência artificial só funciona pagando assinatura cara na nuvem. "
                f"A virada em {title.lower()} é que os processadores de celular atuais já rodam modelos leves direto no aparelho, sem depender de internet. "
                f"Isso traz resposta na hora, privacidade total dos seus dados e zero custo mensal com servidor externo. "
                f"Você usaria uma IA 100% offline direto no seu celular? Comenta aqui embaixo!"
            ),
            (
                f"Olha o salto silencioso da inteligência artificial em {title.lower()}. "
                f"Enquanto todo mundo olha para servidores gigantes, a computação local no bolso já entrega velocidade real e autonomia sem mensalidade. "
                f"Quem dominar essas ferramentas agora sai muito na frente no trabalho e nos projetos pessoais. "
                f"Qual tarefa você automatizaria primeiro no seu celular? Deixa nos comentários!"
            ),
            (
                f"O jogo da inteligência artificial mudou com {title.lower()}, e pouca gente percebeu o tamanho disso. "
                f"Rodar modelos otimizados direto no dispositivo corta latência, protege sua privacidade e elimina gargalos de conexão. "
                f"Na prática, o aparelho que você já tem na mão vira um estúdio completo de produtividade. "
                f"Você prefere ferramentas locais ou na nuvem? Comenta aqui!"
            ),
        ]
    elif is_finance:
        variants = [
            (
                f"O maior vazamento no orçamento quase nunca aparece numa compra gigante, e sim no piloto automático da rotina. "
                f"Ao analisar {title.lower()}, fica claro como pequenas taxas recorrentes e decisões por impulso somam um valor alto no fim do ano. "
                f"Trocar dois hábitos caros por regras simples libera caixa todos os meses sem cortar o que realmente importa. "
                f"Qual gasto invisível você cortou primeiro? Deixa nos comentários!"
            ),
            (
                f"Muita gente trabalha dobrado e não vê o dinheiro sobrar por causa de um erro silencioso ligado a {title.lower()}. "
                f"Quando você coloca os números lado a lado, descobre que pequenos ajustes de alocação valem mais do que promessas milagrosas. "
                f"Organizar reservas e cortar juros invisíveis muda seu patamar financeiro em poucos meses. "
                f"Você já aplica essa regra na sua conta? Comenta aqui embaixo!"
            ),
            (
                f"Existe uma diferença clara entre ganhar mais e construir patrimônio de verdade em {title.lower()}. "
                f"Quem observa os ciclos de juros e fluxo de caixa sabe que proteção vem antes da rentabilidade extrema. "
                f"Com disciplina semanal e metas objetivas, o efeito composto começa a trabalhar a seu favor. "
                f"Qual é sua meta financeira para este ano? Conta nos comentários!"
            ),
        ]
    elif "psico" in horizon or "saude" in horizon:
        variants = [
            (
                f"Você já reparou por que o seu cérebro reage antes mesmo de você pensar direito? "
                f"Pesquisas ligadas a {title.lower()} mostram como pequenos estímulos da rotina drenam sua atenção e energia logo cedo. "
                f"Ao ajustar dois hábitos simples nos primeiros vinte minutos do dia, você recupera o foco e rende muito mais. "
                f"Testa essa mudança amanhã mesmo e me conta nos comentários!"
            ),
            (
                f"A maioria das pessoas tenta resolver cansaço mental com mais cafeína, quando o ponto real está em {title.lower()}. "
                f"Quando o ambiente dispara micro-distrações o tempo todo, sua clareza cognitiva despenca sem você notar. "
                f"Criar blocos curtos de foco profundo devolve controle emocional e produtividade real. "
                f"Qual hábito mais rouba sua atenção hoje? Comenta aqui!"
            ),
        ]
    elif "anime" in horizon or "entretenimento" in horizon or "cultura" in horizon:
        variants = [
            (
                f"Pouca gente notou esse detalhe escondido, mas os fãs já estão debatendo {title.lower()} no mundo todo. "
                f"Se você olhar com atenção para a construção dessa cena, existe uma pista clara que conecta os eventos anteriores e muda o peso do próximo episódio. "
                f"É exatamente esse tipo de detalhe oculto que transforma uma cena comum na maior teoria da temporada. "
                f"Você também percebeu essa referência? Comenta sua teoria aqui embaixo!"
            ),
            (
                f"A comunidade inteira voltou a analisar {title.lower()} depois que um detalhe visual passou despercebido na primeira exibição. "
                f"Quando ligamos essa pista aos arcos antigos da obra, fica claro que o autor preparou essa virada há muito tempo. "
                f"Agora resta saber qual será o impacto imediato nos próximos capítulos. "
                f"Qual personagem vai surpreender mais daqui pra frente? Deixa seu palpite!"
            ),
        ]
    elif "ciencia" in horizon or "mundo" in horizon:
        variants = [
            (
                f"Olha o impacto real disso que acabou de chamar atenção em {title.lower()}. "
                f"Enquanto muita gente olha apenas para a manchete superficial, os dados mostram uma mudança importante nos bastidores que afeta tecnologia e economia. "
                f"Vale acompanhar de perto como esse cenário evolui a partir desta semana. "
                f"O que você acha dessa virada? Deixa sua opinião nos comentários!"
            ),
            (
                f"Os bastidores de {title.lower()} revelam uma transformação que pouca gente colocou no radar até agora. "
                f"Segundo os relatórios mais recentes, os desdobramentos práticos já começam a aparecer nos próximos meses. "
                f"Entender essa movimentação cedo ajuda a enxergar para onde o mundo está indo. "
                f"Qual é a sua leitura sobre esse cenário? Comenta aqui!"
            ),
        ]
    else:
        variants = [
            (
                f"Esse assunto está chamando atenção agora por um motivo bem direto: {title.lower()}, segundo destaque de {source}. "
                f"O ponto mais importante é como um detalhe que parecia pequeno muda completamente a leitura do cenário atual e o que vem pela frente. "
                f"E você, o que pensa sobre isso? Comenta sua visão aqui embaixo!"
            ),
            (
                f"Por trás do que {source} destacou sobre {title.lower()}, existe uma lição prática que vale observar de perto. "
                f"Quando o contexto completo aparece, fica fácil entender por que tanta gente está debatendo esse tema hoje. "
                f"Deixe sua opinião nos comentários e acompanhe os próximos vídeos!"
            ),
        ]

    body = variants[spoke_idx % len(variants)]
    clean_hook = hook.strip(" .!?:").capitalize()
    final_script = immunize_spoken_script(humanize_ptbr_script(f"{clean_hook}. {body}"), title=title)
    mahoraga.record_speech_turn(niche_key, spoke["id"], title, final_script)
    return final_script


