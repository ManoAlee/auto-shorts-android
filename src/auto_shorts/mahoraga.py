"""Mahoraga 8-Spoke Adaptive Intelligence Engine for auto-shorts-android.

Inspired by the Eight-Handled Sword Divergent Sila Divine General Mahoraga:
every failure, rejection, repetition, or quality drop turns the Wheel of Dharma,
diagnoses the phenomenon signature, applies an immediate counter-adaptation,
and permanently immunizes the pipeline in SQLite (`shorts_evolution.db`).
"""

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MAHORAGA_SPOKES: List[Dict[str, str]] = [
    {
        "id": "spoke_1_investigativo",
        "roman": "I",
        "name": "Revelação Investigativa",
        "cadence": "misterio_bastidores",
        "description": "Abre com o detalhe oculto nos bastidores, conecta as provas e fecha com pergunta analítica.",
    },
    {
        "id": "spoke_2_contrariano",
        "roman": "II",
        "name": "Quebra de Crença",
        "cadence": "choque_contrariano",
        "description": "Desafia o senso comum logo nos 3 primeiros segundos e mostra a realidade nos dados.",
    },
    {
        "id": "spoke_3_efeito_domino",
        "roman": "III",
        "name": "Efeito Dominó",
        "cadence": "causa_consequencia",
        "description": "Parte direto do fato gerador e rastreia a reação em cadeia na prática.",
    },
    {
        "id": "spoke_4_raio_x",
        "roman": "IV",
        "name": "Raio-X Técnico",
        "cadence": "direto_analitico",
        "description": "Zero rodeios: apresenta o problema central, disseca o mecanismo técnico e entrega a conclusão.",
    },
    {
        "id": "spoke_5_dilema",
        "roman": "V",
        "name": "Dilema Estratégico",
        "cadence": "debate_polarizado",
        "description": "Coloca duas visões opostas em choque sobre o tema e convoca o público a decidir.",
    },
    {
        "id": "spoke_6_cronica",
        "roman": "VI",
        "name": "Crônica de Impacto",
        "cadence": "storytelling_imersivo",
        "description": "Constrói uma cena viva em torno do ponto de virada e fecha em loop contínuo.",
    },
    {
        "id": "spoke_7_radar_futuro",
        "roman": "VII",
        "name": "Alerta de Tendência",
        "cadence": "previsao_acelerada",
        "description": "Mostra por que essa mudança está acelerando agora e o que muda nas próximas semanas.",
    },
    {
        "id": "spoke_8_anatomia",
        "roman": "VIII",
        "name": "Anatomia do Segredo",
        "cadence": "dissecacao_profunda",
        "description": "Isola a peça-chave que quase ninguém enxergou e prova por que ela muda o jogo.",
    },
]

ACTIVE_IMMUNITIES: List[Dict[str, str]] = [
    {
        "code": "IMMUNITY_SPEECH_8SPOKE",
        "title": "Rotação de Fala em 8 Raios (Anti-Repetição)",
        "detail": "Proíbe repetir o mesmo molde narrativo ou abertura entre vídeos seguidos e elimina eco título==resumo.",
    },
    {
        "code": "IMMUNITY_HOOK_WORD_BOUNDARY",
        "title": "Blindagem de Gancho Sem Corte de Palavra",
        "detail": "Nunca corta palavras ao meio ('SOBRE O S') nem para em verbo transitivo ('POR QUE ESCREVER SOFTWARE').",
    },
    {
        "code": "IMMUNITY_VISUAL_NICHE_SHIELD",
        "title": "Escudo Visual Multi-Cena por Nicho",
        "detail": "Bloqueia fundos de gameplay (Minecraft/Subway) fora do nicho gaming e exige B-roll cinematográfico multi-cena.",
    },
    {
        "code": "IMMUNITY_FFMPEG_3STAGE_HEAL",
        "title": "Auto-Cura FFmpeg em 3 Estágios (Exit 254)",
        "detail": "Diretórios de trabalho isolados por execução + fallback automático de filtros e re-corte direto da fonte.",
    },
    {
        "code": "IMMUNITY_TIKTOK_REWARDS_180S",
        "title": "Adaptação Dinâmica de Duração por Plataforma",
        "detail": "Reconhece clipes TikTok Creator Rewards (60s–180s) sem reprovar no limite de 60s do YouTube Shorts.",
    },
    {
        "code": "IMMUNITY_DEEP_ARTICLE_EXTRACTOR",
        "title": "Extração Profunda de Artigos (Anti-Manchete Vazia)",
        "detail": "Quando feeds como Hacker News trazem só o título, extrai parágrafos reais da URL ou gera análise técnica contextual.",
    },
]

