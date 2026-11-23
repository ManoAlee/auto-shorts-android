# AUTO SHORTS SENTINEL — Pre-Render Multimodal Validation & Creative Intelligence Harness

## Visão Geral e Missão

O **AUTO SHORTS SENTINEL** é o subsistema de inteligência criativa, direção de arte e garantia de qualidade (QA) multimodal pré-renderização do **Auto Shorts**.

Seu papel fundamental é atuar como um **Diretor Criativo, Editor Sênior de Vídeo e Auditor Multimodal** antes de qualquer gasto de recursos computacionais com a renderização final em alta definição (1080x1920).

```
                                  +------------------------------------+
                                  |    ROTEIRO & PACOTE CRIATIVO       |
                                  | (ContentBrief + SceneContracts)    |
                                  +-----------------+------------------+
                                                    |
                                                    v
                                  +------------------------------------+
                                  |        SENTINEL PRE-RENDER         |
                                  |       ORCHESTRATION ENGINE         |
                                  +-----------------+------------------+
                                                    |
         +------------------------------------------+------------------------------------------+
         |                                          |                                          |
         v                                          v                                          v
+------------------+                       +------------------+                       +------------------+
|  CONSISTÊNCIA    |                       |  INTELIGÊNCIA DE |                       |   ALINHAMENTO    |
|   TÍTULO-CONTEÚDO|                       |  ROTEIRO E ARCO  |                       | VISUAL-SEMÂNTICO |
+--------+---------+                       +--------+---------+                       +--------+---------+
         |                                          |                                          |
         +------------------------------------------+------------------------------------------+
                                                    |
                                                    v
                                  +------------------------------------+
                                  |   10 QUALITY GATES MULTIMODAIS     |
                                  +-----------------+------------------+
                                                    |
                         +--------------------------+--------------------------+
                         | [FAIL / REVISE]                                     | [PASS >= 75%]
                         v                                                     v
          +-----------------------------+                       +-----------------------------+
          |   EVIDENCE-GUIDED AUTO-     |                       |     STORYBOARD & PROXY      |
          |       REVISION ENGINE       |                       |        VERIFICADOS          |
          +--------------+--------------+                       +--------------+--------------+
                         |                                                     |
                         +----------> (Re-validação)                           v
                                                                +-----------------------------+
                                                                |       RENDER FINAL HQ       |
                                                                |       1080x1920 @ 30fps     |
                                                                +-----------------------------+
```

---

## Capacidades Chave

1. **Validação Rigorosa de Título vs Conteúdo:**
   - Extração de promessas numéricas (ex: "5 Dicas", "3 Erros").
   - Mapeamento estático: `TITLE_CLAIM -> SCRIPT_SEGMENT -> VISUAL_EVIDENCE -> TIMESTAMP`.
   - Eliminação de clickbait descolado da realidade do vídeo.
2. **Inteligência de Roteiro e Análise de Arco:**
   - Potência dos primeiros 3 segundos (retenção de audiência).
   - Verificação dos 3 atos (Gancho, Desenvolvimento, Resolução/CTA).
   - Ritmo e cadência calculados em Palavras Por Minuto (WPM ideal: 130–165 WPM em PT-BR).
   - Filtro anti-slop para clichês genéricos de IA.
3. **Alinhamento Visual-Semântico de Cenas:**
   - Comparação semântica e por radicais entre narração e tags dos ativos de mídia.
   - Detecção de contradições grotescas (ex: falar de hardware de computadores exibindo praia ensolarada).
   - Penalização de ativos repetidos em cenas consecutivas.
4. **Storyboard-First & Proxy Rendering de Custo Mínimo:**
   - 5 modos de pré-visualização progressiva: `STORYBOARD_ONLY`, `SCENE_PREVIEW`, `AUDIO_SYNC_PREVIEW`, `FULL_PROXY_PREVIEW` (360x640 @ 15fps em < 3s) e `FINAL_RENDER`.
   - Storyboard responsivo em HTML gerado instantaneamente com cards de cena, narração e safe zones.
5. **Safe Zones para Plataformas Verticais (9:16):**
   - Linting determinístico de legendas contra áreas de colisão da interface do YouTube Shorts, TikTok e Instagram Reels.
   - Reflow automático de linhas com mais de 34 caracteres.
6. **Autocorreção Guiada por Evidências:**
   - Reajuste automático de contagem do título (ex: de "5 Dicas" para "3 Dicas Reais").
   - Quebra inteligente de legendas em limites de palavras.
   - Substituição automática de mídias contraditórias por ativos do acervo.

---

## Estrutura do Módulo

O código-fonte do subsistema reside em `src/auto_shorts/sentinel_pre_render/`:

```
src/auto_shorts/sentinel_pre_render/
├── __init__.py                  # Exportação da API pública do Sentinel
├── contracts.py                 # Contratos Dataclass (ContentBrief, SceneContract, etc.)
├── title_consistency.py         # Motor de consistência Título <-> Conteúdo
├── script_intelligence.py       # Motor de análise de roteiro, gancho e WPM
├── semantic_scene_aligner.py    # Motor de alinhamento visual-semântico
├── storyboard_engine.py         # Gerador de storyboards e HTML inspection boards
├── preview_renderer.py          # Modos de preview de baixo custo e linting de safe-zone
├── multimodal_personas.py       # 8 Personas sequenciais de revisão especializada
├── quality_gates_sentinel.py    # Motor de avaliação dos 10 Quality Gates
├── revision_engine.py           # Motor de autocorreção em loop fechado
└── orchestrator.py              # Orquestrador mestre ponta a ponta
```

---

## Como Executar

### 1. Via Linha de Comando (CLI-Anything)

O CLI-Anything do Auto Shorts inclui o comando `sentinel` com saídas estritamente estruturadas em `--json`:

```bash
# Verificar status do subsistema
python -m auto_shorts.cli_anything sentinel status --json

# Validar um pacote criativo existente
python -m auto_shorts.cli_anything sentinel validate --brief output/sentinel/sample_brief.json --json

# Executar validação com geração de proxy rápido
python -m auto_shorts.cli_anything sentinel validate --brief output/sentinel/sample_brief.json --preview-mode FULL_PROXY_PREVIEW --json
```

### 2. Via Web Studio UI (`:8787`)

O Sentinel Pre-Render está integrado ao painel operacional do estúdio:
- **Aba:** `Sentinel QA Pre-Render` (`#tab-sentinel`)
- **API Endpoints:**
  - `GET /api/sentinel/status`: Retorna prontidão dos motores e contadores de auditoria.
  - `GET /api/sentinel/report?project_id=<id>`: Obtém o laudo completo em JSON.
  - `POST /api/sentinel/validate`: Dispara a validação prévia de um pacote criativo com suporte a `auto_revise=true`.
