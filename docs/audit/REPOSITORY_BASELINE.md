# REPOSITORY BASELINE AUDIT — AUTO SHORTS ANDROID

**Audit Date:** 2026-11-23  
**Commit Baseline:** `3daad86` (`feat(sentinel): implement pre-render multimodal validation harness, 10 quality gates and fix weak news generation`)  
**Branch:** `docs/world-class-repository`  
**Target Repository:** `git@github.com:ManoAlee/auto-shorts-android.git`  
**Primary Target Environment:** Android 14 (ARM64 / aarch64) + Termux Userspace (Exynos 1480 / Samsung Galaxy A55 5G)  
**Secondary/Auxiliary Environments:** Linux ARM64/x86_64, Windows 11 PowerShell

---

## 1. Executive Summary

O **Auto Shorts Android** é um ecossistema autônomo e nativo de ponta a ponta para pesquisa de pautas, engenharia reversa de formatos virais, síntese de roteiros em três atos, geração de voz neural offline, seleção semântica de B-Roll, validação multimodal pré-renderização (Sentinel Pre-Render), queima de legendas animadas em conformidade com safe zones verticais (9:16) e publicação multiplataforma (YouTube Shorts, TikTok e Instagram Reels).

O sistema foi especificamente arquitetado e endurecido contra os limites severos de memória e gerenciamento de processos do Android (Low Memory Killer / OOM killer do Linux Kernel), mantendo consumo de RSS estritamente abaixo de **150MB**, operando sem depender de conexão contínua de terminal SSH e permitindo operação 24/7.

---

## 2. Inventário de Arquivos e Componentes

### 2.1 Código Python (`src/auto_shorts/`)
Total de 62 módulos Python organizados em subsistemas coesos:
- **Core Pipeline:** `pipeline.py`, `renderer.py`, `narrator.py`, `validator.py`, `publisher.py`, `config.py`
- **Pre-Render Multimodal QA:** `sentinel_pre_render/` (`contracts.py`, `title_consistency.py`, `script_intelligence.py`, `semantic_scene_aligner.py`, `storyboard_engine.py`, `preview_renderer.py`, `multimodal_personas.py`, `quality_gates_sentinel.py`, `revision_engine.py`, `orchestrator.py`)
- **Omega CDP Browser Automation:** `omega_cdp/` (`engine.py`, `orchestrator.py`, `approval_gateway.py`, `session_manager.py`, `visual_qa.py`, `adapters/base.py`, `adapters/youtube.py`, `adapters/tiktok.py`, `adapters/instagram.py`)
- **Intelligence & Forensics:** `viral_forensics.py`, `viral_intelligence.py`, `viral_titling.py`, `re_engine.py`, `mahoraga.py`, `evolution.py`
- **Journalism & World News:** `world_news.py`, `deduplication.py`, `horizon_radar.py`
- **Audiovisual & Motion:** `pro_editor_engine.py`, `semantic_visual_engine.py`, `design_system.py`, `subtitles.py`, `silence.py`, `highlights.py`, `gameplay.py`
- **Live Streams:** `live_stream_sniper.py`, `live_clipping_multimodal.py`
- **Web Studio & UI:** `webapp.py`, `frontend/index.html`, `frontend/studio.css`, `frontend/studio.js`, `frontend/tokens.css`
- **CLI & MCP Tools:** `cli.py`, `cli_anything.py`, `autoshorts_mcp.py`, `youtube_studio_mcp.py`

### 2.2 Suíte de Testes Automatizados (`tests/`)
Total de 21 suítes de testes automatizados com cobertura completa:
- `test_sentinel_pre_render.py` (9 testes do Sentinel QA)
- `test_heal_vault_titles.py` (2 testes de autocura de acervo)
- `test_viral_titling.py` (4 testes de titulação contextual)
- `test_news_sanitization.py` (18 testes de sanitização e imunização de fala)
- `test_omega_cdp.py`, `test_omega_integration_harness.py`
- `test_atlas_studio.py`, `test_pro_editor_and_platforms.py`
- `test_cli_anything_and_recovery.py`, `test_pipeline.py`, `test_story_engine.py`