_DANGLING_TOKENS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "e", "ou", "para", "por", "com", "sem", "sob", "sobre", "entre", "ate", "até",
    "que", "se", "mas", "como", "quando", "onde", "porque",
    "nao", "não", "mais", "menos", "muito", "muita", "todo", "toda",
    "ser", "estar", "ter", "haver", "ir", "vai", "foi", "era",
    "escrever", "criar", "fazer", "usar", "manter", "mudar", "evitar",
    "deixar", "ficar", "mostrar", "revelar", "entender", "descobrir", "ver",
}

_PLACEHOLDER_PATTERNS = (
    "4 words in caps",
    "words in caps",
    "in caps",
    "curious title",
    "short call",
    "hook title",
    "max 4 palavras",
    "gancho em ",
    "titulo curioso",
)


def clean_word_boundary_hook(raw: str, max_chars: int = 32, fallback: str = "DESTAQUE DO DIA") -> str:
    """Build a complete, self-contained uppercase hook that NEVER slices mid-word or ends on a dangling word."""
    text = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" .,:;!?-|\"'»«>")
    if not text or any(p in text.lower() for p in _PLACEHOLDER_PATTERNS):
        return fallback

    # If there is a sentence break inside the hook candidate ("HAROLD. MESMO TENTANDO"), keep the longest clean clause
    if "." in text or "!" in text or "?" in text:
        clauses = [c.strip(" ,:;-") for c in re.split(r"[.!?]+", text) if len(c.strip(" ,:;-")) >= 10]
        if clauses:
            text = clauses[0]

    # Strip conversational prefixes when headline overflows max_chars ("Por que escrever software correto é difícil" -> "SOFTWARE CORRETO É DIFÍCIL")
    if len(text) > max_chars:
        stripped = re.sub(
            r"^(?:entenda\s+por\s+que\s+|veja\s+por\s+que\s+|saiba\s+por\s+que\s+|"
            r"por\s+que\s+(?:escrever|criar|fazer|usar|manter|aprender|investir\s+em)\s+|"
            r"por\s+que\s+o\s+|por\s+que\s+a\s+|por\s+que\s+|"
            r"o\s+segredo\s+proibido\s+sobre\s+o\s+segredo\s+proibido\s+de\s+|"
            r"o\s+segredo\s+proibido\s+sobre\s+|"
            r"como\s+o\s+|como\s+a\s+|como\s+)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if len(stripped) >= 4:
            text = stripped

    words = text.split()
    chosen: List[str] = []
    for w in words:
        candidate = " ".join(chosen + [w])
        if len(candidate) > max_chars and len(chosen) >= 2:
            break
        chosen.append(w)
        if len(chosen) >= 6 and w.lower().strip(",.:;!?") not in _DANGLING_TOKENS:
            break

    # If the last chosen word is a dangling preposition/article/verb or a 1-letter fragment, either extend by 1 short word or pop it
    while len(chosen) >= 2:
        last_clean = chosen[-1].lower().strip(",.:;!?")
        if last_clean not in _DANGLING_TOKENS and len(last_clean) > 1:
            break
        next_idx = len(chosen)
        if next_idx < len(words):
            next_word = words[next_idx]
            extended = " ".join(chosen + [next_word])
            if len(extended) <= max_chars + 4 and next_word.lower().strip(",.:;!?") not in _DANGLING_TOKENS and len(next_word.strip(",.:;!?")) > 1:
                chosen.append(next_word)
                break
        chosen.pop()

    result = " ".join(chosen).strip(" .,:;!?-").upper()
    if not result or len(result) < 4:
        return fallback
    return result


def _word_set(sentence: str) -> set:
    return {
        w
        for w in re.findall(r"[a-záàâãéêíóôõúç0-9]{3,}", (sentence or "").lower())
        if w not in _DANGLING_TOKENS
    }


def sentence_similarity(a: str, b: str) -> float:
    sa, sb = _word_set(a), _word_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(min(len(sa), len(sb)))


def immunize_spoken_script(script: str, title: str = "", summary: str = "") -> str:
    """Remove duplicate sentences, title==summary echoes, and placeholder leaks from any spoken PT-BR script."""
    raw = re.sub(r"\s+", " ", str(script or "").strip())
    if not raw:
        return ""

    # Split into sentences preserving punctuation
    parts = re.split(r"(?<=[.!?])\s+", raw)
    kept: List[str] = []
    for part in parts:
        clean_p = part.strip()
        if not clean_p:
            continue
        low_p = clean_p.lower()
        if any(pat in low_p for pat in _PLACEHOLDER_PATTERNS):
            continue
        # Fix recursive title duplication like "O segredo proibido sobre O Segredo Proibido de..."
        clean_p = re.sub(
            r"(?i)\b(o\s+segredo\s+proibido\s+(?:sobre|de)\s+)\1+",
            r"\1",
            clean_p,
        )
        clean_p = re.sub(
            r"(?i)\b(o\s+segredo\s+proibido\s+sobre\s+)o\s+segredo\s+proibido\s+de\s+",
            "O segredo proibido de ",
            clean_p,
        )
        # Check if this sentence is a near-duplicate of any already kept sentence
        is_dup = False
        for prev in kept:
            if clean_p.lower().rstrip(".!?") == prev.lower().rstrip(".!?"):
                is_dup = True
                break
            if len(_word_set(clean_p)) >= 4 and sentence_similarity(clean_p, prev) >= 0.78:
                is_dup = True
                break
        if not is_dup:
            kept.append(clean_p)

    return " ".join(kept).strip()


class MahoragaEngine:
    """SQLite-backed 8-Spoke Adaptive Intelligence & Self-Healing Engine."""

    def __init__(self, db_path: str | Path = Path("output") / "shorts_evolution.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mahoraga_adaptations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    phenomenon TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    spoke_id TEXT NOT NULL,
                    trigger_detail TEXT NOT NULL,
                    counter_action TEXT NOT NULL,
                    resolved INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mahoraga_speech_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    niche TEXT NOT NULL,
                    spoke_id TEXT NOT NULL,
                    topic_hash TEXT NOT NULL,
                    opening_sig TEXT NOT NULL,
                    reward REAL DEFAULT 0.85
                )
                """
            )

    def select_adaptive_spoke(self, niche: str, topic_title: str = "") -> Tuple[int, Dict[str, str]]:
        """Turn the 8-Spoke Wheel so consecutive videos NEVER use the same narrative formula."""
        clean_niche = (niche or "geral").strip().lower()
        with self._connect() as conn:
            recent_rows = conn.execute(
                "SELECT spoke_id FROM mahoraga_speech_ledger ORDER BY id DESC LIMIT 4"
            ).fetchall()
            niche_rows = conn.execute(
                "SELECT spoke_id FROM mahoraga_speech_ledger WHERE niche = ? ORDER BY id DESC LIMIT 3",
                (clean_niche,),
            ).fetchall()

        forbidden = {str(r["spoke_id"]) for r in recent_rows} | {str(r["spoke_id"]) for r in niche_rows}
        available = [
            (idx, sp)
            for idx, sp in enumerate(MAHORAGA_SPOKES)
            if sp["id"] not in forbidden
        ]
        if not available:
            available = list(enumerate(MAHORAGA_SPOKES))

        seed_str = f"{clean_niche}:{topic_title}:{len(recent_rows)}"
        pick_pos = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:6], 16) % len(available)
        spoke_idx, spoke = available[pick_pos]
        return spoke_idx, spoke

    def record_speech_turn(self, niche: str, spoke_id: str, topic_title: str, script: str, reward: float = 0.9) -> None:
        """Record the chosen Spoke and opening signature so the Wheel rotates on the next generation."""
        clean_niche = (niche or "geral").strip().lower()
        topic_hash = hashlib.md5((topic_title or "").lower().encode("utf-8")).hexdigest()[:12]
        words = re.findall(r"[a-záàâãéêíóôõúç0-9]+", (script or "").lower())
        opening_sig = " ".join(words[:7])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mahoraga_speech_ledger (niche, spoke_id, topic_hash, opening_sig, reward)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_niche, spoke_id, topic_hash, opening_sig, float(reward)),
            )

    def adapt_to_phenomenon(
        self,
        phenomenon: str,
        niche: str,
        trigger_detail: str,
        counter_action: str,
        spoke_id: str = "spoke_4_raio_x",
        resolved: bool = True,
    ) -> Dict[str, Any]:
        """Log a failure/degradation phenomenon and register the counter-adaptation turn."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mahoraga_adaptations (phenomenon, niche, spoke_id, trigger_detail, counter_action, resolved)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(phenomenon)[:80],
                    str(niche or "geral")[:40],
                    str(spoke_id)[:40],
                    str(trigger_detail)[:280],
                    str(counter_action)[:280],
                    1 if resolved else 0,
                ),
            )
            total_turns = conn.execute("SELECT COUNT(*) AS c FROM mahoraga_adaptations").fetchone()["c"]
        return {
            "phenomenon": phenomenon,
            "counter_action": counter_action,
            "wheel_turns": int(total_turns),
            "resolved": resolved,
        }

    def compose_news_narrative(
        self,
        pt_title: str,
        pt_summary: str,
        source_name: str,
        category: str = "mundo",
    ) -> Tuple[str, Dict[str, str]]:
        """Compose a journalistic PT-BR script using the next unrepeated Spoke of the 8-Spoke Wheel."""
        spoke_idx, spoke = self.select_adaptive_spoke(f"news_{category}", pt_title)
        title_clean = pt_title.strip().rstrip(".!?")
        sum_clean = pt_summary.strip()
        if sum_clean and not sum_clean.endswith((".", "!", "?")):
            sum_clean += "."
        sum_lower_start = sum_clean[0].lower() + sum_clean[1:] if len(sum_clean) > 1 else sum_clean

        templates = [
            # Spoke I: Revelação Investigativa
            (
                f"Por trás do destaque sobre {title_clean}, existe um detalhe técnico que muda toda a leitura. "
                f"Segundo os dados apurados por {source_name}, {sum_lower_start} "
                f"Quem enxerga esse movimento nos bastidores entende por que o setor entrou em alerta. "
                f"Qual é a sua análise sobre isso? Deixe nos comentários!"
            ),
            # Spoke II: Quebra de Crença
            (
                f"{title_clean}! "
                f"Muita gente subestima esse ponto, mas a apuração de {source_name} mostra que {sum_lower_start} "
                f"Na prática, isso derruba o padrão antigo e exige uma postura totalmente nova a partir de agora. "
                f"Você concorda com essa visão? Comente aqui embaixo!"
            ),
            # Spoke III: Efeito Dominó
            (
                f"Olha o efeito dominó que acabou de começar: {title_clean}. "
                f"{sum_clean} "
                f"Esse levantamento de {source_name} explica por que a decisão já impacta diretamente o mercado e a tecnologia. "
                f"Como você vê esse cenário? Comente e siga o canal!"
            ),
            # Spoke IV: Raio-X Técnico
            (
                f"{title_clean}. "
                f"De acordo com {source_name}, {sum_lower_start} "
                f"O ponto central aqui é simples: quem domina o fundamento resolve na raiz o que a maioria tenta remendar depois. "
                f"Deixe sua opinião nos comentários!"
            ),
            # Spoke V: Dilema Estratégico
            (
                f"Esse tema dividiu opiniões lá fora: {title_clean}. "
                f"Enquanto parte do mercado aposta na velocidade, o destaque de {source_name} lembra que {sum_lower_start} "
                f"No fim das contas, a escolha entre atalho e precisão define quem sobrevive no longo prazo. "
                f"De que lado você fica? Comente aqui!"
            ),
            # Spoke VI: Crônica de Impacto
            (
                f"Imagine construir um sistema inteiro e descobrir que o maior risco estava invisível: {title_clean}. "
                f"{sum_clean} "
                f"A análise publicada via {source_name} resume exatamente o desafio real de quem atua na linha de frente. "
                f"Compartilhe sua experiência nos comentários!"
            ),
            # Spoke VII: Alerta de Tendência
            (
                f"Um sinal claro do que vem pela frente ganhou força em {source_name}: {title_clean}. "
                f"{sum_clean} "
                f"Essa virada antecipa uma mudança estrutural que vai pautar as próximas semanas. "
                f"Siga o canal para acompanhar cada desdobramento!"
            ),
            # Spoke VIII: Anatomia do Segredo
            (
                f"A peça-chave para entender {title_clean} quase nunca aparece na superfície. "
                f"Como aponta {source_name}, {sum_lower_start} "
                f"É exatamente esse detalhe que separa um resultado mediano de uma execução impecável. "
                f"O que você achou dessa análise? Comente aqui embaixo!"
            ),
        ]
        chosen_raw = templates[spoke_idx % len(templates)]
        final_script = immunize_spoken_script(chosen_raw, title=title_clean, summary=sum_clean)
        self.record_speech_turn(f"news_{category}", spoke["id"], title_clean, final_script)
        return final_script, spoke

    def get_status_summary(self) -> Dict[str, Any]:
        """Return live Mahoraga telemetry, wheel rotation count, active spoke, and immunities."""
        with self._connect() as conn:
            adapt_count = int(conn.execute("SELECT COUNT(*) AS c FROM mahoraga_adaptations").fetchone()["c"])
            speech_count = int(conn.execute("SELECT COUNT(*) AS c FROM mahoraga_speech_ledger").fetchone()["c"])
            last_speech = conn.execute(
                "SELECT spoke_id, niche, opening_sig, created_at FROM mahoraga_speech_ledger ORDER BY id DESC LIMIT 1"
            ).fetchone()
            recent_adapts = conn.execute(
                "SELECT phenomenon, niche, spoke_id, trigger_detail, counter_action, created_at "
                "FROM mahoraga_adaptations ORDER BY id DESC LIMIT 6"
            ).fetchall()

        total_turns = adapt_count + speech_count
        active_spoke = MAHORAGA_SPOKES[total_turns % len(MAHORAGA_SPOKES)]
        if last_speech:
            for sp in MAHORAGA_SPOKES:
                if sp["id"] == last_speech["spoke_id"]:
                    active_spoke = sp
                    break

        return {
            "mode": "MAHORAGA_8_SPOKE_ACTIVE",
            "wheel_turns": total_turns,
            "adaptation_events": adapt_count,
            "speech_rotations": speech_count,
            "active_spoke": active_spoke,
            "immunities_count": len(ACTIVE_IMMUNITIES),
            "immunities": ACTIVE_IMMUNITIES,
            "recent_adaptations": [dict(r) for r in recent_adapts],
        }

