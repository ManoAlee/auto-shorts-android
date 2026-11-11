"""Smart Retention engine calibrated to Instagram Reels, TikTok, and Shorts algorithms."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RetentionProfile:
    platform: str
    min_silence_sec: float
    pace_speed: float
    punch_zoom: float
    target_min_sec: int
    target_max_sec: int
    reels_cta_hint: str


RETENTION_PROFILES: Dict[str, RetentionProfile] = {
    "instagram_reels": RetentionProfile(
        platform="instagram_reels",
        min_silence_sec=0.45,  # Aggressive jump-cut for high completion & rewatch rate
        pace_speed=1.04,       # Subtle 4% pace lift keeps attention without chipmunk voice
        punch_zoom=1.05,       # 5% periodic zoom pulse every 6s as visual pattern interrupt
        target_min_sec=25,
        target_max_sec=48,     # Sweet spot for Reels completion + shares/saves
        reels_cta_hint="Salva esse Reel pra nao perder e manda pra um amigo que curte isso!",
    ),
    "youtube_shorts": RetentionProfile(
        platform="youtube_shorts",
        min_silence_sec=0.50,
        pace_speed=1.03,
        punch_zoom=1.04,
        target_min_sec=30,
        target_max_sec=56,
        reels_cta_hint="Se inscreve para acompanhar os proximos cortes e novidades todos os dias!",
    ),
    "tiktok_rewards": RetentionProfile(
        platform="tiktok_rewards",
        min_silence_sec=0.65,  # Preserves >60s runtime required by Creator Rewards
        pace_speed=1.00,
        punch_zoom=1.04,
        target_min_sec=62,
        target_max_sec=90,
        reels_cta_hint="Comenta sua opiniao e segue para acompanhar os proximos cortes!",
    ),
}


def get_retention_profile(platform: str) -> RetentionProfile:
    return RETENTION_PROFILES.get(platform, RETENTION_PROFILES["instagram_reels"])


def build_pattern_interrupt_filter(width: int, height: int, zoom: float = 1.05, interval_sec: int = 6) -> str:
    """Return a zero-overhead FFmpeg scale+crop expression toggling subtle zoom every N seconds.

    Breaks visual monotony every few seconds to hold attention and avoid static-reupload flags.
    """
    if zoom <= 1.0:
        return ""
    amp = (zoom - 1.0) / 2.0
    # Smooth cos-eased zoom pulse avoiding jarring jumps while preserving eval=frame
    return (
        f"scale='trunc((iw*(1+{amp:.4f}*(1-cos(2*PI*t/{interval_sec}))))/2)*2':"
        f"'trunc((ih*(1+{amp:.4f}*(1-cos(2*PI*t/{interval_sec}))))/2)*2':eval=frame,"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
    )

