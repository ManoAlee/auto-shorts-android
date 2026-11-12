# Dossiê Técnico: Engenharia Reversa Completa & Plano de Evolução Next-Gen Cinema
> **Auto Shorts Android — Estúdio Audiovisual Autônomo Mobile (Termux ARM64)**  
> *Autor: Engenheiro-Chefe Antigravity & DeepMind Agentic Team*  
> *Data: Novembro de 2026 | Versão: 2.0-CINEMA-AUDIT*

---

## 1. Mapeamento Arquitetural do Sistema

O **Auto Shorts Android** foi concebido com uma premissa técnica sólida: **zero dependências Python externas obrigatórias** (`requirements.txt` vazio de pacotes de runtime), operando exclusivamente com a biblioteca padrão do Python 3, binários nativos do sistema operacional Android/Linux via Termux (`ffmpeg`, `ffprobe`, `yt-dlp`, `llama-cpp`, `clang`, `espeak`) e banco de dados SQLite embarcado.

```
+-----------------------------------------------------------------------------------+
|                            INTERFACES DE CONTROLE                                 |
|   +--------------------------+  +-------------------+  +-----------------------+  |
|   | Web Studio PWA (:8787)   |  | CLI (main.py)     |  | MCP Server (JSON-RPC) |  |
|   | - Mobile Touch Glassmorf |  | - Autopilot / Cut |  | - Ferramentas de IA   |  |
|   +--------------------------+  +-------------------+  +-----------------------+  |
+-----------------------------------------+-----------------------------------------+
                                          |
+-----------------------------------------v-----------------------------------------+
|                    ORQUESTRAÇÃO & MOTORES CENTRAIS (Python)                       |
|   +------------------------+  +------------------------+  +-------------------+   |
|   | webapp.py              |  | pipeline.py            |  | narrator.py       |   |
|   | - Threading Server     |  | - Longform Ingestion   |  | - Kokoro-82M ONNX |   |
|   | - Async Job Queue      |  | - Segment Cutting      |  | - Cascade TTS     |   |
|   +------------------------+  +------------------------+  +-------------------+   |
|   +------------------------+  +------------------------+  +-------------------+   |
|   | re_engine.py           |  | validator.py           |  | evolution.py      |   |
|   | - YouTube InnerTube    |  | - Luma / Motion QA     |  | - UCB1 Bandit     |   |
|   | - Opus Scorecard 5D    |  | - Signalstats / Audio  |  | - SQLite Store    |   |
|   +------------------------+  +------------------------+  +-------------------+   |
|   +------------------------+  +------------------------+  +-------------------+   |
|   | offline_llm.py         |  | gameplay.py            |  | subtitles.py      |   |
|   | - ARM64 ISA Probe      |  | - B-Roll Multi-Scene   |  | - ASS Karaoke     |   |
|   | - Okapi BM25 RAG       |  | - Brightness Filter    |  | - Kinetic Pacing  |   |
|   +------------------------+  +------------------------+  +-------------------+   |
+-----------------------------------------+-----------------------------------------+
                                          |
+-----------------------------------------v-----------------------------------------+
|                  CAMADA NATIVA DO DISPOSITIVO (Termux / ARM64)                    |
|   +-------------------+  +-------------------+  +-----------------------------+   |
|   | FFmpeg / FFprobe  |  | llama-server      |  | Native C11 (media_audit)    |   |
|   | - libx264         |  | - GGUF Q4_K_M     |  | - ISO-BMFF Box Inspection   |   |
|   | - MediaCodec HW   |  | - ARM64 DotProd   |  | - Watchdog de Processos     |   |
|   +-------------------+  +-------------------+  +-----------------------------+   |
|   +-------------------+  +-------------------+  +-----------------------------+   |
|   | Kokoro ONNX INT8  |  | yt-dlp            |  | Armazenamento UFS Flash     |   |
|   | - espeak-ng       |  | - Stream Extract  |  | - output/                   |   |
|   | - PT-BR Offline   |  | - PO-Token Safe   |  | - assets/gameplay/          |   |
|   +-------------------+  +-------------------+  +-----------------------------+   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Fluxograma Completo de Geração Audiovisual

O sistema possui **dois fluxos fundamentais de geração**:

### Fluxo A: Ingestão de Long-Form (Clipping & Curadoria)
```
Origem (YouTube / Local MP4)
   │
   ▼
