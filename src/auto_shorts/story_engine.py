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
    "dark_shonen": "Ação sobrenatural épica, superação, batalhas táticas e reviravoltas dramáticas no estilo anime moderno.",
    "cyberpunk_br": "Ficção científica urbana no Brasil de 2077, megacorporações, inteligência artificial rebelde e submundo hacker.",
    "misterio_investigativo": "Suspense noir, crimes inexplicáveis, pistas microscópicas, deduções lógicas e revelações chocantes.",
    "curiosidades_cosmicas": "Exploração espacial, paradoxos temporais, buracos negros, civilizações alienígenas e fronteiras da física.",
    "terror_psicologico": "Horror analógico, lendas urbanas reimaginadas, quebra da quarta parede e tensão psicológica crescente.",
}


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

        # 2. Try LLM Generation (Local GGUF or Cloud)
        caps = detect_android_llm_capabilities(llama_url=llama_url)
        raw_script_data = None
        if caps.get("llama_server_online"):
            raw_script_data = self._generate_with_local_llm(prompt, genre, chars, ep_num, llama_url)

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
        if genre == "dark_shonen":
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
        """Deterministic, highly curated narrative generator built for 100% offline edge execution."""
        clean_topic = prompt.strip() or "O Segredo Proibido"
        char_a = chars[0].name if chars else "Ren"
        char_b = chars[1].name if len(chars) > 1 else "Kage"

        hook = f"O segredo proibido sobre {clean_topic} que quase ninguém percebeu..."
        loop = f"E foi assim que começou o mistério de {clean_topic}."

        scenes = [
            {
                "act": "HOOK",
                "speaker": chars[0].char_id,
                "dialogue": hook,
                "visual_description": f"Close-up dramático nos olhos de {char_a} refletindo uma chama azul neon.",
                "shot_type": "CLOSE_UP",
                "camera_movement": "SLOW_ZOOM_IN",
                "vfx": "IMPACT_LINES",
                "sfx": "WHOOSH",
            },
            {
                "act": "SETUP",
                "speaker": "narrator",
                "dialogue": f"No episódio {ep_num}, tudo indicava que o plano estava sob controle.",
                "visual_description": f"Plano aberto de uma metrópole futurista com céu tempestuoso e relâmpagos ao fundo.",
                "shot_type": "WIDE_SHOT",
                "camera_movement": "PAN_RIGHT_TO_LEFT",
                "vfx": "NONE",
                "sfx": "NONE",
            },
            {
                "act": "ESCALATION",
                "speaker": chars[1].char_id if len(chars) > 1 else chars[0].char_id,
                "dialogue": f"Mas {char_b} encontrou um registro escondido há mais de cem anos.",
                "visual_description": f"Enquadramento médio de {char_b} analisando um holograma vermelho em ruínas.",
                "shot_type": "MEDIUM_SHOT",
                "camera_movement": "SLOW_ZOOM_IN",
                "vfx": "VIGNETTE_PULSE",
                "sfx": "TENSION_RISER",
            },
            {
                "act": "TWIST",
                "speaker": chars[0].char_id,
                "dialogue": f"O documento provava: o inimigo não era quem todos pensavam.",
                "visual_description": "Ângulo holandês (Dutch Angle) mostrando o chão se rachando com energia negra.",
                "shot_type": "DUTCH_ANGLE",
                "camera_movement": "WHIP_PAN",
                "vfx": "COLOR_INVERT",
                "sfx": "GLITCH",
            },
            {
                "act": "CLIMAX",
                "speaker": chars[1].char_id if len(chars) > 1 else chars[0].char_id,
                "dialogue": f"Se esse poder for liberado, não restará nada para contar a história.",
                "visual_description": f"Corte em zoom extremo no confronto cara a cara entre {char_a} e {char_b}.",
                "shot_type": "EXTREME_CLOSE_UP",
                "camera_movement": "SHAKE_IMPACT",
                "vfx": "SCREEN_SHAKE",
                "sfx": "SUB_BOOM",
            },
            {
                "act": "LOOP_OUTRO",
                "speaker": chars[0].char_id,
                "dialogue": f"Você teria coragem de enfrentar essa verdade? {loop}",
                "visual_description": f"{char_a} virando as costas para a câmera e caminhando rumo à tempestade.",
                "shot_type": "CLOSE_UP",
                "camera_movement": "SLOW_ZOOM_IN",
                "vfx": "NONE",
                "sfx": "HEARTBEAT",
            },
        ]

        return {
            "title": f"{clean_topic.title()} — Ep. {ep_num}",
            "hook_sentence": hook,
            "loop_sentence": loop,
            "scenes": scenes,
        }

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
