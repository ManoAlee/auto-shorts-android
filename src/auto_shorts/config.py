"""Configuration presets for platforms, Brazilian niches, and FFmpeg tuning."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


def load_dotenv_file(env_path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from .env without external dependencies."""
    p = Path(env_path)
    if not p.is_file():
        return
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class PlatformPreset:
    name: str
    min_duration: int
    max_duration: int
    sweet_spot: str
    aspect_ratio: str = "9:16"


@dataclass(frozen=True)
class NicheProfile:
    key: str
    label: str
    hook_keywords: List[str]
    cta_suggestion: str


PLATFORMS: Dict[str, PlatformPreset] = {
    "tiktok_rewards": PlatformPreset(
        name="tiktok_rewards",
        min_duration=62,
        max_duration=95,
        sweet_spot="62-90s (obrigatorio >= 60s para Creator Rewards)",
    ),
    "youtube_shorts": PlatformPreset(
        name="youtube_shorts",
        min_duration=30,
        max_duration=58,
        sweet_spot="35-55s (maxima retencao abaixo de 60s)",
    ),
    "instagram_reels": PlatformPreset(
        name="instagram_reels",
        min_duration=25,
        max_duration=58,
        sweet_spot="30-50s (foco em salvamentos e compartilhamentos)",
    ),
}

NICHES: Dict[str, NicheProfile] = {
    "financas": NicheProfile(
        key="financas",
        label="Financas, Investimentos e Renda Extra",
        hook_keywords=[
            "dinheiro", "juros", "divida", "investir", "banco", "cartao",
            "salario", "renda", "cripto", "bitcoin", "pix", "lucro", "erro", "segredo",
        ],
        cta_suggestion="Qual sua opiniao sobre essa visao financeira? Comenta aqui e se inscreve!",
    ),
    "ia_tech": NicheProfile(
        key="ia_tech",
        label="IA, Tecnologia e SaaS",
        hook_keywords=[
            "ia", "inteligencia artificial", "ferramenta", "gratis", "automatizar",
            "prompt", "site", "app", "codigo", "celular", "claude", "gemini", "chatgpt",
        ],
        cta_suggestion="Voce testaria essa tecnologia no dia a dia? Comenta aqui e siga o canal!",
    ),
    "desenvolvimento_pessoal": NicheProfile(
        key="desenvolvimento_pessoal",
        label="Desenvolvimento Pessoal e Mentalidade",
        hook_keywords=[
            "habito", "disciplina", "foco", "mente", "sucesso", "fracasso",
            "tempo", "ansiedade", "medo", "mudar", "regra", "verdade", "ninguem",
        ],
        cta_suggestion="Salva esse corte para lembrar dessa licao e compartilha com quem precisa!",
    ),
    "saude_fitness": NicheProfile(
        key="saude_fitness",
        label="Saude, Fitness e Emagrecimento",
        hook_keywords=[
            "treino", "dieta", "proteina", "creatina", "sono", "emagrecer",
            "acucar", "metabolismo", "musculo", "saude", "medico", "alimento",
        ],
        cta_suggestion="Voce ja aplica esse habito na sua rotina? Conta nos comentarios!",
    ),
    "concursos": NicheProfile(
        key="concursos",
        label="Carreira, Concursos e Educacao",
        hook_keywords=[
            "prova", "edital", "concurso", "estudar", "aprovado", "vaga",
            "ingles", "carreira", "entrevista", "curriculo", "metodo", "nota",
        ],
        cta_suggestion="Salva esse resumo para revisar depois e comente qual seu objetivo!",
    ),
    "entretenimento_animes": NicheProfile(
        key="entretenimento_animes",
        label="Entretenimento, Animes, Mangas e Teorias",
        hook_keywords=[
            "anime", "manga", "teoria", "capitulo", "episodio", "spoiler",
            "poder", "vilao", "protagonista", "segredo", "final", "arco",
            "batalha", "canon", "autor", "obra", "referencia", "easter egg",
        ],
        cta_suggestion="Qual a sua teoria sobre essa cena? Deixe nos comentarios e se inscreva!",
    ),
    "podcast": NicheProfile(
        key="podcast",
        label="Cortes de Podcast, Entrevistas e Debates",
        hook_keywords=[
            "podcast", "historia", "aconteceu", "verdade", "segredo", "polemica",
            "dinheiro", "carreira", "entrevista", "revelou", "chocado", "nunca",
        ],
        cta_suggestion="Episodio original creditado acima! Se inscreva para mais cortes de podcast.",
    ),
    "noticias_mundiais": NicheProfile(
        key="noticias_mundiais",
        label="Noticias Mundiais e Jornais Internacionais no Brasil",
        hook_keywords=[
            "mundo", "urgente", "internacional", "eua", "europa", "china",
            "economia", "ia", "ciencia", "mercado", "brasil", "anuncio",
        ],
        cta_suggestion="Fonte jornalistica internacional creditada acima — siga para atualizacoes globais!",
    ),
    "geral": NicheProfile(
        key="geral",
        label="Curiosidades, Cortes e Storytelling",
        hook_keywords=[
            "segredo", "nunca", "verdade", "chocante", "historia", "aconteceu",
            "ninguem", "cuidado", "descobri", "porque", "motivo", "pior", "melhor",
        ],
        cta_suggestion="Comenta o que voce achou e se inscreva para os proximos videos!",
    ),
}

NICHE_BADGES: Dict[str, str] = {
    "financas": "FINANCAS",
    "ia_tech": "IA & TECH",
    "desenvolvimento_pessoal": "MENTALIDADE",
    "saude_fitness": "SAUDE",
    "concursos": "CONCURSOS",
    "entretenimento_animes": "ANIMES",
    "podcast": "PODCAST",
    "noticias_mundiais": "MUNDO HOJE",
    "geral": "DESTAQUE",
}


def get_niche_badge(niche: str) -> str:
    """Return a clean uppercase thumbnail badge that never clips mid-word."""
    key = str(niche or "geral").strip().lower()
    if key in NICHE_BADGES:
        return NICHE_BADGES[key]
    return key.replace("_", " ").upper()[:14] or "SHORTS"

# Extracted from openshorts/ffmpeg_utils.py: strips source handler tags (e.g. Google Inc.)
METADATA_SCRUB: List[str] = [
    "-map_metadata", "-1",
    "-map_chapters", "-1",
    "-map_metadata:s:v", "-1",
    "-map_metadata:s:a", "-1",
]

# Calibrated to TikTok / Shorts / Reels -14 LUFS target with -2.0 dBTP headroom for AAC.
LOUDNORM_FILTER = "loudnorm=I=-14:TP=-2.0:LRA=11"

QUALITY_PRESETS: Dict[str, Dict[str, str]] = {
    "mobile": {"width": "720", "height": "1280", "preset": "veryfast", "crf": "23"},
    "high": {"width": "1080", "height": "1920", "preset": "fast", "crf": "19"},
}