### 2.3 Scripts de Automação & DevOps (`scripts/`)
- `install_termux.sh`, `install_kokoro_ptbr.sh`, `start_webapp.sh`
- `autoshorts_sentinel.ps1`, `start_sentinel_hidden.vbs`
- `heal_vault_titles.py`, `generate_sentinel_short.py`
- `inspect_titles.py`, `inspect_sentinel_report.py`, `test_api_videos.py`

### 2.4 Ativos de Mídia e Design (`assets/`)
- **Fontes Oficiais:** `AlbertSans-ExtraBold.ttf`, `Optimistic_VF_App_Lite.ttf`, `TikTokSans-VF.otf`
- **Color Grading LUTs:** 14 LUTs cinematográficas (`lut_BEAM.png`, `lut_NOIR.png`, `lut_SUPER8.png`, `lut_capcut_base.png`, etc.)
- **Perfis de Voz Neural:** `pt_female_ref.wav`, `pt_male_ref.wav`

---

## 3. Estado de Funcionalidades: Matriz de Confiabilidade

| Subsistema / Funcionalidade | Estado Real | Testes Passando | Ambiente Validado | Observações |
|---|---|---|---|---|
| **Sentinel Pre-Render QA** | 🟢 Totalmente Funcional | Sim (9/9) | Android Termux + Win | 10 Quality Gates ativos, gera HTML Storyboard e proxy |
| **Geração de Roteiro 3 Atos** | 🟢 Totalmente Funcional | Sim (18/18) | Android Termux + Win | Mahoraga 8-Spoke com anti-slop e cadência 130-165 WPM |
| **TTS Neural Offline (Kokoro-82M)** | 🟢 Totalmente Funcional | Sim | Android Termux | Vozes `pf_dora` e `pm_alex` sem dependência de internet |
| **Queima de Legendas CapCut** | 🟢 Totalmente Funcional | Sim | Android Termux + Win | Estilo dinâmico com realce de palavras e safe zones |
| **Alinhamento Visual Semântico** | 🟢 Totalmente Funcional | Sim | Android Termux + Win | Detecção de contradições visuais e variedade de B-Roll |
| **Web Studio SPA (:8787)** | 🟢 Totalmente Funcional | Sim | Android Termux | UI móvel/desktop com tabs de Sentinel, Radar, Vault |
| **CLI-Anything HKUDS** | 🟢 Totalmente Funcional | Sim | Android Termux + Win | Suporte estrito a `--json` estruturado |
| **Publicação TikTok CDP** | 🟡 Parcialmente Funcional | Simulado em testes | Android Termux | Requer sessão do navegador Chromium ativa via CDP |
| **Publicação YouTube OAuth** | 🟡 Parcialmente Funcional | Simulado em testes | Android Termux | Requer `client_secrets.json` configurado pelo usuário |
| **Publicação Instagram Graph** | 🟡 Parcialmente Funcional | Simulado em testes | Android Termux | Requer token de longa duração da Meta |

---

## 4. Riscos Identificados e Mitigações

1. **Low Memory Killer (Android OOM):**
   - *Risco:* Processos com consumo > 300MB de RAM são finalizados pelo Android sem aviso.
   - *Mitigação:* O Sentinel Pre-Render e o renderizador limitam threads do FFmpeg (`-threads 2`), executam personas de revisão sequencialmente e operam com teto de RSS de 150MB.
2. **Thermal Throttling em Renderizações Longas:**
   - *Risco:* CPU móvel superaquece se múltiplos vídeos em 1080x1920 forem gerados em sequência.
   - *Mitigação:* Modo `FULL_PROXY_PREVIEW` em 360x640 @ 15fps (< 3s de CPU) para pré-visualização, renderizando 1080p somente após aprovação do Gate 10.
3. **Dependência de Stubs de Notícias:**
   - *Risco:* RSS de buscadores fornecendo apenas títulos, gerando vídeos curtos vazios.
   - *Mitigação:* Priorização de portais com matérias completas e barreira de entrada mínima de 28 palavras / 160 caracteres.
