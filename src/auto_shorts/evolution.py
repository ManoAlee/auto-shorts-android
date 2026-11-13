"""Closed-loop self-learning & UCB1 bandit telemetry store for auto-shorts-android."""

import math
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


DEFAULT_DB_PATH = Path("output") / "shorts_evolution.db"
DURATION_BUCKETS: List[Tuple[str, float, float]] = [
    ("30-45s", 0.0, 45.0),
    ("45-60s", 45.0, 60.0),
    ("60-75s", 60.0, 75.0),
    ("75-95s", 75.0, 999.0),
]


def duration_bucket(seconds: float) -> str:
    for label, low, high in DURATION_BUCKETS:
        if low <= seconds < high:
            return label
    return "60-75s"


def compute_reward(
    views: int,
    avg_watch_pct: float = 0.0,
    shares: int = 0,
    saves: int = 0,
    likes: int = 0,
) -> float:
    """Compute normalized reward emphasizing retention, shares, and saves."""
    retention_mult = 0.5 + max(0.0, min(1.5, avg_watch_pct / 100.0))
    base = math.log1p(max(0, views)) * retention_mult
    viral_actions = math.log1p(max(0, shares) * 4 + max(0, saves) * 3 + max(0, likes) * 0.5)
    return round(base + viral_actions, 4)


