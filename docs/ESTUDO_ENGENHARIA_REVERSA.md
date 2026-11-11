# Estudo de Engenharia Reversa e Arquitetura Mobile (`auto-shorts-android`)

## 1. Diagnóstico do Ambiente de Engenharia Reversa (`/rea-doctor`)

A inspeção via `rea doctor` (v4.0.1) e `rea capabilities` no host Windows (`win32 x64`, Node `24.18.0`) registrou:
- **Providers ativos:** `rea-artifact-graph` e `rea-dotnet-static` (total de 69 comandos CLI e 116 tools MCP).
- **Providers ausentes (não necessários para análise de código-fonte aberto):** `ghidra` (`GHIDRA_INSTALL_DIR` não configurado) e `hopper` (`HOPPER_LAUNCHER_PATH` ausente).
- **Observação:** como os 6 repositórios de referência são open-source (Kotlin/Java, Python, C/C++), a engenharia reversa foi conduzida diretamente sobre os módulos-fonte clonados em `refs/`, combinando análise estática de pipeline, contratos FFmpeg e restrições reais do hardware alvo.

### Hardware e Ambiente Alvo (Validado via SSH)
- **Dispositivo:** Samsung Galaxy A55 5G (`SM-A556E`), Android 16, `aarch64` (LSE `atomics` nativo)
- **RAM / Swap:** `7.3 GiB` RAM + `8.0 GiB` ZRAM/Swap
- **Armazenamento:** `58 GB` livres em `/data/data/com.termux/files`
- **Toolchain Termux:** `ffmpeg 8.1.2` (com `libass`, `libx264`, `libx265`, `libdav1d`, `harfbuzz`, `fontconfig`), `python 3.13`, `python-yt-dlp`, `codex-cli 0.122.0`, `agy 1.5.4`, `tmux 3.6b`.

---

## 2. Análise Técnica dos 6 Repositórios de Referência

| Repositório | Stack Principal | O que extraímos para o projeto | O que descartamos (e por quê) |
|---|---|---|---|
| **LibreCuts** (`refs/LibreCuts`) | Kotlin / Android + `FFmpegKit` | Uso explícito de `fontfile=` no filtro `drawtext` (evita erro fatal `Option 'font' not found`), fallback automático entre `h264_mediacodec` e `libx264`, cálculo de dimensões pares (`trunc(iw/2)*2`). | UI manual em XML/Activity; nosso motor roda em pipeline CLI/batch no Termux. |
| **losslesscut-android** (`refs/losslesscut-android`) | Kotlin Multi-Module + `MediaExtractor` / `MediaMuxer` | Conceito de corte *lossless* por keyframe e **Smart Cut** (`SilenceDetectionUseCase`: detecção de silêncio por energia RMS e corte sem perda antes da renderização final). | APIs exclusivas de UI Android (`SAF`/`MediaStore`/`ExploreByTouchHelper`), substituídas por `ffmpeg silencedetect` + filesystem local no Termux. |
| **openshorts** (`refs/openshorts`) | Python + FastAPI + Gemini + MediaPipe + FFmpeg | 1) `METADATA_SCRUB` (`-map_metadata -1 -map_chapters -1 -map_metadata:s:v -1 -map_metadata:s:a -1`) para remover assinaturas como `"produced by Google Inc."`;<br>2) `LOUDNORM_FILTER = "loudnorm=I=-14:TP=-2.0:LRA=11"` (calibrado para TikTok/Reels/Shorts evitando clipping inter-sample AAC);<br>3) Escape seguro de filtros ASS (nunca usar apóstrofos no nome do arquivo `.ass`);<br>4) Layouts 9:16 (`TRACK`, `GENERAL` blur-bg, `SPLIT` dois falantes empilhados);<br>5) Prevenção de dupla legenda (`burned_subtitles.py`). | Stack pesada de servidor (Docker, Postgres, S3, Remotion, MediaPipe/PyTorch com 8GB+ RAM), inviável para rodar em container no Android. |
| **AI-Youtube-Shorts-Generator** (`refs/AI-Youtube-Shorts-Generator`) | Python + `yt-dlp` + Whisper + LLM + OpenCV | 1) Prompt estruturado com os **8 sinais de viralidade** (`HOOK`, `EMOTIONAL PEAKS`, `OPINION BOMBS`, `REVELATION`, `CONFLICT`, `ONE-LINERS`, `STORY PEAKS`, `PRACTICAL VALUE`);<br>2) Chunking de vídeos >30 min em blocos de 20 min com overlap de 60s;<br>3) Deduplicação por sobreposição baseada em score;<br>4) Cache de transcrição `.srt` por `mtime`. | `faster-whisper` (`ctranslate2`) e `opencv-python` pesados em Termux ARM64; substituídos por legendas `yt-dlp` / `whisper.cpp` / API + crops FFmpeg nativos. |
| **whisper.cpp** (`refs/whisper.cpp`) | C/C++ (GGML, ARM64 NEON) | Transcrição 100% offline rápida no Galaxy A55 compilando com `-DGGML_NO_OPENMP=ON` e modelos leves (`tiny`/`base`/`small` quantizados), gerando `.srt` e `.json` word-level sem PyTorch. | Modelos `large-v3` no celular (lentos e causam aquecimento). |
| **auto-editor** (`refs/auto-editor`) | Python + FFmpeg | Técnica de jump-cut automático removendo pausas mortas/silêncios para elevar a retenção dos primeiros segundos em Reels/Shorts/TikTok. | Dependências científicas pesadas se compiladas sem wheels ARM64; reimplementamos a detecção via `ffmpeg -af silencedetect` em Python puro. |