downloader.py (yt-dlp + whisper.cpp)
   │
   ▼
transcript.py (Parser VTT/SRT com deduplicação)
   │
   ▼
silence.py (FFmpeg silencedetect)
   │
   ▼
highlights.py (Scoring Heurístico / LLM com sentenças completas)
   │
   ▼
renderer.py (Enquadramento 9:16 - blur_bg / crop)
   │
   ▼
subtitles.py (ASS Karaoke estilizado)
   │
   ▼
validator.py (Inspeção Multimodal de Luma, Motion e Opus 5D)
   │
   ▼
publisher.py (TikTok API + YouTube Shorts)
```

### Fluxo B: Narrativa Sintética, Notícias & Radar Cultural
```
world_news.py / anime_trends.py / radar
   │
   ▼
offline_llm.py / LLM (Roteirização em Atos: Hook, Escalação, Clímax)
   │
   ▼
narrator.py (Kokoro-82M ONNX PT-BR 100% Offline)
   │
   ▼
gameplay.py (B-Roll Dinâmico UCB1 - Multi-Cena a cada 4.2s)
   │
   ▼
renderer.py (Sidechain Audio Ducking -18dB + Legenda ASS)
   │
   ▼
validator.py (Inspeção 5D de Retenção e Contraste)
   │
   ▼
Fila de Publicação Autônoma / Acervo
```

---

## 3. Diagnóstico de Desempenho no Hardware Mobile (Termux ARM64)

### Especificação de Referência (Dispositivo Real Conectado: Samsung Galaxy A55 5G)
- **SoC:** Samsung Exynos 1480 (4nm).
- **CPU:** Octa-Core (4x Cortex-A78 @ 2.75 GHz + 4x Cortex-A55 @ 2.0 GHz).
- **GPU:** Samsung Xclipse 530 (Arquitetura AMD RDNA 2 Mobile).
- **Memória RAM:** 8 GB LPDDR5 (Folga no Termux: ~4.2 GB livres).
- **Extensões ISA ARM64 Detectadas:** `neon`, `fp16`, `dotprod` (`asimddp`), `i8mm`.

### Análise de Gargalos Críticos Mobile:
1. **Memória RAM & LMK (Low Memory Killer):**
   - *Gargalo:* Se o `llama-server` carregar um modelo GGUF > 3GB enquanto o FFmpeg renderiza em 1080p, o kernel Android dispara o LMK e mata o processo do Termux silenciosamente.
   - *Solução Atual:* Limite de modelos GGUF para o tier `qwen2.5-1.5b-q4_k_m` (~1.1 GB em RAM) e threads de inferência travadas em 4 (usando apenas os núcleos A78).
2. **Processamento Térmico & Throttling de CPU:**
   - *Gargalo:* Renderizações de vídeo de 60 segundos com `libx264` em `preset fast` ou `medium` mantêm os 8 núcleos a 100% por ~45s, aquecendo o aparelho a mais de 43°C e ativando throttling térmico (queda de clock de 2.75 GHz para 1.4 GHz).
   - *Solução Atual:* `preset veryfast`, `-threads 4`, resolução mobile nativa 720x1280. Suporte opcional a `-c:v h264_mediacodec` (aceleração de hardware do chip).
3. **Armazenamento Interno (Flash UFS):**
   - *Gargalo:* Vídeos intermediários, áudios `.wav` temporários e frames de inspeção acumulam gigabytes rapidamente.
   - *Solução Atual:* Função `prune_storage()` e exclusão em massa com 1-clique recém-implementada.

---

## 4. Inventário Detalhado de Funcionalidades

| Módulo / Funcionalidade | Estado Atual | Avaliação Técnica | Destino na Evolução |
|:---|:---:|:---|:---|
| **Pipeline de Clipping Longform** | ✅ 100% Operacional | Robusto, com detecção de silêncio e snap de sentenças | Manter como base de ingestão |
| **Legendas ASS Karaoke** | ✅ 100% Operacional | Efeito pop-up suave, destaque amarelo, sem sobreposição | Evoluir para Kinetic Typography |
| **Síntese de Voz Kokoro-82M ONNX** | ✅ 100% Operacional | 100% offline, naturalidade humana, vozes PT-BR | Expandir para multi-vozes por personagem |
| **Busca Semântica / RAG BM25** | ✅ 100% Operacional | Zero dependências, roda em milissegundos no celular | Integrar com banco de conhecimento visual |
| **Auditoria Visual & Luma Gate** | ✅ 100% Operacional | Extração de 5 frames, cálculo de movimento e luma | Base para o Vision QA 2.0 |
| **B-Roll Multi-Cena UCB1** | ✅ 100% Operacional | Troca de cenas a cada 4.2s com bandit adaptativo | **Substituir/Evoluir**: Gameplays por cenas de história |
| **InnerTube & Heatmap Scraper** | ✅ 100% Operacional | Parser nativo de JSON sem dependências externas | Manter para radar de retenção |
| **TikTok & YouTube API** | ✅ 100% Operacional | Upload direto, inbox e agendamento | Manter e polir |
| **Story Engine (Narrativas & Temporadas)** | ⚠️ Não existe | Roteiros atuais são informativos/noticiosos | **Criar na Fase 2** |
| **Director Engine (Planos & Câmera)** | ⚠️ Não existe | FFmpeg usa cortes estáticos e pan genérico | **Criar na Fase 2 / 6** |
| **Character Engine (Identidade Persistente)** | ⚠️ Não existe | Vídeos não possuem personagens consistentes | **Criar na Fase 3** |
| **Anime & Manga Lab (2.5D Parallax)** | 🟡 Blueprint criado | Arquitetura desenhada, filtros FFmpeg mapeados | **Implementar na Fase 4** |
| **Mobile Animation Engine (I2V / Flow)** | ⚠️ Não existe | Apenas vídeo pré-gravado cortado | **Desenvolver na Fase 5** |

---

## 5. Oportunidades Imediatas de Otimização no Código Atual

1. **Remoção da Dependência de Gameplays Baixados:**
   - *Problema:* Atualmente, vídeos sintéticos dependem de baixar gameplays de 500 MB do YouTube (GTA, Minecraft).
   - *Oportunidade:* Gerar animações visuais procedurais, Ken Burns cinematográfico em painéis de mangá e composição gráfica 2.5D sem consumo abusivo de internet móvel.
2. **Modularização de Prompts e Roteiros Estruturados:**
   - *Problema:* Os prompts são strings rígidas espalhadas no código.
   - *Oportunidade:* Criar schemas JSON estruturados com atos, diálogos, emoções de fala e direções visuais para alimentar o motor cinematográfico.
3. **Multi-Voice Dialogue Engine:**
   - *Problema:* Todo vídeo gerado utiliza apenas uma voz monológica contínua.
   - *Oportunidade:* Alternar vozes do Kokoro-82M por personagem (ex: Voz Masculina Herói + Voz Feminina Vilã + Narrador Epico) com mixagem automática.

---

## 6. Plano de Evolução Incremental (Roadmap das 12 Fases)

```
[FASE 1: CONCLUÍDA] ──> Auditoria, Engenharia Reversa e Mapa de Hardware
       │
       ▼