class EvolutionStore:
    """SQLite-backed closed-loop tracker that learns winning layouts, hooks, and durations."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clip_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    layout TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    duration_bucket TEXT NOT NULL,
                    hook_title TEXT NOT NULL,
                    predicted_score INTEGER NOT NULL,
                    output_path TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clip_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clip_id INTEGER NOT NULL REFERENCES clip_runs(id) ON DELETE CASCADE,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    views INTEGER DEFAULT 0,
                    avg_watch_pct REAL DEFAULT 0.0,
                    likes INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    saves INTEGER DEFAULT 0,
                    reward REAL DEFAULT 0.0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_sources (
                    video_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS background_arms (
                    niche TEXT NOT NULL,
                    style TEXT NOT NULL,
                    pulls INTEGER DEFAULT 0,
                    reward_sum REAL DEFAULT 0.0,
                    last_quality REAL DEFAULT 0.0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (niche, style)
                )
                """
            )

    def get_processed_ids(self) -> Set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT video_id FROM processed_sources").fetchall()
        return {str(row["video_id"]) for row in rows}

    def mark_source_processed(self, video_id: str, url: str, title: str, niche: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_sources (video_id, url, title, niche)
                VALUES (?, ?, ?, ?)
                """,
                (video_id, url, title, niche),
            )

    def record_clip(
        self,
        source: str,
        platform: str,
        niche: str,
        layout: str,
        duration_sec: float,
        hook_title: str,
        predicted_score: int,
        output_path: str,
    ) -> int:
        bucket = duration_bucket(duration_sec)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO clip_runs
                (source, platform, niche, layout, duration_sec, duration_bucket, hook_title, predicted_score, output_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source, platform, niche, layout, duration_sec, bucket, hook_title, predicted_score, output_path),
            )
            return int(cur.lastrowid)

    def record_feedback(
        self,
        clip_id: int,
        views: int,
        avg_watch_pct: float = 0.0,
        likes: int = 0,
        shares: int = 0,
        saves: int = 0,
    ) -> float:
        if isinstance(clip_id, bool) or not isinstance(clip_id, int) or clip_id <= 0:
            raise ValueError("clip_id must be a positive integer")
        for field, value in (("views", views), ("likes", likes), ("shares", shares), ("saves", saves)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 1_000_000_000_000:
                raise ValueError(f"{field} must be an integer between 0 and 1000000000000")
        if isinstance(avg_watch_pct, bool) or not isinstance(avg_watch_pct, (int, float)):
            raise ValueError("avg_watch_pct must be a number between 0 and 500")
        if not math.isfinite(float(avg_watch_pct)) or not 0 <= float(avg_watch_pct) <= 500:
            raise ValueError("avg_watch_pct must be a number between 0 and 500")
        reward = compute_reward(views=views, avg_watch_pct=avg_watch_pct, shares=shares, saves=saves, likes=likes)
        with self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM clip_runs WHERE id = ?", (clip_id,)).fetchone()
            if not exists:
                raise ValueError(f"clip_id {clip_id} not found in {self.db_path}")
            conn.execute(
                """
                INSERT INTO clip_metrics (clip_id, views, avg_watch_pct, likes, shares, saves, reward)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (clip_id, views, avg_watch_pct, likes, shares, saves, reward),
            )
        return reward

    def learning_status(self, candidate_limit: int = 40) -> Dict:
        """Return real-feedback coverage and recent clips that still need metrics."""
        safe_limit = max(1, min(100, int(candidate_limit)))
        with self._connect() as conn:
            total_clips = int(conn.execute("SELECT COUNT(*) FROM clip_runs").fetchone()[0])
            measured_clips = int(conn.execute("SELECT COUNT(DISTINCT clip_id) FROM clip_metrics").fetchone()[0])
            avg_reward_row = conn.execute(
                """
                SELECT AVG(m.reward)
                FROM clip_metrics m
                WHERE m.id = (
                    SELECT MAX(m2.id) FROM clip_metrics m2 WHERE m2.clip_id = m.clip_id
                )
                """
            ).fetchone()
            candidates = conn.execute(
                """
                SELECT r.id, r.created_at, r.output_path, r.hook_title, r.niche,
                       r.platform, r.duration_sec, r.predicted_score
                FROM clip_runs r
                WHERE NOT EXISTS (
                    SELECT 1 FROM clip_metrics m WHERE m.clip_id = r.id
                )
                ORDER BY r.id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return {
            "total_clips": total_clips,
            "measured_clips": measured_clips,
            "pending_feedback": max(0, total_clips - measured_clips),
            "avg_latest_reward": round(float(avg_reward_row[0] or 0.0), 4),
            "candidates": [dict(row) for row in candidates],
        }

    def recommend_layout(self, niche: str, candidates: Optional[List[str]] = None) -> str:
        """Select layout using UCB1 exploration/exploitation over recorded rewards."""
        arms = candidates or ["blur_bg", "center_crop", "split_top_bottom"]
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.layout AS arm, COUNT(m.id) AS n, AVG(m.reward) AS avg_reward
                FROM clip_runs r
                JOIN clip_metrics m ON m.clip_id = r.id
                    AND m.id = (SELECT MAX(m2.id) FROM clip_metrics m2 WHERE m2.clip_id = r.id)
                WHERE r.niche = ?
                GROUP BY r.layout
                """,
                (niche,),
            ).fetchall()

        stats = {row["arm"]: (int(row["n"]), float(row["avg_reward"] or 0.0)) for row in rows}
        total_n = sum(n for n, _ in stats.values())
        if total_n == 0:
            return arms[0]

        for arm in arms:
            if arm not in stats:
                return arm

        best_arm = arms[0]
        best_ucb = -1.0
        for arm in arms:
            n, avg = stats[arm]
            ucb = avg + math.sqrt(2.0 * math.log(total_n) / n)
            if ucb > best_ucb:
                best_ucb = ucb
                best_arm = arm
        return best_arm

    def build_learning_context(self, niche: str, top_k: int = 3) -> str:
        """Summarize top-performing real hooks & weak patterns for prompt injection."""
        with self._connect() as conn:
            winners = conn.execute(
                """
                SELECT r.hook_title, r.duration_bucket, r.layout, m.views, m.avg_watch_pct, m.reward
                FROM clip_runs r
                JOIN clip_metrics m ON m.clip_id = r.id
                    AND m.id = (SELECT MAX(m2.id) FROM clip_metrics m2 WHERE m2.clip_id = r.id)
                WHERE r.niche = ?
                ORDER BY m.reward DESC
                LIMIT ?
                """,
                (niche, top_k),
            ).fetchall()

        if not winners:
            return ""

        lines = ["Aprendizado real de performance anterior neste nicho (use como referencia):"]
        for row in winners:
            lines.append(
                f"- VENCEDOR (views={row['views']}, retencao={row['avg_watch_pct']:.0f}%, "
                f"layout={row['layout']}, faixa={row['duration_bucket']}): \"{row['hook_title']}\""
            )
        return "\n".join(lines)

    def record_background_outcome(
        self,
        niche: str,
        style: str,
        quality_score: float = 80.0,
        views: int = 0,
        avg_watch_pct: float = 0.0,
    ) -> float:
        """Update adaptive visual-background bandit arm reward from validation/metrics."""
        clean_style = (style or "dynamic").strip().lower()
        clean_niche = (niche or "geral").strip().lower()
        reward = max(0.0, min(1.5, quality_score / 100.0)) + compute_reward(views=views, avg_watch_pct=avg_watch_pct)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO background_arms (niche, style, pulls, reward_sum, last_quality)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(niche, style) DO UPDATE SET
                    pulls = pulls + 1,
                    reward_sum = reward_sum + excluded.reward_sum,
                    last_quality = excluded.last_quality,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (clean_niche, clean_style, reward, float(quality_score)),
            )
        return round(reward, 4)

    def select_evolving_background_style(
        self,
        niche: str,
        candidates: List[str],
        last_style: str = "",
    ) -> str:
        """Select next visual background via UCB1 bandit while forbidding consecutive repeats."""
        clean_cands = [c for c in candidates if c] or ["dynamic"]
        pool = [c for c in clean_cands if c != last_style] or clean_cands
        clean_niche = (niche or "geral").strip().lower()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT style, pulls, reward_sum FROM background_arms WHERE niche = ?",
                (clean_niche,),
            ).fetchall()
        stats = {
            str(r["style"]): (int(r["pulls"]), float(r["reward_sum"]) / max(1, int(r["pulls"])))
            for r in rows
        }
        total_pulls = sum(p for p, _ in stats.values())
        unexplored = [s for s in pool if s not in stats or stats[s][0] == 0]
        if unexplored:
            import random
            return random.choice(unexplored)
        best = pool[0]
        best_ucb = -1.0
        for s in pool:
            n_s, avg_r = stats[s]
            ucb = avg_r + math.sqrt(2.0 * math.log(max(2, total_pulls)) / max(1, n_s))
            if ucb > best_ucb:
                best_ucb = ucb
                best = s
        return best

    def list_background_evolution(self) -> List[Dict]:
        """Return learned adaptive background rankings for diagnostics/UI."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT style, SUM(pulls) AS pulls, AVG(last_quality) AS avg_quality, SUM(reward_sum) AS total_reward
                FROM background_arms
                GROUP BY style
                ORDER BY avg_quality DESC, pulls DESC
                """
            ).fetchall()
        return [
            {
                "style": str(r["style"]),
                "pulls": int(r["pulls"] or 0),
                "avg_quality": round(float(r["avg_quality"] or 0.0), 1),
            }
            for r in rows
        ]

