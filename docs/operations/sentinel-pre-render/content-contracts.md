# Contratos de Conteúdo — AUTO SHORTS SENTINEL

## Visão Geral

Todos os módulos do Sentinel operam sobre contratos formais declarados em `src/auto_shorts/sentinel_pre_render/contracts.py`. Estes contratos garantem que o roteiro, metadados, ativos de mídia e laudos de validação possuam tipagem estrita e validação determinística.

---

## 1. Contratos Principais

### `ContentBrief`
Define a promessa editorial, canal, público-alvo e roteiro integral do vídeo.

```python
@dataclass
class ContentBrief:
    project_id: str
    channel_name: str
    target_platform: str          # "youtube_shorts", "tiktok", "instagram_reels"
    title: str
    category: str                 # "tech_ia", "futebol", "games", "curiosidades", etc.
    full_script: str
    target_duration_sec: float = 45.0
    hook_promise: str = ""
    key_claims: List[str] = field(default_factory=list)
    call_to_action: str = ""
    target_audience: str = "geral"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### `SceneContract`
Especifica cada batida visual e de áudio individual do vídeo.

```python
@dataclass
class SceneContract:
    scene_id: int
    narration_text: str
    expected_duration_sec: float
    visual_intent: str
    asset_path: Optional[str] = None
    asset_tags: List[str] = field(default_factory=list)
    motion_type: str = "zoom_in"   # "pan_left", "pan_right", "zoom_in", "zoom_out", "static"
    subtitle_cues: List[str] = field(default_factory=list)
    transition_in: str = "cut"
    transition_out: str = "cut"
    is_hook_scene: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### `StoryboardManifest`
Agrupa o `ContentBrief` e a sequência ordenada de `SceneContract`s que compõem o produto audiovisual.

```python
@dataclass
class StoryboardManifest:
    brief: ContentBrief
    scenes: List[SceneContract]
    created_at: str
    total_scenes: int
    total_estimated_duration_sec: float
    manifest_version: str = "1.0.0"
```

---

## 2. Contratos de Validação e Relatórios

### `TitleConsistencyMatrix`
Rastreia a correspondência entre promessas do título e a evidência concreta no vídeo:

```python
@dataclass
class TitleConsistencyMatrix:
    title: str
    claimed_entities: List[str]
    numerical_promises: List[int]
    script_delivered_items: int
    topic_matches: List[str]
    missing_entities: List[str]
    clickbait_severity: float     # 0.0 (puro) a 1.0 (clickbait enganoso)
    consistency_score: float      # 0 a 100
    is_consistent: bool
    evidence_trail: List[Dict[str, Any]]
```

### `SentinelReport`
Dossiê completo de validação emitido após a passagem pelos 10 Quality Gates:

```python
@dataclass
class SentinelReport:
    project_id: str
    timestamp: str
    overall_status: GateStatus    # PASS, FAIL, REQUIRES_REVIEW
    overall_score: float          # 0 a 100
    gate_results: Dict[str, GateResult]
    title_matrix: Optional[TitleConsistencyMatrix]
    persona_reviews: List[PersonaReview]
    storyboard_path: Optional[str]
    preview_path: Optional[str]
    auto_revised: bool = False
    revision_count: int = 0
    recommendations: List[str] = field(default_factory=list)
    raw_metrics: Dict[str, Any] = field(default_factory=dict)
```
