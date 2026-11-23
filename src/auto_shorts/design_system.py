"""AutoShorts Creative Design System — Typography, Safe Zones, Color Palettes and Niche Presets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SafeZoneSpec:
    """Safe zones para telas verticais 9:16 (1080x1920) considerando UI do YouTube Shorts, TikTok e Reels."""
    width: int = 1080
    height: int = 1920
    top_margin_px: int = 220       # Área de status bar, search e header do app
    bottom_margin_px: int = 380    # Área de botões de som, legendas da plataforma e descrição
    right_margin_px: int = 140     # Coluna de engajamento (Like, Comentário, Compartilhar, Remix)
    left_margin_px: int = 60       # Margem de segurança lateral

    @property
    def usable_rect(self) -> Tuple[int, int, int, int]:
        """Retorna (x1, y1, x2, y2) da caixa delimitadora segura para texto e rostos."""
        return (
            self.left_margin_px,
            self.top_margin_px,
            self.width - self.right_margin_px,
            self.height - self.bottom_margin_px,
        )


@dataclass
class NicheDesignPreset:
    """Preset estético audiovisual completo por nicho de conteúdo."""
    id: str
    label: str
    primary_font: str
    font_weight: str
    primary_color_hex: str
    accent_color_hex: str
    background_tint_hex: str
    stroke_color_hex: str
    stroke_width_px: int
    subtitle_style: str            # "kinetic_word", "two_line_box", "lower_third", "minimal_clean"
    max_words_per_cue: int
    visual_pace: str               # "dynamic_fast", "cinematic_steady", "moderate_clear"
    ducking_db: float              # Atenuação da trilha de fundo sob a fala (ex: -16.0 dB)
    target_loudness_lufs: float    # -14.0 LUFS para plataformas móveis
    banner_style: str              # "urgent_alert", "neon_glow", "editorial_pill", "minimal_dark"


_NICHE_PRESETS: Dict[str, NicheDesignPreset] = {
    "news": NicheDesignPreset(
        id="news",
        label="Plantão Notícias & Geopolítica",
        primary_font="Montserrat-Bold,Arial-Bold",
        font_weight="800",
        primary_color_hex="#FFFFFF",
        accent_color_hex="#E63946",       # Vermelho urgente
        background_tint_hex="#0A1128",     # Navy escuro
        stroke_color_hex="#000000",
        stroke_width_px=3,
        subtitle_style="two_line_box",
        max_words_per_cue=4,
        visual_pace="moderate_clear",
        ducking_db=-18.0,
        target_loudness_lufs=-14.0,
        banner_style="urgent_alert",
    ),
    "tech": NicheDesignPreset(
        id="tech",
        label="IA & Tecnologia Avançada",
        primary_font="Inter-Bold,Roboto-Bold",
        font_weight="800",
        primary_color_hex="#F8F9FA",
        accent_color_hex="#00F5D4",       # Ciano neon tech
        background_tint_hex="#0B090A",     # Preto absoluto
        stroke_color_hex="#161A1D",
        stroke_width_px=3,
        subtitle_style="kinetic_word",
        max_words_per_cue=3,
        visual_pace="dynamic_fast",
        ducking_db=-16.0,
        target_loudness_lufs=-14.0,
        banner_style="neon_glow",
    ),
    "gaming": NicheDesignPreset(
        id="gaming",
        label="Games & GTA 6",
        primary_font="Impact,Arial-Black",
        font_weight="900",
        primary_color_hex="#FFBE0B",       # Amarelo elétrico
        accent_color_hex="#FF006E",       # Rosa neon
        background_tint_hex="#140152",     # Roxo escuro
        stroke_color_hex="#000000",
        stroke_width_px=4,
        subtitle_style="kinetic_word",
        max_words_per_cue=3,
        visual_pace="dynamic_fast",
        ducking_db=-14.0,
        target_loudness_lufs=-14.0,
        banner_style="neon_glow",
    ),
    "storytelling": NicheDesignPreset(
        id="storytelling",
        label="Narrativas & Mistérios",
        primary_font="Cinzel-Bold,Georgia-Bold",
        font_weight="700",
        primary_color_hex="#F1FAEE",
        accent_color_hex="#D4AF37",       # Ouro clássico
        background_tint_hex="#1A1A1A",
        stroke_color_hex="#000000",
        stroke_width_px=2,
        subtitle_style="minimal_clean",
        max_words_per_cue=5,
        visual_pace="cinematic_steady",
        ducking_db=-20.0,
        target_loudness_lufs=-15.0,
        banner_style="editorial_pill",
    ),
    "educational": NicheDesignPreset(
        id="educational",
        label="Curiosidades & Ciência",
        primary_font="Poppins-Bold,Arial-Bold",
        font_weight="700",
        primary_color_hex="#FFFFFF",
        accent_color_hex="#38B000",       # Verde vibrante
        background_tint_hex="#101820",
        stroke_color_hex="#000000",
        stroke_width_px=3,
        subtitle_style="two_line_box",
        max_words_per_cue=4,
        visual_pace="moderate_clear",
        ducking_db=-16.0,
        target_loudness_lufs=-14.0,
        banner_style="editorial_pill",
    ),
    "podcast": NicheDesignPreset(
        id="podcast",
        label="Cortes de Podcast & Entrevistas",
        primary_font="Montserrat-ExtraBold,Arial-Bold",
        font_weight="800",
        primary_color_hex="#FFFFFF",
        accent_color_hex="#FB5607",       # Laranja podcast
        background_tint_hex="#1B1B1E",
        stroke_color_hex="#000000",
        stroke_width_px=3,
        subtitle_style="kinetic_word",
        max_words_per_cue=3,
        visual_pace="dynamic_fast",
        ducking_db=-16.0,
        target_loudness_lufs=-14.0,
        banner_style="editorial_pill",
    ),
}


class DesignSystemManager:
    """Gerenciador de Design System e Presets Audiovisuais do AutoShorts."""

    def __init__(self, safe_zone: Optional[SafeZoneSpec] = None) -> None:
        self.safe_zone = safe_zone or SafeZoneSpec()
        self.presets = dict(_NICHE_PRESETS)

    def get_preset(self, niche: str | NicheDesignPreset) -> NicheDesignPreset:
        if isinstance(niche, NicheDesignPreset):
            return niche
        norm = str(niche or "").lower().strip()
        if "noticia" in norm or "mundo" in norm:
            return self.presets["news"]
        if "tech" in norm or "ia" in norm:
            return self.presets["tech"]
        if "game" in norm or "gta" in norm:
            return self.presets["gaming"]
        if "historia" in norm or "story" in norm or "misterio" in norm:
            return self.presets["storytelling"]
        if "cienc" in norm or "curiosidade" in norm or "edu" in norm or "finan" in norm:
            return self.presets["educational"]
        if "podcast" in norm or "corte" in norm:
            return self.presets["podcast"]
        return self.presets.get(norm, self.presets["podcast"])

    def list_presets(self) -> List[Dict[str, Any]]:
        return [asdict(p) for p in self.presets.values()]

    def validate_coordinate_safe(self, x: int, y: int) -> bool:
        """Verifica se uma coordenada (x, y) está situada dentro da zona segura."""
        x1, y1, x2, y2 = self.safe_zone.usable_rect
        return (x1 <= x <= x2) and (y1 <= y <= y2)

    def generate_ass_style_header(self, niche: str | NicheDesignPreset) -> str:
        """Gera o bloco [V4+ Styles] do arquivo Advanced SubStation Alpha (.ass)."""
        p = self.get_preset(niche)
        font = p.primary_font.split(",")[0]
        # Converter hex RRGGBB para ASS BGR com alpha &H00BBGGRR&
        pri_hex = p.primary_color_hex.lstrip("#")
        acc_hex = p.accent_color_hex.lstrip("#")
        pri_ass = f"&H00{pri_hex[4:6]}{pri_hex[2:4]}{pri_hex[0:2]}&"
        acc_ass = f"&H00{acc_hex[4:6]}{acc_hex[2:4]}{acc_hex[0:2]}&"

        return (
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{font},72,{pri_ass},&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,1,0,1,{p.stroke_width_px},1,2,60,60,380,1\n"
            f"Style: Highlight,{font},76,{acc_ass},&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,105,105,2,0,1,{p.stroke_width_px + 1},2,2,60,60,380,1\n"
            f"Style: TopBanner,{font},48,&H00FFFFFF&,&H000000FF&,&H00000000&,&HCC0A1128&,-1,0,0,0,100,100,0,0,1,2,0,8,60,60,220,1\n"
        )
