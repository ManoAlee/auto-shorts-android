# Renderizador de Pré-Visualizações e Safe Zones — AUTO SHORTS SENTINEL

## 1. Modos de Pré-Visualização Graduais

O `LowCostPreviewEngine` (`src/auto_shorts/sentinel_pre_render/preview_renderer.py`) oferece cinco modos de geração conforme a necessidade de custo e velocidade:

| Modo | Custo de CPU | Resolução | FPS | Uso Indicado |
|---|---|---|---|---|
| `STORYBOARD_ONLY` | Quase zero (<0.1s) | N/A (HTML) | 0 | Validação textual e alinhamento visual preliminar |
| `SCENE_PREVIEW` | Mínimo (~0.5s) | 360x640 | 15 | Inspeção de uma cena isolada que sofreu alteração |
| `AUDIO_SYNC_PREVIEW`| Baixo (~1.2s) | 360x640 | 15 | Checagem de sincronia da locução com troca de imagens |
| `FULL_PROXY_PREVIEW` | Baixo (~2.8s) | 360x640 | 15 | Revisão completa do vídeo antes de aprovar render HQ |
| `FINAL_RENDER` | Padrão (~25s) | 1080x1920 | 30/60 | Renderização definitiva para upload nas redes |

---

## 2. Especificação de Safe Zones para Formato Vertical (9:16)

As plataformas móveis (TikTok, YouTube Shorts e Instagram Reels) sobrepõem elementos fixos de interface sobre o vídeo:
- Topo: Barra de status do sistema, abas "Seguindo / Para Você" e botão de busca.
- Direita: Botões de Avatar, Curtir, Comentários, Salvar e Compartilhar.
- Base: Título do vídeo, nome de usuário, descrição e nome da música em rotação.

### `SafeZoneSpec`
```python
@dataclass
class SafeZoneSpec:
    platform: str
    top_margin_px: int = 150       # Reserva de topo
    bottom_margin_px: int = 280    # Reserva de base
    right_margin_px: int = 120     # Reserva lateral direita (ícones sociais)
    left_margin_px: int = 40       # Margem de respiro esquerda
    max_line_length_chars: int = 34
    max_lines_per_cue: int = 2
```

O linter de legendas analisa cada linha gerada para o Short. Linhas que ultrapassam 34 caracteres provocam quebra e estouro de safe zone, sendo imediatamente reprovadas no Gate 05.