---

## 3. Arquitetura Sintetizada (`auto-shorts-android`)

```text
[URL YouTube ou MP4 Local]
        │
        ▼ (yt-dlp + extração de legenda PT-BR / whisper.cpp / API)
[Transcrição Normalizada + Cache .srt/.json]
        │
        ▼ (Chunking >30min + 8 Sinais de Viralidade + Filtro de Duração por Plataforma)
[Candidatos Ranqueados (Score + Hook + Motivo) + Dedupe]
        │
        ▼ (Opcional: ffmpeg silencedetect -> remoção de pausas > 0.65s)
[Intervalos Otimizados para Retenção]
        │
        ▼ (Gerador .ASS estilo Karaokê/Bloco + Nome de Arquivo Seguro sem Apóstrofos)
[Legendas Dinâmicas .ass]
        │
        ▼ (FFmpeg 9:16: blur_bg / center_crop / split + drawtext hook + loudnorm -14 LUFS + metadata scrub)
[MP4 Final 9:16 Pronto para TikTok Creator Rewards / YouTube Shorts / Reels]
```

### Decisões Específicas para Rodar no Celular (Samsung A55 / Termux)
1. **Zero dependência de PyTorch/CUDA/Docker:** apenas `ffmpeg` (nativo do Termux), `yt-dlp` e Python puro (+ `whisper.cpp` opcional em C++ nativo).
2. **Transcrição em 3 camadas (custo e bateria mínimos):**
   - Camada 1: Baixa legendas automáticas/manuais `pt`/`pt-BR` do YouTube via `yt-dlp` (instantâneo, zero CPU).
   - Camada 2: `whisper.cpp` local compilado para ARM64 (`whisper-cli`) se for vídeo local sem legenda.
   - Camada 3: Fallback via API (OpenAI/Groq Whisper) ou `.srt` pré-existente.
3. **Presets térmicos:** opção `--quality mobile` (`720x1280`, `-preset veryfast`, `-crf 23`) para processar em lote sem superaquecer o celular, e `--quality high` (`1080x1920`, `-preset fast`, `-crf 19`) quando ligado no carregador.
4. **Higienização anti-reuso:** `METADATA_SCRUB` + `loudnorm=I=-14:TP=-2.0:LRA=11` + hook textual no topo + legendas `.ass` queimadas + reenquadramento 9:16 (`blur_bg` ou `split_top_bottom`).

