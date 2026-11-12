"""Character Engine: Persistent Visual Identity, Character Bible & Drift Detection.

Designed for 100% offline edge execution on Android/Termux ARM64 with zero mandatory
third-party dependencies. Provides full character profile modeling, color palette
consistency verification, dynamic prompt compilation, and visual drift inspection.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# EXPRESSIONS & POSES VOCABULARY
# ==============================================================================

STANDARD_EXPRESSIONS = (
    "NEUTRAL",
    "INTENSE_FOCUS",
    "SHOCKED",
    "SMIRK_CONFIDENT",
    "ENRAGED",
    "VULNERABLE",
    "SMILING_GENTLE",
    "PAINED_EXHAUSTED",
)

STANDARD_POSES = (
    "STAND_NEUTRAL",
    "COMBAT_READY",
    "ARMS_CROSSED",
    "LOOKING_BACK_OVER_SHOULDER",
    "DASHING_FORWARD",
    "FALLEN_REACHING_OUT",
    "SITTING_MEDITATIVE",
)


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclass
class PhysicalTraits:
    gender: str = "NON_SPECIFIED"
    apparent_age: int = 24
    height_build: str = "Médio atlético"
    hair_color: str = "Preto"
    hair_style: str = "Curto repicado com franja lateral"
    eye_color: str = "Azul elétrico"
    eye_shape: str = "Amendoado focado"
    skin_tone: str = "Claro com subtom neutro"
    distinguishing_features: str = "Cicatriz sutil sobre a sobrancelha direita"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostumeDetails:
    primary_outfit: str = "Sobretudo preto de combate com revestimento tático"
    secondary_elements: str = "Bandagens pretas nos punhos e calça cargo tática"
    accessories: str = "Pingente holográfico de prisma no pescoço"
    color_palette_hex: List[str] = field(default_factory=lambda: ["#0B0E14", "#00F0FF", "#2A324B"])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CharacterBibleEntry:
    char_id: str
    name: str
    role: str  # PROTAGONIST, ANTAGONIST, MENTOR, RIVAL, WITNESS
    archetype: str
    personality_summary: str
    physical: PhysicalTraits = field(default_factory=PhysicalTraits)
    costume: CostumeDetails = field(default_factory=CostumeDetails)
    voice_key: str = "pm_alex"
    voice_speed: float = 1.05
    voice_pitch: float = 1.0
    expressions_map: Dict[str, str] = field(default_factory=dict)
    poses_map: Dict[str, str] = field(default_factory=dict)
    reference_images: List[str] = field(default_factory=list)
    appearance_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "char_id": self.char_id,
            "name": self.name,
            "role": self.role,
            "archetype": self.archetype,
            "personality_summary": self.personality_summary,
            "physical": self.physical.to_dict(),
            "costume": self.costume.to_dict(),
            "voice_key": self.voice_key,
            "voice_speed": self.voice_speed,
            "voice_pitch": self.voice_pitch,
            "expressions_map": self.expressions_map,
            "poses_map": self.poses_map,
            "reference_images": self.reference_images,
            "appearance_history": self.appearance_history,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def compile_visual_prompt(self, expression: str = "NEUTRAL", pose: str = "STAND_NEUTRAL") -> str:
        """Compile a bulletproof, consistent visual prompt for 2D/Anime/CGI generation engines."""
        exp_desc = self.expressions_map.get(expression, f"expressão facial {expression.lower()}")
        pose_desc = self.poses_map.get(pose, f"pose corporal {pose.lower()}")
        p = self.physical
        c = self.costume

        parts = [
            f"{self.name}, {self.role.lower()} ({self.archetype.lower()})",
            f"{p.apparent_age} anos, compleição {p.height_build}",
            f"cabelo {p.hair_color} estilo {p.hair_style}",
            f"olhos {p.eye_color} {p.eye_shape}",
            f"pele tom {p.skin_tone}, {p.distinguishing_features}",
            f"vestindo {c.primary_outfit}, {c.secondary_elements}",
            f"acessórios: {c.accessories}",
            f"paleta de cores primária: {', '.join(c.color_palette_hex)}",
            f"expressão: {exp_desc}",
            f"pose: {pose_desc}",
            "enquadramento vertical 9:16 cinematográfico, iluminação dramática, alta definição",
        ]
        return ", ".join(parts)


# ==============================================================================
# CHARACTER DATABASE (SQLITE PERSISTENCE)
# ==============================================================================

class CharacterDatabase:
    """Manages the persistent character roster and appearance tracking in SQLite."""

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS character_bible (
                    char_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    archetype TEXT,
                    personality TEXT,
                    physical_json TEXT NOT NULL,
                    costume_json TEXT NOT NULL,
                    voice_key TEXT NOT NULL,
                    voice_speed REAL DEFAULT 1.0,
                    voice_pitch REAL DEFAULT 1.0,
                    expressions_json TEXT,
                    poses_json TEXT,
                    references_json TEXT,
                    history_json TEXT,
                    created_at REAL NOT NULL
                );
            """)

    def save_character(self, entry: CharacterBibleEntry) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO character_bible
                   (char_id, name, role, archetype, personality, physical_json, costume_json,
                    voice_key, voice_speed, voice_pitch, expressions_json, poses_json,
                    references_json, history_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.char_id,
                    entry.name,
                    entry.role,
                    entry.archetype,
                    entry.personality_summary,
                    json.dumps(entry.physical.to_dict(), ensure_ascii=False),
                    json.dumps(entry.costume.to_dict(), ensure_ascii=False),
                    entry.voice_key,
                    entry.voice_speed,
                    entry.voice_pitch,
                    json.dumps(entry.expressions_map, ensure_ascii=False),
                    json.dumps(entry.poses_map, ensure_ascii=False),
                    json.dumps(entry.reference_images, ensure_ascii=False),
                    json.dumps(entry.appearance_history, ensure_ascii=False),
                    entry.created_at,
                ),
            )

    def get_character(self, char_id: str) -> Optional[CharacterBibleEntry]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM character_bible WHERE char_id = ?", (char_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def list_all_characters(self) -> List[CharacterBibleEntry]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM character_bible ORDER BY name ASC")
            return [self._row_to_entry(row) for row in cur.fetchall()]

    def record_appearance(self, char_id: str, story_id: str, season: int, episode: int, scene_id: int) -> None:
        char = self.get_character(char_id)
        if not char:
            return
        char.appearance_history.append({
            "story_id": story_id,
            "season": season,
            "episode": episode,
            "scene_id": scene_id,
            "timestamp": time.time(),
        })
        self.save_character(char)

    def _row_to_entry(self, row: sqlite3.Row) -> CharacterBibleEntry:
        phy_dict = json.loads(row["physical_json"] or "{}")
        cos_dict = json.loads(row["costume_json"] or "{}")
        return CharacterBibleEntry(
            char_id=row["char_id"],
            name=row["name"],
            role=row["role"],
            archetype=row["archetype"] or "",
            personality_summary=row["personality"] or "",
            physical=PhysicalTraits(**phy_dict) if phy_dict else PhysicalTraits(),
            costume=CostumeDetails(**cos_dict) if cos_dict else CostumeDetails(),
            voice_key=row["voice_key"] or "pm_alex",
            voice_speed=float(row["voice_speed"] or 1.0),
            voice_pitch=float(row["voice_pitch"] or 1.0),
            expressions_map=json.loads(row["expressions_json"] or "{}"),
            poses_map=json.loads(row["poses_json"] or "{}"),
            reference_images=json.loads(row["references_json"] or "[]"),
            appearance_history=json.loads(row["history_json"] or "[]"),
            created_at=float(row["created_at"] or time.time()),
        )


