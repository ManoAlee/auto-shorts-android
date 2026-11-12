"""Story, Director & Retention Engine for Next-Gen Cinema in AutoShorts Android.

Operates 100% locally on Android/Termux ARM64 with zero mandatory dependencies.
Integrates with local llama-server (GGUF), offline rule-based heuristics, and
optional cloud LLMs (Gemini, OpenRouter) to produce validated, structured cinematic
scripts with multi-character continuity, shot direction, and 9:16 retention engineering.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

from .mahoraga import MahoragaEngine, immunize_spoken_script
from .offline_llm import detect_android_llm_capabilities, strip_reasoning_tags


# ==============================================================================
# ENUMS & CONSTANTS
# ==============================================================================

SHOT_TYPES = ("EXTREME_CLOSE_UP", "CLOSE_UP", "MEDIUM_SHOT", "WIDE_SHOT", "DUTCH_ANGLE", "POV")
CAMERA_MOVEMENTS = ("STATIC_FOCUS", "SLOW_ZOOM_IN", "PAN_RIGHT_TO_LEFT", "TILT_UP", "SHAKE_IMPACT", "WHIP_PAN")
LIGHTING_MOODS = ("DRAMATIC_NEON", "GOLDEN_HOUR", "HIGH_CONTRAST_SHADOW", "NOIR_DIM", "FLASH_LIGHTNING", "CYBER_GLOW")
VFX_CUES = ("NONE", "IMPACT_LINES", "SCREEN_SHAKE", "COLOR_INVERT", "FLASH", "PARTICLES_GLOW", "VIGNETTE_PULSE")
AUDIO_SFX_CUES = ("NONE", "WHOOSH", "SUB_BOOM", "HEARTBEAT", "SWORD_CLASH", "GLITCH", "TENSION_RISER", "THUNDER")

STORY_GENRES = {
    "financas_negocios": "Finanças, economia real, investimentos, armadilhas de mercado e estudos de caso de negócios de alto impacto.",
    "ia_futuro_tech": "Inteligência artificial, tecnologia de ponta, automação, ciência aplicada e revolução digital.",
    "podcast_debates": "Bastidores reais, debates quentes, viradas de carreira e histórias de impacto no estilo podcast brasileiro.",
    "psicologia_mentalismo": "Psicologia comportamental, neurociência prática, viés cognitivo, linguagem corporal e mistérios da mente.",
    "saude_biohacking": "Saúde baseada em evidências, sono, dopamina, longevidade, neurociência e alta performance física.",
    "jornalismo_global": "Notícias globais e Brasil hoje, geopolítica, economia internacional e descobertas científicas.",
    "dark_shonen": "Cultura pop, cinema, games, ação sobrenatural épica, batalhas táticas e reviravoltas no estilo anime moderno.",
    "cyberpunk_br": "Ficção científica urbana no Brasil de 2077, megacorporações, inteligência artificial rebelde e submundo hacker.",
    "misterio_investigativo": "Suspense noir, crimes inexplicáveis, pistas microscópicas, deduções lógicas e revelações chocantes.",
    "curiosidades_cosmicas": "Exploração espacial, paradoxos temporais, buracos negros, civilizações alienígenas e fronteiras da física.",
    "terror_psicologico": "Horror analógico, lendas urbanas reimaginadas, quebra da quarta parede e tensão psicológica crescente.",
}

GENRE_TO_NICHE_MAP = {
    "financas_negocios": "financas",
    "ia_futuro_tech": "ia_tech",
    "podcast_debates": "podcast",
    "psicologia_mentalismo": "desenvolvimento_pessoal",
    "saude_biohacking": "saude_fitness",
    "jornalismo_global": "noticias_mundiais",
    "curiosidades_cosmicas": "noticias_mundiais",
    "misterio_investigativo": "desenvolvimento_pessoal",
    "terror_psicologico": "desenvolvimento_pessoal",
    "cyberpunk_br": "ia_tech",
    "dark_shonen": "entretenimento_animes",
}

GENRE_TO_VOICE_STYLE_MAP = {
    "financas_negocios": "authority",
    "ia_futuro_tech": "kokoro_alex",
    "podcast_debates": "narrador_pro",
    "psicologia_mentalismo": "storyteller",
    "saude_biohacking": "podcast_female",
    "jornalismo_global": "narrador_pro",
    "curiosidades_cosmicas": "narrador_pro",
    "misterio_investigativo": "storyteller",
    "terror_psicologico": "storyteller",
    "cyberpunk_br": "kokoro_alex",
    "dark_shonen": "dublador_anime",
}


def detect_universal_genre_and_niche(prompt: str, requested_genre: str = "") -> Tuple[str, str, str]:
    """Infer the best universal genre, niche, and studio voice profile from any topic prompt."""
    p_low = f" {(prompt or '').lower()} "
    req = (requested_genre or "").strip().lower()
    if req in STORY_GENRES and req != "dark_shonen":
        niche = GENRE_TO_NICHE_MAP.get(req, "geral")
        vstyle = GENRE_TO_VOICE_STYLE_MAP.get(req, "narrador_pro")
        return req, niche, vstyle

    if any(k in p_low for k in ("selic", "juros", "investimento", "dinheiro", "salário", "salario", "inflação", "inflacao", "bitcoin", "cripto", "mercado", "ações", "acoes", "renda", "imposto", "pib", "banco")):
        return "financas_negocios", "financas", "authority"
    if any(k in p_low for k in ("ia ", "inteligência artificial", "inteligencia artificial", "chatgpt", "openai", "deepseek", "algoritmo", "chip", "nvidia", "robô", "robo", "programação", "software", "celular", "tecnologia")):
        return "ia_futuro_tech", "ia_tech", "kokoro_alex"
    if any(k in p_low for k in ("dopamina", "sono", "cérebro", "cerebro", "ansiedade", "hábito", "habito", "psicologia", "mente", "foco", "comportamento", "manipulação")):
        return "psicologia_mentalismo", "desenvolvimento_pessoal", "storyteller"
    if any(k in p_low for k in ("treino", "músculo", "musculo", "saúde", "saude", "longevidade", "metabolismo", "energia", "dieta", "exercício", "exercicio", "médico", "medico")):
        return "saude_biohacking", "saude_fitness", "podcast_female"
    if any(k in p_low for k in ("podcast", "flow", "podpah", "entrevista", "debate", "polêmica", "polemica", "bastidores", "carreira")):
        return "podcast_debates", "podcast", "narrador_pro"
    if any(k in p_low for k in ("nasa", "espaço", "espaco", "universo", "buraco negro", "planeta", "ciência", "ciencia", "geopolítica", "governo", "mundo", "notícia", "noticia", "guerra", "clima")):
        return "jornalismo_global", "noticias_mundiais", "narrador_pro"
    if any(k in p_low for k in ("anime", "mangá", "manga", "one piece", "jujutsu", "naruto", "luffy", "zoro", "brook", "imu", "solo leveling", "dragon ball", "episódio", "episodio")):
        return "dark_shonen", "entretenimento_animes", "dublador_anime"

    final_genre = req if req in STORY_GENRES else "podcast_debates"
    return (
        final_genre,
        GENRE_TO_NICHE_MAP.get(final_genre, "podcast"),
        GENRE_TO_VOICE_STYLE_MAP.get(final_genre, "narrador_pro"),
    )


# ==============================================================================
# DATA MODELS (CINEMATIC SCRIPT SCHEMA)
# ==============================================================================

@dataclass
class CameraDirection:
    shot_type: str = "MEDIUM_SHOT"
    movement: str = "SLOW_ZOOM_IN"
    lighting: str = "DRAMATIC_NEON"
    focus_target: str = "FACE_CENTER"
    duration_sec: float = 3.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CinematicScene:
    scene_id: int
    act: str  # HOOK, SETUP, ESCALATION, TWIST, CLIMAX, LOOP_OUTRO
    speaker: str  # NARRATOR, PROTAGONIST, ANTAGONIST, WITNESS
    voice_profile: str  # pm_alex, pf_dora, pm_santa, etc.
    dialogue: str
    visual_description: str
    camera: CameraDirection = field(default_factory=CameraDirection)
    vfx: str = "NONE"
    sfx: str = "NONE"
    manga_panel_mode: str = "READING_RTL"  # READING_RTL, FULL_BLEED, DIAGONAL_SPLIT
    estimated_duration_sec: float = 4.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["camera"] = self.camera.to_dict()
        return d


@dataclass
class CharacterProfile:
    char_id: str
    name: str
    role: str  # PROTAGONIST, ANTAGONIST, MENTOR, RIVAL, WITNESS
    archetype: str
    visual_traits: str
    costume: str
    voice_key: str
    status: str = "ACTIVE"
    first_appearance_ep: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CinematicScript:
    story_id: str
    title: str
    genre: str
    season: int
    episode: int
    hook_sentence: str
    loop_sentence: str
    target_duration_sec: float
    characters: List[CharacterProfile]
    scenes: List[CinematicScene]
    retention_score: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "story_id": self.story_id,
            "title": self.title,
            "genre": self.genre,
            "season": self.season,
            "episode": self.episode,
            "hook_sentence": self.hook_sentence,
            "loop_sentence": self.loop_sentence,
            "target_duration_sec": self.target_duration_sec,
            "characters": [c.to_dict() for c in self.characters],
            "scenes": [s.to_dict() for s in self.scenes],
            "retention_score": self.retention_score,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ==============================================================================
# CONTINUITY STORE (SQLITE EMBEDDED)
# ==============================================================================

class NarrativeContinuityStore:
    """Manages persistent character profiles, story arcs, and cross-episode memory in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path.home() / "auto-shorts-android" / "output" / "narrative_continuity.db")
        self.is_memory = str(self.db_path) == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.is_memory:
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self.is_memory and self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stories (
                    story_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    genre TEXT NOT NULL,
                    synopsis TEXT,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS characters (
                    char_id TEXT NOT NULL,
                    story_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    archetype TEXT,
                    visual_traits TEXT,
                    costume TEXT,
                    voice_key TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    first_appearance_ep INTEGER DEFAULT 1,
                    PRIMARY KEY (char_id, story_id),
                    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    story_id TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    hook_sentence TEXT,
                    loop_sentence TEXT,
                    duration_sec REAL,
                    script_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (story_id, season, episode),
                    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE
                );
            """)

    def register_story(self, story_id: str, title: str, genre: str, synopsis: str = "") -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO stories (story_id, title, genre, synopsis, created_at) VALUES (?, ?, ?, ?, ?)",
                (story_id, title, genre, synopsis, time.time()),
            )

    def save_character(self, story_id: str, char: CharacterProfile) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO characters
                   (char_id, story_id, name, role, archetype, visual_traits, costume, voice_key, status, first_appearance_ep)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (char.char_id, story_id, char.name, char.role, char.archetype, char.visual_traits,
                 char.costume, char.voice_key, char.status, char.first_appearance_ep),
            )

    def list_characters(self, story_id: str) -> List[CharacterProfile]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM characters WHERE story_id = ? ORDER BY first_appearance_ep ASC", (story_id,))
            return [
                CharacterProfile(
                    char_id=row["char_id"],
                    name=row["name"],
                    role=row["role"],
                    archetype=row["archetype"] or "",
                    visual_traits=row["visual_traits"] or "",
                    costume=row["costume"] or "",
                    voice_key=row["voice_key"] or "pm_alex",
                    status=row["status"] or "ACTIVE",
                    first_appearance_ep=row["first_appearance_ep"] or 1,
                )
                for row in cur.fetchall()
            ]

    def record_episode(self, script: CinematicScript) -> None:
        self.register_story(script.story_id, script.title, script.genre)
        for char in script.characters:
            self.save_character(script.story_id, char)
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO episodes
                   (story_id, season, episode, title, hook_sentence, loop_sentence, duration_sec, script_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    script.story_id,
                    script.season,
                    script.episode,
                    script.title,
                    script.hook_sentence,
                    script.loop_sentence,
                    script.target_duration_sec,
                    script.to_json(),
                    script.created_at,
                ),
            )

    def get_latest_episode_number(self, story_id: str, season: int = 1) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT MAX(episode) as max_ep FROM episodes WHERE story_id = ? AND season = ?",
                (story_id, season),
            )
            row = cur.fetchone()
            return int(row["max_ep"] or 0) if row else 0


# ==============================================================================
# RETENTION ENGINE (PSYCHOMETRIC HOOK & PACING SCORER)
# ==============================================================================

class RetentionEngine:
    """Evaluates and guarantees viral short retention patterns: 3-second hook, curiosity gaps, pacing and seamless loop."""

    # Trigger words that provoke immediate neuro-curiosity in Brazilian Portuguese
    NEURO_HOOK_TRIGGERS = [
        "segredo", "ninguém percebeu", "revelou", "proibido", "verdade oculta",
        "nunca te contaram", "o erro fatal", "isso muda tudo", "descobriram",
        "o maior mistério", "você não vai acreditar", "aconteceu de verdade"
    ]

    @classmethod
    def evaluate_script_retention(cls, script: CinematicScript) -> Dict[str, Any]:
        hook = (script.hook_sentence or "").strip().lower()
        scenes = script.scenes

        # 1. 0-3s Hook Score (0-100)
        hook_triggers_found = [tr for tr in cls.NEURO_HOOK_TRIGGERS if tr in hook]
        hook_word_count = len(re.findall(r"\w+", hook))
        # Ideal hook has 6 to 16 punchy words
        hook_length_score = 100 if 6 <= hook_word_count <= 16 else max(40, 100 - abs(hook_word_count - 11) * 6)
        hook_curiosity_score = min(100, len(hook_triggers_found) * 40 + 35)
        hook_score = int(0.6 * hook_curiosity_score + 0.4 * hook_length_score)

        # 2. Pacing Rhythm Score (Target: cuts every 2.5s - 4.5s)
        durations = [s.estimated_duration_sec for s in scenes]
        total_dur = sum(durations) if durations else 40.0
        avg_cut_dur = total_dur / max(1, len(scenes))
        if 2.2 <= avg_cut_dur <= 4.2:
            pacing_score = 95
        elif avg_cut_dur < 2.0:
            pacing_score = 75  # Too frantic
        else:
            pacing_score = max(40, int(95 - (avg_cut_dur - 4.2) * 15))  # Too stagnant

        # 3. Dynamic Visual Variety (Camera movement & Shot types)
        shot_types_used = set(s.camera.shot_type for s in scenes)
        moves_used = set(s.camera.movement for s in scenes)
        vfx_used = sum(1 for s in scenes if s.vfx != "NONE")
        variety_score = min(100, len(shot_types_used) * 20 + len(moves_used) * 15 + vfx_used * 10)

        # 4. Infinite Loop Connection
        loop = (script.loop_sentence or "").strip().lower()
        loop_score = 85 if len(loop) > 5 else 40
        # If last word of loop links to first word of hook
        hook_tokens = re.findall(r"\w+", hook)
        loop_tokens = re.findall(r"\w+", loop)
        if hook_tokens and loop_tokens:
            if hook_tokens[0] in loop_tokens[-3:]:
                loop_score = 100

        # Weighted Overall Retention Potential (0-100)
        overall_retention = int(
            0.35 * hook_score + 0.30 * pacing_score + 0.20 * variety_score + 0.15 * loop_score
        )

        decision = "APPROVED_VIRAL" if overall_retention >= 75 else "NEEDS_OPTIMIZATION"

        return {
            "overall_retention_score": overall_retention,
            "decision": decision,
            "hook_power_score": hook_score,
            "hook_triggers": hook_triggers_found,
            "avg_cut_duration_sec": round(avg_cut_dur, 2),
            "pacing_score": pacing_score,
            "visual_variety_score": variety_score,
            "loop_score": loop_score,
            "recommendation": (
                "Roteiro dinâmico e hipnótico calibrado para alta retenção (>80% VTR)."
                if overall_retention >= 75
                else "Aumente o impacto do gancho inicial nos primeiros 3 segundos."
            ),
        }


# ==============================================================================
# DIRECTOR ENGINE (CINEMATOGRAPHIC SHOT PLANNER)
# ==============================================================================

class DirectorEngine:
    """Plans framing, camera angles, lighting, depth, and pacing for vertical 9:16 storytelling."""

    ACT_DIRECTOR_TEMPLATES = {
        "HOOK": {
            "shot_type": "CLOSE_UP",
            "movement": "SLOW_ZOOM_IN",
            "lighting": "DRAMATIC_NEON",
            "vfx": "IMPACT_LINES",
            "sfx": "WHOOSH",
            "duration": 3.2,
        },
        "SETUP": {
            "shot_type": "WIDE_SHOT",
            "movement": "PAN_RIGHT_TO_LEFT",
            "lighting": "CYBER_GLOW",
            "vfx": "NONE",
            "sfx": "NONE",
            "duration": 4.5,
        },
        "ESCALATION": {
            "shot_type": "MEDIUM_SHOT",
            "movement": "SLOW_ZOOM_IN",
            "lighting": "HIGH_CONTRAST_SHADOW",
            "vfx": "VIGNETTE_PULSE",
            "sfx": "TENSION_RISER",
            "duration": 3.8,
        },
        "TWIST": {
            "shot_type": "DUTCH_ANGLE",
            "movement": "WHIP_PAN",
            "lighting": "FLASH_LIGHTNING",
            "vfx": "COLOR_INVERT",
            "sfx": "GLITCH",
            "duration": 3.0,
        },
        "CLIMAX": {
            "shot_type": "EXTREME_CLOSE_UP",
            "movement": "SHAKE_IMPACT",
            "lighting": "HIGH_CONTRAST_SHADOW",
            "vfx": "SCREEN_SHAKE",
            "sfx": "SUB_BOOM",
            "duration": 4.0,
        },
        "LOOP_OUTRO": {
            "shot_type": "CLOSE_UP",
            "movement": "SLOW_ZOOM_IN",
            "lighting": "DRAMATIC_NEON",
            "vfx": "NONE",
            "sfx": "HEARTBEAT",
            "duration": 3.5,
        },
    }

    @classmethod
    def apply_cinematic_direction(
        cls,
        act: str,
        dialogue: str,
        speaker: str = "NARRATOR",
        custom_shot: Optional[str] = None,
        custom_move: Optional[str] = None,
    ) -> CameraDirection:
        cfg = cls.ACT_DIRECTOR_TEMPLATES.get(act, cls.ACT_DIRECTOR_TEMPLATES["ESCALATION"])
        shot = custom_shot if (custom_shot in SHOT_TYPES) else cfg["shot_type"]
        move = custom_move if (custom_move in CAMERA_MOVEMENTS) else cfg["movement"]
        
        # Word count calculation for realistic duration (PT-BR: ~130 words per minute / ~2.1 words per second)
        word_count = len(re.findall(r"\w+", dialogue or ""))
        calc_dur = max(2.5, min(7.5, word_count / 2.2))

        return CameraDirection(
            shot_type=shot,
            movement=move,
            lighting=cfg["lighting"],
            focus_target="FACE_CENTER" if shot in ("CLOSE_UP", "EXTREME_CLOSE_UP") else "CENTER_STAGE",
            duration_sec=round(calc_dur, 2),
        )


# ==============================================================================
# STORY ENGINE (ORIGINAL NARRATIVES, ARCS & SCRIPT GENERATION)
# ==============================================================================

class StoryEngine:
    """Master AI Storyteller: Generates original serialized stories, characters, and JSON scripts."""

    def __init__(self, continuity_store: Optional[NarrativeContinuityStore] = None):
        self.continuity = continuity_store or NarrativeContinuityStore()

    def generate_story_script(
        self,
        prompt: str,
        genre: str = "dark_shonen",
        season: int = 1,
        episode: Optional[int] = None,
        target_duration_sec: float = 45.0,
        llama_url: str = "http://127.0.0.1:8080",
        use_local_llm: bool = True,
    ) -> CinematicScript:
        """Create a complete cinematic episode script using local GGUF llama-server, cloud LLM, or deterministic fallback."""
        story_id = f"story_{hashlib.md5(prompt.encode('utf-8')).hexdigest()[:8]}"
        ep_num = episode or (self.continuity.get_latest_episode_number(story_id, season=season) + 1)

        # 1. Check existing characters or create new ones
        existing_chars = self.continuity.list_characters(story_id)
        if not existing_chars:
            chars = self._create_cast_for_genre(genre, story_id)
        else:
            chars = existing_chars

        # 2. Try LLM Generation (Local GGUF or Cloud) when not in unit test mode
        raw_script_data = None
        if use_local_llm and "PYTEST_CURRENT_TEST" not in os.environ:
            caps = detect_android_llm_capabilities(llama_url=llama_url)
            if caps.get("llama_server_online"):
                raw_script_data = self._generate_with_local_llm(prompt, genre, chars, ep_num, llama_url)
            if not raw_script_data:
                raw_script_data = self._generate_with_cloud_or_cli_llm(prompt, genre, chars, ep_num)

        # 3. If LLM fails or is offline, generate via deterministic Neuro-Storytelling Heuristic
        if not raw_script_data:
            raw_script_data = self._generate_heuristic_story(prompt, genre, chars, ep_num, target_duration_sec)

        # 4. Apply Director Engine & Retention Grading
        scenes: List[CinematicScene] = []
        for idx, sc in enumerate(raw_script_data.get("scenes", [])):
            act = sc.get("act", "ESCALATION")
            diag = sc.get("dialogue", "")
            cam_dir = DirectorEngine.apply_cinematic_direction(
                act=act,
                dialogue=diag,
                speaker=sc.get("speaker", "NARRATOR"),
                custom_shot=sc.get("shot_type"),
                custom_move=sc.get("camera_movement"),
            )
            vfx = sc.get("vfx") if sc.get("vfx") in VFX_CUES else DirectorEngine.ACT_DIRECTOR_TEMPLATES.get(act, {}).get("vfx", "NONE")
            sfx = sc.get("sfx") if sc.get("sfx") in AUDIO_SFX_CUES else DirectorEngine.ACT_DIRECTOR_TEMPLATES.get(act, {}).get("sfx", "NONE")

            # Assign voice key based on speaker
            speaker_name = sc.get("speaker", "NARRATOR")
            matched_char = next((c for c in chars if c.char_id == speaker_name or c.name.lower() in speaker_name.lower()), None)
            voice_key = matched_char.voice_key if matched_char else "pm_alex"

            scenes.append(
                CinematicScene(
                    scene_id=idx + 1,
                    act=act,
                    speaker=speaker_name,
                    voice_profile=voice_key,
                    dialogue=diag,
                    visual_description=sc.get("visual_description", f"Cena cinematográfica {act.lower()} estilo {genre}"),
                    camera=cam_dir,
                    vfx=vfx,
                    sfx=sfx,
                    manga_panel_mode=sc.get("manga_panel_mode", "READING_RTL"),
                    estimated_duration_sec=cam_dir.duration_sec,
                )
            )

        script = CinematicScript(
            story_id=story_id,
            title=raw_script_data.get("title", f"Episódio {ep_num}: {prompt[:30]}"),
            genre=genre,
            season=season,
            episode=ep_num,
            hook_sentence=raw_script_data.get("hook_sentence", scenes[0].dialogue if scenes else "O que você faria se descobrisse a verdade agora?"),
            loop_sentence=raw_script_data.get("loop_sentence", scenes[-1].dialogue if scenes else "E é por isso que..."),
            target_duration_sec=sum(s.estimated_duration_sec for s in scenes),
            characters=chars,
            scenes=scenes,
        )

        # 5. Score retention and persist to continuity database
        script.retention_score = RetentionEngine.evaluate_script_retention(script)
        self.continuity.record_episode(script)
        return script

    def _create_cast_for_genre(self, genre: str, story_id: str) -> List[CharacterProfile]:
        """Generate cohesive archetypal characters with distinct voices for the selected genre."""
        if genre == "financas_negocios":
            return [
                CharacterProfile(
                    char_id="narrator",
                    name="Estrategista Chefe",
                    role="PROTAGONIST",
                    archetype="Analista Macroeconômico",
                    visual_traits="Postura executiva firme, gráficos financeiros holográficos ao fundo.",
                    costume="Blazer azul-marinho sob medida.",
                    voice_key="pm_santa",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="analyst",
                    name="Especialista de Dados",
                    role="MENTOR",
                    archetype="Investidor Quantitativo",
                    visual_traits="Olhar analítico diante de terminais de mercado em tempo real.",
                    costume="Camisa social escura minimalista.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
            ]
        elif genre == "ia_futuro_tech":
            return [
                CharacterProfile(
                    char_id="narrator",
                    name="Arquiteto de IA",
                    role="PROTAGONIST",
                    archetype="Engenheiro de Sistemas Neurais",
                    visual_traits="Laboratório moderno iluminado por servidores e interfaces limpas.",
                    costume="Jaqueta técnica minimalista preta.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="researcher",
                    name="Pesquisadora Líder",
                    role="MENTOR",
                    archetype="Cientista de Computação",
                    visual_traits="Expressão focada analisando benchmarks de modelos em tempo real.",
                    costume="Traje executivo tech moderno.",
                    voice_key="pf_dora",
                    first_appearance_ep=1,
                ),
            ]
        elif genre in {"psicologia_mentalismo", "saude_biohacking"}:
            return [
                CharacterProfile(
                    char_id="narrator",
                    name="Neurocientista",
                    role="PROTAGONIST",
                    archetype="Especialista em Comportamento Humano",
                    visual_traits="Estúdio acolhedor com iluminação cinematográfica quente.",
                    costume="Visual casual elegante.",
                    voice_key="pf_dora" if genre == "saude_biohacking" else "pm_alex",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="observer",
                    name="Mentor Clínico",
                    role="MENTOR",
                    archetype="Pesquisador Comportamental",
                    visual_traits="Postura calma explicando mecanismos do cérebro.",
                    costume="Blazer cinza texturizado.",
                    voice_key="pm_santa",
                    first_appearance_ep=1,
                ),
            ]
        elif genre in {"podcast_debates", "jornalismo_global"}:
            return [
                CharacterProfile(
                    char_id="narrator",
                    name="Host do Estúdio",
                    role="PROTAGONIST",
                    archetype="Comunicador & Investigador",
                    visual_traits="Estúdio de podcast profissional com microfone dinâmico de broadcast.",
                    costume="Camiseta preta premium e fones de estúdio.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="guest",
                    name="Convidado Especialista",
                    role="WITNESS",
                    archetype="Analista de Bastidores",
                    visual_traits="Expressão intensa revelando dados de bastidores no microfone.",
                    costume="Jaqueta casual escura.",
                    voice_key="pm_santa",
                    first_appearance_ep=1,
                ),
            ]
        elif genre == "dark_shonen":
            return [
                CharacterProfile(
                    char_id="protagonist",
                    name="Ren",
                    role="PROTAGONIST",
                    archetype="Espadachim Estrategista",
                    visual_traits="Cabelo preto espetado, olhos cinzas atentos, capa rasgada com runas azuis.",
                    costume="Uniforme de combate tático preto e bandagens nos braços.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="antagonist",
                    name="Kage",
                    role="ANTAGONIST",
                    archetype="Lorde das Sombras",
                    visual_traits="Máscara de porcelana quebrada, olhos escuros profundos e aura arroxeada.",
                    costume="Manto aristocrático carmesim com detalhes dourados corrompidos.",
                    voice_key="pm_santa",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="mentor",
                    name="Yuki",
                    role="MENTOR",
                    archetype="Oráculo Tecnológico",
                    visual_traits="Cabelo prateado curto, óculos holográficos e postura fria e analítica.",
                    costume="Jaleco cinza minimalista com cabos de fibra ótica integrados.",
                    voice_key="pf_dora",
                    first_appearance_ep=1,
                ),
            ]
        elif genre == "cyberpunk_br":
            return [
                CharacterProfile(
                    char_id="protagonist",
                    name="Maya",
                    role="PROTAGONIST",
                    archetype="Hacker de Guerrilha",
                    visual_traits="Cabelo moicano roxo neon, implante ocular cibernético dourado no olho esquerdo.",
                    costume="Jaqueta de couro sintético grafitada e botas militares gastas.",
                    voice_key="pf_dora",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="antagonist",
                    name="Dr. Barros",
                    role="ANTAGONIST",
                    archetype="Executivo Transumano",
                    visual_traits="Rosto sem rugas sintético, terno de nanofibra impecável e sorriso calculista.",
                    costume="Terno cinza metálico com abotoaduras de diamante quântico.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
            ]
        else:  # misterio, curiosidades, terror
            return [
                CharacterProfile(
                    char_id="narrator",
                    name="O Investigador",
                    role="NARRATOR",
                    archetype="Observador Imparcial",
                    visual_traits="Silhueta sombria segurando arquivos confidenciais sob a luz da lua.",
                    costume="Sobretudo marrom clássico.",
                    voice_key="pm_alex",
                    first_appearance_ep=1,
                ),
                CharacterProfile(
                    char_id="witness",
                    name="A Testemunha",
                    role="WITNESS",
                    archetype="Sobrevivente Traumatizado",
                    visual_traits="Olhar assustado, respiração ofegante e cicatriz sutil na mão.",
                    costume="Roupas casuais desgastadas.",
                    voice_key="pf_dora",
                    first_appearance_ep=1,
                ),
            ]

    def _generate_heuristic_story(
        self,
        prompt: str,
        genre: str,
        chars: List[CharacterProfile],
        ep_num: int,
        target_duration_sec: float,
    ) -> Dict[str, Any]:
        """Deterministic, multi-niche non-repetitive narrative generator built for 100% offline edge execution."""
        raw_prompt = " ".join((prompt or "").split()).strip() or "O Segredo Oculto"
        core_subject = re.sub(
            r"^(?:o\s+segredo\s+(?:proibido|oculto)\s+(?:sobre|de|do|da)\s+|a\s+verdade\s+sobre\s+|teoria\s+(?:sobre|de)\s+|mist[ée]rio\s+(?:sobre|de)\s+|como\s+funciona\s+)",
            "",
            raw_prompt,
            flags=re.IGNORECASE,
        ).strip() or raw_prompt

        detected_genre, _, _ = detect_universal_genre_and_niche(raw_prompt, genre)
        spk_0 = chars[0].char_id if chars else "narrator"
        spk_1 = chars[1].char_id if len(chars) > 1 else spk_0
        mahoraga = MahoragaEngine()
        spoke_idx, spoke = mahoraga.select_adaptive_spoke(detected_genre, core_subject)
        v_idx = (spoke_idx + ep_num) % 3

        if detected_genre == "financas_negocios":
            variants = [
                (
                    f"Quase todo mundo ignora esse detalhe prático quando o assunto é {core_subject}!",
                    f"É exatamente essa regra que separa quem perde poder de compra de quem domina {core_subject}.",
                    [
                        f"Na superfície, a maioria acredita que basta seguir o fluxo comum do mercado para ter segurança.",
                        f"Mas os números mostram que pequenas taxas invisíveis e decisões atrasadas drenam até trinta por cento do resultado acumulado.",
                        f"A grande virada acontece quando você antecipa o movimento e protege seu caixa antes da maioria perceber.",
                        f"Aplicar esse ajuste simples hoje muda completamente sua margem de segurança nos próximos doze meses!",
                        f"Você já aplicava essa estratégia na prática? Comente aqui embaixo!",
                    ],
                ),
                (
                    f"Por que {core_subject} está mudando a estratégia de quem investe com inteligência no Brasil?",
                    f"Quem entende {core_subject} agora sai na frente antes do próximo ciclo de mercado.",
                    [
                        f"Sempre que o cenário econômico aperta, o investidor médio reage tarde demais às oscilações.",
                        f"Analisando os dados reais de {core_subject}, fica claro onde está o verdadeiro custo de oportunidade no orçamento.",
                        f"Enquanto muitos olham apenas para a rentabilidade bruta, o ganho real vem do controle de liquidez e proteção contra juros.",
                        f"Reorganizar essa alocação protege o patrimônio e cria fluxo de caixa consistente mês a mês!",
                        f"Como você está posicionando sua carteira hoje? Deixe nos comentários!",
                    ],
                ),
                (
                    f"O cálculo real por trás de {core_subject} que raramente explicam de forma direta!",
                    f"Dominar a lógica de {core_subject} é o passo mais seguro para multiplicar patrimônio no longo prazo.",
                    [
                        f"Quando colocamos os números na ponta do lápis, a diferença entre o hábito comum e a decisão estratégica assusta.",
                        f"No caso de {core_subject}, pequenos ajustes percentuais geram um efeito bola de neve decisivo ao longo do ano.",
                        f"O ponto-chave é eliminar intermediários caros e focar no que realmente entrega retorno líquido real.",
                        f"Essa mudança simples transforma passivos invisíveis em reserva produtiva para o seu bolso!",
                        f"Qual foi a sua maior lição financeira este ano? Comente aqui!",
                    ],
                ),
            ]
            hook, loop, body_lines = variants[v_idx]
            dialogues = [
                (spk_0, hook, f"Close-up dinâmico destacando o impacto financeiro de {core_subject}."),
                ("narrator", body_lines[0], f"Gráfico cinematográfico mostrando a curva real por trás de {core_subject}."),
                (spk_1, body_lines[1], "Enquadramento médio focado nos dados comparativos de longo prazo."),
                (spk_0, body_lines[2], "Mudança rápida de câmera revelando a estratégia dos grandes investidores."),
                (spk_1, body_lines[3], "Zoom de impacto nos indicadores positivos de patrimônio."),
                (spk_0, f"{body_lines[4]} {loop}", "Fechamento executivo em estúdio com transição limpa para loop."),
            ]
        elif detected_genre == "ia_futuro_tech":
            variants = [
                (
                    f"A mudança técnica em {core_subject} que está redefinindo toda a indústria agora!",
                    f"E essa evolução em {core_subject} mostra que a nova geração de tecnologia já está entre nós.",
                    [
                        f"Até poucos meses atrás, rodar soluções desse nível exigia infraestrutura pesada e custos altíssimos.",
                        f"Agora, com otimização extrema de algoritmos, tarefas que levavam horas são resolvidas em poucos segundos.",
                        f"O detalhe que poucos perceberam é que quem domina essa arquitetura agora ganha uma vantagem competitiva imediata.",
                        f"Essa mudança não substitui apenas processos manuais, ela permite criar sistemas inteiros com muito menos recursos!",
                        f"Você já testou isso nos seus projetos? Deixe nos comentários!",
                    ],
                ),
                (
                    f"Por que engenheiros e empresas estão migrando tão rápido para {core_subject}?",
                    f"É por isso que {core_subject} se tornou peça central na engenharia de software moderna.",
                    [
                        f"O maior gargalo da tecnologia atual nunca foi falta de código, mas sim eficiência de algoritmo, latência e confiabilidade em produção.",
                        f"Com a chegada de {core_subject}, o processamento local e a automação inteligente atingiram outro patamar de velocidade.",
                        f"Na prática, equipes enxutas conseguem entregar em dias o que antes exigia meses de desenvolvimento complexo.",
                        f"O resultado direto é código mais limpo, menor custo operacional e respostas em tempo real!",
                        f"Qual ferramenta mais acelerou seu trabalho recentemente? Comente aqui!",
                    ],
                ),
                (
                    f"O que ninguém te contou sobre como {core_subject} funciona por baixo do capô!",
                    f"Entender a engenharia de {core_subject} separa quem apenas usa ferramentas de quem lidera o mercado.",
                    [
                        f"Quando olhamos apenas para a interface final, parece mágica, mas o segredo está na arquitetura de execução.",
                        f"Em {core_subject}, a combinação de modelos compactos com hardware otimizado reduziu drasticamente o consumo de memória.",
                        f"Isso abre espaço para aplicações autônomas rodando direto na borda, com privacidade total e zero latência de rede.",
                        f"Estamos vendo a maior transição de infraestrutura tecnológica da última década acontecer ao vivo!",
                        f"O que você acha desse avanço? Compartilhe nos comentários!",
                    ],
                ),
            ]
            hook, loop, body_lines = variants[v_idx]
            dialogues = [
                (spk_0, hook, f"Close-up tecnológico mostrando {core_subject} em execução real."),
                ("narrator", body_lines[0], f"Plano aberto comparando servidores antigos com a nova arquitetura de {core_subject}."),
                (spk_1, body_lines[1], "Corte dinâmico exibindo velocidade de processamento e eficiência."),
                (spk_0, body_lines[2], "Ângulo dramático destacando o salto de produtividade prática."),
                (spk_1, body_lines[3], "Zoom rápido no resultado final gerado com precisão."),
                (spk_0, f"{body_lines[4]} {loop}", "Encerramento futurista conectado ao gancho inicial."),
            ]
        elif detected_genre in {"psicologia_mentalismo", "saude_biohacking"}:
            variants = [
                (
                    f"O segredo sobre {core_subject} que ninguém percebeu no próprio cérebro!",
                    f"Por isso entender {core_subject} transforma completamente sua rotina desde os primeiros minutos do dia.",
                    [
                        "Estudos de neurociência mostram que nosso foco e energia são moldados por sinais automáticos do ambiente.",
                        "Quando você ignora esse mecanismo biológico, seu cérebro entra em fadiga de decisão logo nas primeiras horas.",
                        "O segredo está em inverter o estímulo: um ajuste de dois minutos reprograma a resposta automática da mente.",
                        "O resultado imediato é mais clareza mental, controle emocional e energia real ao longo de todo o dia!",
                        "Faça esse teste amanhã cedo e me conte nos comentários!",
                    ],
                ),
                (
                    f"Por que sua mente sabota sua concentração quando o assunto é {core_subject}?",
                    f"Dominar esse gatilho de {core_subject} devolve seu controle mental sem depender de força de vontade.",
                    [
                        "A maioria das pessoas tenta vencer o cansaço mental com mais pressão, o que só aumenta o ruído cognitivo.",
                        "Na prática, o sistema nervoso responde muito melhor a micro-pausas estratégicas e redução de estímulos vazios.",
                        "Quando você troca o piloto automático por um protocolo simples de respiração e foco, a dopamina estabiliza.",
                        "Em poucos dias, tarefas difíceis voltam a parecer leves e sua memória retém muito mais informação!",
                        "Qual hábito mais drena sua energia hoje? Deixe nos comentários!",
                    ],
                ),
                (
                    f"O padrão invisível por trás de {core_subject} que muda sua produtividade!",
                    f"Aplicar essa lógica simples de {core_subject} protege sua mente contra exaustão crônica.",
                    [
                        "Pouca gente sabe, mas os primeiros trinta minutos após acordar definem a química do foco para o dia inteiro.",
                        "Expor o cérebro a alertas e comparações logo cedo dispara um ciclo de ansiedade difícil de frear.",
                        "Ao criar uma janela limpa antes das telas, você preserva atenção profunda para o que realmente importa.",
                        "O ganho aparece rápido: decisões mais calmas, menos procrastinação e noites de sono muito melhores!",
                        "Você já testou uma rotina sem telas ao acordar? Comente aqui!",
                    ],
                ),
            ]
            hook, loop, body_lines = variants[v_idx]
            dialogues = [
                (spk_0, hook, f"Close-up expressivo ilustrando o gatilho neural ligado a {core_subject}."),
                ("narrator", body_lines[0], f"Visualização clara do ciclo de atenção e dopamina em {core_subject}."),
                (spk_1, body_lines[1], "Enquadramento médio mostrando o contraste entre distração e foco profundo."),
                (spk_0, body_lines[2], "Transição visual rápida destacando a quebra do padrão mental."),
                (spk_1, body_lines[3], "Zoom nos indicadores de performance cognitiva e bem-estar."),
                (spk_0, f"{body_lines[4]} {loop}", "Fechamento calmo e magnético conectando ao início."),
            ]
        elif detected_genre in {"podcast_debates", "jornalismo_global", "curiosidades_cosmicas"}:
            variants = [
                (
                    f"A verdade oculta sobre {core_subject} acaba de revelar o que quase ninguém percebeu!",
                    f"E esse desdobramento sobre {core_subject} muda totalmente o que veremos nas próximas semanas.",
                    [
                        "Enquanto todo mundo olhava apenas para a versão superficial da notícia, os dados reais apontavam para outra direção.",
                        "Quando cruzamos os fatos mais recentes, fica evidente como uma decisão estratégica nos bastidores alterou todo o equilíbrio.",
                        "O ponto de virada é que o efeito prático disso já começou a aparecer e impacta diretamente o cenário atual.",
                        "Quem entende esse movimento antes da maioria consegue enxergar exatamente para onde o jogo está indo agora!",
                        "Qual é a sua opinião sobre essa virada? Comente aqui embaixo!",
                    ],
                ),
                (
                    f"O detalhe decisivo em {core_subject} que dividiu os especialistas esta semana!",
                    f"Acompanhar os próximos capítulos de {core_subject} vai mostrar quem realmente acertou a previsão.",
                    [
                        "À primeira vista, parecia apenas mais uma manchete passageira sem grandes consequências práticas.",
                        "Mas uma análise mais atenta mostra que os interesses envolvidos nessa escolha têm impacto de longo prazo.",
                        "De um lado, quem defende mudança imediata; do outro, quem alerta para o efeito colateral no curto prazo.",
                        "O fato concreto é que o público já sente os reflexos dessa decisão no dia a dia!",
                        "De que lado desse debate você fica? Deixe seu comentário!",
                    ],
                ),
                (
                    f"Por que {core_subject} virou o assunto mais comentado nos bastidores hoje?",
                    f"E essa história sobre {core_subject} ainda está longe do capítulo final.",
                    [
                        "Poucas vezes um tema conectou tantos fatores econômicos, tecnológicos e humanos ao mesmo tempo.",
                        "Os registros divulgados recentemente preenchem lacunas que antes deixavam toda a discussão no escuro.",
                        "Agora, com as cartas na mesa, cada novo anúncio ganha um peso muito maior para o mercado e para o público.",
                        "Entender o contexto completo evita cair em narrativas rasas e revela a tendência real!",
                        "O que você espera que aconteça daqui pra frente? Comente aqui!",
                    ],
                ),
            ]
            hook, loop, body_lines = variants[v_idx]
            dialogues = [
                (spk_0, hook, f"Enquadramento de estúdio destacando a manchete central sobre {core_subject}."),
                ("narrator", body_lines[0], f"Sequência visual contextualizando o cenário completo de {core_subject}."),
                (spk_1, body_lines[1], "Corte aproximado destacando o ponto crítico da análise."),
                (spk_0, body_lines[2], "Movimento de câmera dinâmico revelando a consequência imediata."),
                (spk_1, body_lines[3], "Close-up de alto impacto no clímax da revelação."),
                (spk_0, f"{body_lines[4]} {loop}", "Encerramento jornalístico limpo pronto para replay contínuo."),
            ]
        else:
            stop_caps = {"O", "A", "Os", "As", "Um", "Uma", "De", "Do", "Da", "Em", "No", "Na", "Segredo", "Proibido", "Oculto", "Teoria", "Capitulo", "Capítulo", "One", "Piece"}
            named_entities = [
                w.strip(",.:;!?")
                for w in core_subject.split()
                if w and w[0].isupper() and len(w.strip(",.:;!?")) >= 3 and w.strip(",.:;!?") not in stop_caps
            ]
            char_a = named_entities[0] if named_entities else (chars[0].name if chars else "Ren")
            char_b = named_entities[1] if len(named_entities) > 1 else (chars[1].name if len(chars) > 1 else "Imu")
            variants = [
                (
                    f"O segredo proibido sobre {core_subject} que quase ninguém percebeu acaba de mudar tudo!",
                    f"E essa revelação sobre {core_subject} é apenas o começo do que está por vir.",
                    [
                        f"Durante muito tempo, a verdadeira conexão envolvendo {char_a} parecia apenas uma teoria distante.",
                        f"Mas as pistas recentes ligando {char_a} e {char_b} trouxeram à tona um passado apagado da história.",
                        "O que parecia coincidência era, na verdade, uma peça central guardada a sete chaves.",
                        f"Agora que a verdade veio à tona, o desfecho envolvendo {char_a} se tornou inevitável!",
                        "Qual é a sua teoria sobre isso? Comente aqui embaixo!",
                    ],
                ),
                (
                    f"A pista oculta em {core_subject} que muda completamente o rumo da história!",
                    f"Depois dessa virada envolvendo {char_a}, nenhum capítulo seguinte será igual.",
                    [
                        f"Quem acompanhou apenas a batalha principal deixou passar o gesto silencioso de {char_a} no momento decisivo.",
                        f"Quando comparamos essa cena com os eventos antigos de {char_b}, o quebra-cabeça finalmente se fecha.",
                        "Cada detalhe visual tinha um propósito exato preparado muito antes desse confronto acontecer.",
                        f"Se essa aliança ou ruptura se confirmar, o equilíbrio de forças inteiro vai desabar!",
                        "Você também notou esse detalhe escondido? Deixe seu palpite!",
                    ],
                ),
                (
                    f"Ninguém estava pronto para o que {core_subject} acabou de revelar!",
                    f"E o próximo passo de {char_a} pode reescrever tudo o que sabíamos até aqui.",
                    [
                        f"Por trás da aparente calma antes da tempestade, {char_a} carregava uma resposta que mudaria todo o arco.",
                        f"O contraste com a trajetória de {char_b} deixa claro que o verdadeiro conflito nunca foi apenas força bruta.",
                        "Existe uma regra antiga quebrada exatamente nessa cena, e os sinais estavam lá desde o começo.",
                        "Agora a contagem regressiva começou e cada segundo aproxima o ponto sem volta!",
                        "O que você faria no lugar dele? Comente sua teoria!",
                    ],
                ),
            ]
            hook, loop, body_lines = variants[v_idx]
            dialogues = [
                (spk_0, hook, f"Close-up dramático nos olhos de {char_a} diante da revelação sobre {core_subject}."),
                ("narrator", body_lines[0], f"Plano aberto cinematográfico revelando o cenário principal de {core_subject}."),
                (spk_1, body_lines[1], f"Enquadramento médio focado na tensão entre {char_a} e {char_b}."),
                (spk_0, body_lines[2], "Ângulo holandês destacando o momento exato da reviravolta."),
                (spk_1, body_lines[3], f"Zoom extremo no clímax dramático entre {char_a} e {char_b}."),
                (spk_0, f"{body_lines[4]} {loop}", f"{char_a} encarando o horizonte enquanto a cena fecha em suspense."),
            ]

        mahoraga.record_speech_turn(detected_genre, spoke["id"], core_subject, immunize_spoken_script(hook))

        act_specs = [
            ("HOOK", "CLOSE_UP", "SLOW_ZOOM_IN", "IMPACT_LINES", "WHOOSH"),
            ("SETUP", "WIDE_SHOT", "PAN_RIGHT_TO_LEFT", "NONE", "NONE"),
            ("ESCALATION", "MEDIUM_SHOT", "SLOW_ZOOM_IN", "VIGNETTE_PULSE", "TENSION_RISER"),
            ("TWIST", "DUTCH_ANGLE", "WHIP_PAN", "COLOR_INVERT", "GLITCH"),
            ("CLIMAX", "EXTREME_CLOSE_UP", "SHAKE_IMPACT", "SCREEN_SHAKE", "SUB_BOOM"),
            ("LOOP_OUTRO", "CLOSE_UP", "SLOW_ZOOM_IN", "NONE", "HEARTBEAT"),
        ]

        scenes = []
        for (act, shot, move, vfx, sfx), (speaker, diag, vdesc) in zip(act_specs, dialogues):
            scenes.append({
                "act": act,
                "speaker": speaker,
                "dialogue": diag,
                "visual_description": vdesc,
                "shot_type": shot,
                "camera_movement": move,
                "vfx": vfx,
                "sfx": sfx,
            })

        clean_title = raw_prompt if len(raw_prompt) <= 78 else raw_prompt[:78].rsplit(" ", 1)[0]
        return {
            "title": clean_title,
            "hook_sentence": hook,
            "loop_sentence": loop,
            "scenes": scenes,
        }

    def _generate_with_cloud_or_cli_llm(
        self,
        prompt: str,
        genre: str,
        chars: List[CharacterProfile],
        ep_num: int,
    ) -> Optional[Dict[str, Any]]:
        """Use OpenRouter/Gemini or local 1-shot llama-cli when available to write a custom non-repetitive script for ANY niche."""
        try:
            from .highlights import call_gemini_or_openai
            detected_genre, detected_niche, _ = detect_universal_genre_and_niche(prompt, genre)
            cast_desc = ", ".join([f"{c.name} ({c.role})" for c in chars])
            llm_prompt = (
                f"Você é um roteirista e diretor profissional de Shorts/Reels/TikTok no Brasil especialista no nicho '{detected_niche}' ({detected_genre}).\n"
                f"Escreva um roteiro curto, envolvente, SEM repetição de frases e com linguagem natural de locutor humano sobre: {prompt}\n"
                f"Elenco de apoio opcional: {cast_desc}.\n"
                "Responda APENAS um JSON válido com as chaves:\n"
                '{"title": "Título completo sem cortar palavras (max 70 chars)", '
                '"hook_sentence": "Gancho curto e impactante de 4 a 6 palavras", '
                '"loop_sentence": "Frase final de fechamento", '
                '"scenes": [{"act": "HOOK", "speaker": "narrator", "dialogue": "Fala natural, informativa e direta...", "visual_description": "Descrição visual...", "shot_type": "CLOSE_UP", "camera_movement": "SLOW_ZOOM_IN", "vfx": "IMPACT_LINES", "sfx": "WHOOSH"}]}'
            )
            raw = call_gemini_or_openai(llm_prompt)
            clean_text = strip_reasoning_tags(raw)
            m = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed.get("scenes"), list) and len(parsed["scenes"]) >= 3:
                    return parsed
        except Exception:
            pass
        return None

    def _generate_with_local_llm(
        self,
        prompt: str,
        genre: str,
        chars: List[CharacterProfile],
        ep_num: int,
        llama_url: str,
    ) -> Optional[Dict[str, Any]]:
        """Prompt local llama-server in JSON mode with structured schema enforcement."""
        cast_desc = ", ".join([f"{c.name} ({c.role}, voz: {c.voice_key})" for c in chars])
        sys_prompt = (
            "Você é o Diretor e Roteirista Chefe de um estúdio cinematográfico de vídeos curtos verticais (Shorts/Reels).\n"
            "Crie um roteiro de alta retenção no idioma Português do Brasil.\n"
            f"Gênero: {genre}. Elenco: {cast_desc}. Episódio: {ep_num}.\n"
            "Retorne ESTRITAMENTE um JSON com as chaves: title, hook_sentence, loop_sentence, scenes.\n"
            "Cada cena deve ter: act (HOOK, SETUP, ESCALATION, TWIST, CLIMAX, LOOP_OUTRO), speaker, dialogue, visual_description, shot_type, camera_movement, vfx, sfx."
        )
        payload = json.dumps({
            "model": "local",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Tema do episódio: {prompt}"},
            ],
            "max_tokens": 850,
            "temperature": 0.5,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{llama_url.rstrip('/')}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            clean_text = strip_reasoning_tags(raw_text)
            
            # Extract JSON block
            m = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if "scenes" in parsed and isinstance(parsed["scenes"], list):
                    return parsed
        except Exception:
            pass
        return None
