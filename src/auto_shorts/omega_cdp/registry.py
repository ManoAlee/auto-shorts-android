"""Platform Capability Registry — Defines authorized access boundaries, rate limits, and allowed operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import AdapterType, Platform, PlatformCapability

PROHIBITED_OPERATIONS = frozenset({
    "captcha_bypass",
    "credential_stuffing",
    "private_api_reverse",
    "mfa_bypass",
    "bot_impersonation",
    "fingerprint_spoofing",
    "unauthorized_scraping",
})

_DEFAULT_CAPABILITIES: Dict[Platform, PlatformCapability] = {
    Platform.YOUTUBE: PlatformCapability(
        platform=Platform.YOUTUBE,
        primary_adapter=AdapterType.HYBRID,
        supports_official_api=True,
        supports_cdp_automation=True,
        allowed_operations=[
            "upload_video",
            "set_title",
            "set_description",
            "set_made_for_kids",
            "set_altered_content",
            "manage_drafts",
            "check_processing_status",
            "inspect_live_shorts",
            "visual_qa_screenshot",
            "fetch_analytics",
        ],
        rate_limit_per_day=15,
        requires_human_auth_setup=True,
        notes="Suporta API oficial YouTube Data v3 (quota restrita) e YouTube Studio Web via CDP autorizado.",
    ),
    Platform.TIKTOK: PlatformCapability(
        platform=Platform.TIKTOK,
        primary_adapter=AdapterType.CDP_BROWSER,
        supports_official_api=False,
        supports_cdp_automation=True,
        allowed_operations=[
            "upload_video",
            "set_caption",
            "set_privacy_public",
            "check_upload_complete",
            "manage_studio_drafts",
            "visual_qa_screenshot",
            "inspect_published_video",
            "fetch_public_metrics",
        ],
        rate_limit_per_day=10,
        requires_human_auth_setup=True,
        notes="Opera via TikTok Studio Web oficial com perfil persistido e autenticação interativa humana inicial.",
    ),
    Platform.INSTAGRAM: PlatformCapability(
        platform=Platform.INSTAGRAM,
        primary_adapter=AdapterType.HYBRID,
        supports_official_api=True,
        supports_cdp_automation=True,
        allowed_operations=[
            "upload_reels_meta_graph_api",
            "check_reels_status",
            "visual_qa_screenshot",
            "inspect_live_reel",
            "fetch_insights_api",
        ],
        rate_limit_per_day=25,
        requires_human_auth_setup=True,
        notes="Publicação oficial direta via Meta Graph API v19+ Reels e inspeção visual pós-publicação via CDP.",
    ),
    Platform.TWITCH: PlatformCapability(
        platform=Platform.TWITCH,
        primary_adapter=AdapterType.HYBRID,
        supports_official_api=True,
        supports_cdp_automation=True,
        allowed_operations=[
            "monitor_stream_status",
            "capture_authorized_live_clip",
            "inspect_vod",
            "visual_qa_screenshot",
        ],
        rate_limit_per_day=50,
        requires_human_auth_setup=False,
        notes="Monitoramento de canais autorizados e captura de clipes via Streamlink / API Helix.",
    ),
    Platform.KICK: PlatformCapability(
        platform=Platform.KICK,
        primary_adapter=AdapterType.CDP_BROWSER,
        supports_official_api=False,
        supports_cdp_automation=True,
        allowed_operations=[
            "monitor_stream_status",
            "capture_authorized_live_clip",
            "visual_qa_screenshot",
        ],
        rate_limit_per_day=30,
        requires_human_auth_setup=False,
        notes="Inspeção e monitoramento de transmissões autorizadas via Streamlink e CDP.",
    ),
}


class PlatformCapabilityRegistry:
    """Repositório de regras de capacidade, conformidade e limites por plataforma."""

    def __init__(self, custom_capabilities: Optional[Dict[Platform, PlatformCapability]] = None) -> None:
        self._capabilities: Dict[Platform, PlatformCapability] = dict(_DEFAULT_CAPABILITIES)
        if custom_capabilities:
            self._capabilities.update(custom_capabilities)

    def get_capability(self, platform: Platform | str) -> Optional[PlatformCapability]:
        p = Platform(platform) if isinstance(platform, str) else platform
        return self._capabilities.get(p)

    def is_operation_allowed(self, platform: Platform | str, operation: str) -> bool:
        if operation in PROHIBITED_OPERATIONS:
            return False
        cap = self.get_capability(platform)
        if not cap:
            return False
        return operation in cap.allowed_operations

    def list_capabilities(self) -> List[Dict[str, Any]]:
        result = []
        for p, cap in self._capabilities.items():
            result.append({
                "platform": p.value,
                "primary_adapter": cap.primary_adapter.value,
                "supports_official_api": cap.supports_official_api,
                "supports_cdp_automation": cap.supports_cdp_automation,
                "allowed_operations_count": len(cap.allowed_operations),
                "allowed_operations": cap.allowed_operations,
                "rate_limit_per_day": cap.rate_limit_per_day,
                "requires_human_auth_setup": cap.requires_human_auth_setup,
                "notes": cap.notes,
            })
        return result