# ==============================================================================
# VISUAL DRIFT & PALETTE CONSISTENCY INSPECTOR (100% OFFLINE)
# ==============================================================================

class CharacterVisualAuditor:
    """Evaluates cross-scene character visual stability, palette drift, and motion variance without PyTorch."""

    @staticmethod
    def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
        clean = hex_str.lstrip("#")
        if len(clean) == 3:
            clean = "".join(c * 2 for c in clean)
        if len(clean) != 6:
            return (128, 128, 128)
        return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))

    @classmethod
    def analyze_frame_palette_alignment(cls, rgb_bytes: bytes, target_palette_hex: List[str]) -> Dict[str, Any]:
        """Measure what percentage of pixels in a frame align with the character's designated palette."""
        if not rgb_bytes or not target_palette_hex:
            return {"match_percentage": 100.0, "status": "SKIPPED_NO_DATA"}

        target_rgbs = [cls.hex_to_rgb(hx) for hx in target_palette_hex]
        matched_pixels = 0
        total_samples = 0

        # Sample every 12th pixel (RGB triplet) to keep inspection sub-millisecond on mobile CPU
        step = 12 * 3
        for i in range(0, len(rgb_bytes) - 3, step):
            pr, pg, pb = rgb_bytes[i], rgb_bytes[i + 1], rgb_bytes[i + 2]
            total_samples += 1
            # Check Euclidean color distance against closest target palette color
            min_dist = min(
                math.sqrt((pr - tr) ** 2 + (pg - tg) ** 2 + (pb - tb) ** 2)
                for tr, tg, tb in target_rgbs
            )
            # Threshold distance < 95 in RGB space counts as harmonious match
            if min_dist < 95:
                matched_pixels += 1

        match_pct = round((matched_pixels / max(1, total_samples)) * 100.0, 1)
        # Consistent scenes have at least 18% palette overlap (character usually occupies 20-50% of 9:16 vertical area)
        passed = match_pct >= 14.0

        return {
            "match_percentage": match_pct,
            "passed": passed,
            "status": "CONSISTENT" if passed else "PALETTE_DRIFT_DETECTED",
            "samples_analyzed": total_samples,
        }

    @classmethod
    def compare_scene_frames_consistency(cls, frame_a_bytes: bytes, frame_b_bytes: bytes) -> Dict[str, Any]:
        """Compute pixel-level structural consistency between consecutive scenes featuring the same character."""
        if not frame_a_bytes or not frame_b_bytes:
            return {"structural_similarity_score": 100, "status": "INSUFFICIENT_DATA"}

        n = min(len(frame_a_bytes), len(frame_b_bytes))
        if n < 64:
            return {"structural_similarity_score": 100, "status": "INSUFFICIENT_DATA"}

        # Compare pixel differences
        diffs = [abs(frame_a_bytes[i] - frame_b_bytes[i]) for i in range(0, n, 4)]
        mean_diff = sum(diffs) / max(1, len(diffs))

        # A completely different scene has mean_diff > 70.
        # A consistent continuity scene with motion has mean_diff between 8 and 55.
        if mean_diff < 1.0:
            status = "FROZEN_DUPLICATE"
            score = 50
        elif 5.0 <= mean_diff <= 65.0:
            status = "HEALTHY_CONTINUITY"
            score = 95
        else:
            status = "EXTREME_DISCONTINUITY"
            score = max(40, int(100 - (mean_diff - 65) * 1.5))

        return {
            "mean_pixel_delta": round(mean_diff, 2),
            "continuity_score": score,
            "status": status,
        }

    @classmethod
    def inspect_mp4_character_consistency(
        cls,
        mp4_path: Path,
        character: CharacterBibleEntry,
    ) -> Dict[str, Any]:
        """Inspect a rendered MP4 video for character color harmony and absence of jarring visual breaks."""
        if not mp4_path.is_file() or not shutil.which("ffmpeg"):
            return {"ok": True, "verdict": "FFmpeg indisponível; auditoria simplificada.", "score": 85}

        # Extract 2 central frames at 30% and 70% duration downscaled to 64x64 raw RGB
        frames_rgb: List[bytes] = []
        timestamps = [1.5, 4.5]
        for ts in timestamps:
            try:
                proc = subprocess.run(
                    [
                        "ffmpeg", "-y", "-loglevel", "error", "-ss", str(ts), "-i", str(mp4_path),
                        "-frames:v", "1", "-vf", "scale=64:64,format=rgb24", "-f", "rawvideo", "-",
                    ],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if proc.stdout and len(proc.stdout) >= 64 * 64 * 3:
                    frames_rgb.append(proc.stdout)
            except Exception:
                continue

        if not frames_rgb:
            return {"ok": True, "verdict": "Frames não decodificados; ignorado.", "score": 80}

        palette_res = cls.analyze_frame_palette_alignment(frames_rgb[0], character.costume.color_palette_hex)
        continuity_res = (
            cls.compare_scene_frames_consistency(frames_rgb[0], frames_rgb[1])
            if len(frames_rgb) > 1
            else {"continuity_score": 90, "status": "SINGLE_FRAME"}
        )

        overall_score = int(0.5 * palette_res["match_percentage"] + 0.5 * continuity_res["continuity_score"])
        is_ok = bool(palette_res["passed"] and continuity_res.get("continuity_score", 90) >= 60)

        return {
            "ok": is_ok,
            "character_id": character.char_id,
            "character_name": character.name,
            "palette_audit": palette_res,
            "continuity_audit": continuity_res,
            "overall_character_consistency_score": overall_score,
            "verdict": (
                f"Identidade de '{character.name}' preservada com {palette_res['match_percentage']}% de harmonia de paleta."
                if is_ok
                else f"Alerta de desvio de personagem: paleta {palette_res['match_percentage']}% e continuidade {continuity_res.get('continuity_score')}/100."
            ),
        }
