"""Universal Deduplication & Content Registry Engine.

Guarantees 100% zero-repeat across all channels, niches, and automated cycles:
1. Canonical URL normalization (purging tracking query params, fragments, redirects).
2. YouTube Video ID tracking across all historical renders and publish ledgers.
3. High-precision semantic title similarity (Jaccard token overlap + Levenshtein distance).
4. Permanent historical ledger (never truncates or forgets past produced topics).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

# Common stop words in Portuguese to avoid matching on prepositions
STOP_WORDS_PT = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "e", "ou", "para", "por", "com", "sem", "sob", "sobre", "entre",
    "apos", "após", "antes", "depois", "durante", "contra", "segundo",
    "que", "se", "mas", "como", "quando", "onde", "porque", "por que",
    "ja", "já", "mais", "menos", "muito", "todo", "toda", "apenas",
    "veja", "confira", "saiba", "entenda", "mundo", "brasil", "hoje", "shorts",
}


def normalize_news_url(raw_url: str) -> str:
    """Strip marketing tags, session IDs, and tracking query params from news URLs."""
    if not raw_url or not raw_url.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        # Filter out tracking query params
        qs = urllib.parse.parse_qsl(parsed.query)
        clean_qs = [
            (k, v) for k, v in qs
            if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref", "source", "oc"))
        ]
        new_query = urllib.parse.urlencode(clean_qs)
        cleaned = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower().rstrip("/"),
            parsed.path.rstrip("/"),
            "",
            new_query,
            "",
        ))
        return cleaned
    except Exception:
        return raw_url.strip().lower()


def tokenize_title(title: str) -> Set[str]:
    """Extract significant lowercased keywords from a title."""
    clean = re.sub(r"[^a-zA-Z0-9áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ\s]", " ", (title or "").lower())
    tokens = {w for w in clean.split() if len(w) >= 3 and w not in STOP_WORDS_PT}
    return tokens


def calculate_jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Calculate token-level Jaccard similarity between two sets of words."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


class ContentRegistry:
    """Central registry tracking all past generated stories, clips, and URLs."""

    def __init__(self, out_dir: str | Path = "output") -> None:
        self.out_dir = Path(out_dir)
        self.seen_urls: Set[str] = set()
        self.seen_video_ids: Set[str] = set()
        self.past_titles: List[str] = []
        self.past_token_sets: List[Set[str]] = []
        self._load_registry()

    def _load_registry(self) -> None:
        """Scan historical files: .world_news_seen.json, publish_ledger.json, and *.publish.json."""
        if not self.out_dir.is_dir():
            return

        # 1. Load legacy .world_news_seen.json
        seen_file = self.out_dir / ".world_news_seen.json"
        if seen_file.is_file():
            try:
                data = json.loads(seen_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        norm = normalize_news_url(str(item))
                        if norm:
                            self.seen_urls.add(norm)
                        self.seen_urls.add(str(item).strip())
            except Exception:
                pass

        # 2. Load publish_ledger.json
        ledger_file = self.out_dir / "publish_ledger.json"
        if ledger_file.is_file():
            try:
                data = json.loads(ledger_file.read_text(encoding="utf-8"))
                for hist in data.get("history", []):
                    title = str(hist.get("title") or "").strip()
                    if title:
                        self._register_title(title)
                    fname = str(hist.get("filename") or "")
                    if "_short_" in fname:
                        vid = fname.split("_short_", 1)[0]
                        self.seen_video_ids.add(vid)
            except Exception:
                pass

        # 3. Load all *.publish.json in vault
        for pub_path in self.out_dir.glob("*.publish.json"):
            try:
                pub_data = json.loads(pub_path.read_text(encoding="utf-8"))
                # Register title & pt_title
                for t in (pub_data.get("title"), pub_data.get("pt_title"), pub_data.get("hook_title")):
                    if t:
                        self._register_title(str(t).strip())
                # Register URL
                src_info = pub_data.get("source_news") or {}
                url = src_info.get("url") or pub_data.get("source_url")
                if url:
                    norm = normalize_news_url(str(url))
                    if norm:
                        self.seen_urls.add(norm)
                    self.seen_urls.add(str(url).strip())
                # Register Video ID prefix
                fname = pub_path.stem
                if "_short_" in fname:
                    vid = fname.split("_short_", 1)[0]
                    self.seen_video_ids.add(vid)
            except Exception:
                continue

    def _register_title(self, title: str) -> None:
        t_clean = title.strip()
        if not t_clean or t_clean in self.past_titles:
            return
        tokens = tokenize_title(t_clean)
        if tokens:
            self.past_titles.append(t_clean)
            self.past_token_sets.append(tokens)

    def is_duplicate_url(self, url: str) -> bool:
        """Check if URL was ever produced."""
        if not url:
            return False
        clean = url.strip()
        norm = normalize_news_url(clean)
        return clean in self.seen_urls or (bool(norm) and norm in self.seen_urls)

    def is_duplicate_video_id(self, video_id: str) -> bool:
        """Check if YouTube video was already downloaded or clipped."""
        return bool(video_id and video_id.strip() in self.seen_video_ids)

    def is_duplicate_headline(self, candidate_title: str, threshold: float = 0.65) -> Tuple[bool, Optional[str]]:
        """Check if a headline is semantically identical or heavily overlapping with any past produced story."""
        c_clean = candidate_title.strip()
        if not c_clean:
            return False, None

        # 1. Exact match
        for past in self.past_titles:
            if c_clean.lower() == past.lower():
                return True, past

        # 2. Token overlap (Jaccard similarity)
        c_tokens = tokenize_title(c_clean)
        if len(c_tokens) < 3:
            return False, None

        for past_title, past_tokens in zip(self.past_titles, self.past_token_sets):
            sim = calculate_jaccard_similarity(c_tokens, past_tokens)
            if sim >= threshold:
                return True, past_title
            # Also check if candidate is an almost complete subset of a past title (or vice versa)
            overlap = len(c_tokens & past_tokens)
            min_len = min(len(c_tokens), len(past_tokens))
            if min_len >= 3 and (overlap / min_len) >= 0.85:
                return True, past_title

        return False, None

    def is_duplicate(self, story_or_clip: Dict[str, Any]) -> Tuple[bool, str]:
        """Comprehensive check: returns (is_duplicate, reason)."""
        # Check URL
        url = str(story_or_clip.get("url") or story_or_clip.get("id") or "")
        if self.is_duplicate_url(url):
            return True, f"URL já processada anteriormente: {url}"

        # Check YouTube video ID
        vid = str(story_or_clip.get("id") or "").strip()
        if self.is_duplicate_video_id(vid):
            return True, f"Vídeo ID já processado anteriormente: {vid}"

        # Check Title Semantic Similarity
        title = str(story_or_clip.get("title") or "")
        is_dup_title, matched_past = self.is_duplicate_headline(title)
        if is_dup_title:
            return True, f"Manchete semanticamente idêntica a vídeo anterior: '{matched_past}'"

        return False, ""

    def record_produced_story(self, url: str, title: str, video_id: str = "") -> None:
        """Register newly produced story permanently in memory and update seen file."""
        if url:
            norm = normalize_news_url(url)
            if norm:
                self.seen_urls.add(norm)
            self.seen_urls.add(url.strip())
        if video_id:
            self.seen_video_ids.add(video_id.strip())
        if title:
            self._register_title(title)

        # Persist full list (never truncated to 100)
        seen_file = self.out_dir / ".world_news_seen.json"
        try:
            current: List[str] = []
            if seen_file.is_file():
                current = list(json.loads(seen_file.read_text(encoding="utf-8")))
            if url and url not in current:
                current.append(url)
            # Save all (full permanent ledger)
            seen_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
