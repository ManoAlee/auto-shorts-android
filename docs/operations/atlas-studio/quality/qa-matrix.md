# MATRIZ DE GARANTIA DA QUALIDADE AUDIOVISUAL (QA MATRIX)

## 1. Critérios de Avaliação e Limiares

| Dimensão | Métrica / Ferramenta | Limiar Mínimo Aceitável | Ação em Caso de Violação |
|---|---|---|---|
| **Integridade de Mídia** | FFprobe streams | Streams H.264 + AAC presentes | Rejeição imediata (Gate B) |
| **Proporção de Tela** | Aspect Ratio | Vertical 9:16 (1080x1920) | Rejeição imediata (Gate B) |
| **Duração do Vídeo** | Duration (s) | 15s <= t <= 60s (Shorts) | Re-renderização com corte |
| **Loudness Integrado** | EBU R128 | -14.0 LUFS ± 1.0 LUFS | Re-equalização automática |
| **True Peak** | True Peak Limiter | <= -1.0 dBFS | Re-compressão de áudio |
| **Safe Zone de Texto** | Delimitação de Coordenadas | 100% dentro de `(60, 220, 940, 1540)` | Ajuste de margens do arquivo ASS |
| **Telas Pretas / Congeladas** | Amostragem de Frames | 0 frames pretos (> 0.5s) | Rejeição por falha de renderização |