[FASE 2: STORY & DIRECTOR ENGINE] ──> Modelos Narrativos em Atos, JSON estruturado
       │
       ▼
[FASE 3: CHARACTER ENGINE] ──> Fichas de Personagens, Traços Visuais, Consistência
       │
       ▼
[FASE 4: ANIME & MANGA LAB] ──> Pipeline 2.5D, Right-to-Left Pan, Impact Lines
       │
       ▼
[FASE 5: MOBILE ANIMATION] ──> Modelos de difusão/interpolação ultra-leves no Termux
       │
       ▼
[FASE 6: CINEMA & VFX FFMPEG] ──> Shakes, Partículas, Vinhetas e Ducking Multicanal
       │
       ▼
[FASE 7: MULTI-VOICE KOKORO] ──> Troca de Personagens, Efeitos de Rádio e Vozes
       │
       ▼
[FASE 8: RADAR CULTURAL INTEGRADO] ──> AniList + TMDB + RSS em Pautas Automáticas
       │
       ▼
[FASE 9: VISION QA 2.0] ──> Scorecard com Refação Automática de Cenas Falhas
       │
       ▼
[FASE 10: MOBILE OPTIMIZER] ──> Controle Térmico, Vulkan, Threads Dinâmicas
       │
       ▼
[FASE 11: STUDIO PWA V2] ──> Interface de Direção Cinematográfica Mobile
       │
       ▼
[FASE 12: VALIDAÇÃO & SUÍTE] ──> Bateria de 50+ Testes e Benchmark de RAM/Tempo
```
