# Motores CDP Nativos, Analytics Multiplataforma e Piloto Automático 24/7

Documentação técnica e operacional dos módulos de publicação direta via **Chromium CDP nativo no Termux**, **MCP otimizado**, **Analytics & Radar Global** e **Piloto Automático**.

---

## 1. Visão Geral da Arquitetura

```mermaid
flowchart LR
    A[Acervo output/*.mp4 + .publish.json] --> B{smart_autopublish.py}
    B -->|TIKTOK_PUBLISH_MODE=cdp| C[tiktok_cdp.py\nChromium CDP aarch64]
    B -->|YOUTUBE_PUBLISH_MODE=cdp| D[youtube_cdp.py\nChromium CDP aarch64]
    D -->|login_required / fallback| E[publisher.py\nYouTube Data API v3]
    B -->|IG_USERNAME / Graph API| F[publisher.py\nInstagram Reels + Destaques]
    A --> G[platform_analytics.py\nAnalytics + Radar Global]
    G --> H[/analytics WCAG AA UI\n& /api/analytics/platforms]
    G --> I[autoshorts_mcp.py\nCache _REGISTRY_CACHE]
```

---

## 2. Publicação Nativa via Chromium CDP (Termux `aarch64`)

No Termux/Android, o driver Node do Playwright falha com `Unsupported platform: android`. A solução adotada usa **Python puro + WebSocket RFC 6455 (`CDPClient`)** conectando diretamente ao `chromium-browser` nativo (`pkg install -y x11-repo chromium`).

### 2.1 TikTok Studio Web (`src/auto_shorts/tiktok_cdp.py`)

- **Sessão persistente:** cookies `.tiktok.com` salvos em `output/tiktok_cookies.json` via `POST /api/tiktok/cdp/cookies` e renovados automaticamente a cada execução (`_sync_live_cookies` via `Network.getAllCookies`).
- **Otimização de legenda para o algoritmo (`_build_tiktok_caption`):**
  - Remove URLs externas (`youtube.com`, `youtu.be`) e hashtags concorrentes (`#reels`, `#reelsbrasil`, `#shorts`, `#youtubeshorts`).
  - Mantém gancho SEO curto (`<= 240` caracteres), adiciona CTA de comentário/salvamento e 5 hashtags segmentadas por nicho + `#fyp #tiktokbrasil`.
- **Inserção segura no editor Draft.js:** utiliza `Input.dispatchKeyEvent` (`Ctrl+A` + `Backspace`) seguido de `Input.insertText` em linha única (evita o erro `"Something went wrong"` causado por `document.execCommand` com quebras de linha).
- **Publicação em lote aquecida (`publish_batch_to_tiktok_cdp`):** abre o Chromium uma única vez, injeta cookies e publica múltiplos MP4s na mesma sessão com polling rápido (`0.5s`–`1.0s`).
- **Keepalive (`keepalive_tiktok_cdp`):** reabre o Studio brevemente e persiste cookies renovados.

### 2.2 YouTube Studio Web (`src/auto_shorts/youtube_cdp.py`)

- Reutiliza `CDPClient`, `find_chromium_binary`, `_pick_free_port` e `_wait_cdp_page_ws` de `tiktok_cdp.py`.
- **Contorno de detecção de navegador incompatível:** inicia o Chromium com User-Agent desktop (`Chrome/131.0.0.0`) e navega via `https://www.youtube.com/upload` (tratando `RuntimeError` transitório durante o redirect cross-origin para `studio.youtube.com`).
- **Metadados & Studio:** preenche título (`<= 95` chars), descrição com `#Shorts`, marca `VIDEO_MADE_FOR_KIDS_NOT_MFK`, opção de conteúdo alterado (`ALTERED_CONTENT_NO`/`YES`) e visibilidade (`PUBLIC`/`UNLISTED`/`PRIVATE`).
- **Trava de integridade:** só grava `pack["youtube"]` em `.publish.json` quando extrai um `video_id` real (`youtu.be/<id>` ou `/shorts/<id>`).
- **Fallback automático (`publisher.py`):** se `YOUTUBE_PUBLISH_MODE=cdp` retornar `login_required`, `skipped_unconfigured` ou `error` e houver OAuth (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`), `publish_pack_to_youtube` faz fallback automático para a YouTube Data API v3.

### 2.3 Proteção contra Android Phantom Process Killer & Quedas de SSH

- Flags obrigatórias no Chromium em Android 12+: `--renderer-process-limit=1`, `--disable-background-networking`, `--disable-extensions`, `--disable-sync`, `--mute-audio`, `--disable-dev-shm-usage`.
- Limpeza automática de locks (`SingletonLock`, `SingletonSocket`, `SingletonCookie`) antes de iniciar o navegador.
- No Termux: `termux-wake-lock` ativo + `sshd_config` com `ClientAliveInterval 15`, `ClientAliveCountMax 6`, `TCPKeepAlive yes`, `MaxStartups 30:30:60`.

---

## 3. Servidor MCP Otimizado (`src/auto_shorts/autoshorts_mcp.py`)

- **Cache de registro (`_REGISTRY_CACHE`):** indexado por `(out_dir, mtime de mcp_reified_tools.json)`, evitando reimportar `youtube_studio_mcp` a cada requisição (`tools/list` caiu de `42.71 ms` para `0.04 ms` no Termux; `tiktok.cdp_status` em `2.97 ms`).
- **Ferramentas adicionadas:**
  - `tiktok.cdp_status`, `tiktok.publish_batch`, `tiktok.keepalive`
  - `youtube.cdp_status`, `youtube.publish_batch`
  - `analytics.platforms`, `trends.global`
- `_is_tiktok_configured` e `_is_youtube_configured` reconhecem automaticamente `TIKTOK_PUBLISH_MODE=cdp` e `YOUTUBE_PUBLISH_MODE=cdp` tanto no MCP quanto em `webapp.py`.

---

## 4. Analytics Multiplataforma, Radar Global e UI Acessível

- **`src/auto_shorts/platform_analytics.py`:**
  - `build_cross_platform_analytics(out_dir)`: agrega todos os `.publish.json` (total, aprovados, `quality_score` médio, `algo_score` médio, duração média, distribuição por nicho, status TikTok/YouTube/Instagram) + playbook do algoritmo e recomendações automáticas.
  - `fetch_global_trends_radar(niche)`: coleta tendências em tempo real de **Google Trends RSS (BR e US)**, feeds virais de **X/Twitter**, **Reddit** (`worldnews`, `technology`, `anime`) e **Hacker News**, classificando por nicho e sugerindo ganchos.
- **`src/auto_shorts/analytics_ui.py`:**
  - Servida em `GET /analytics` (com botão **Analytics** no cabeçalho de `src/auto_shorts/frontend/index.html`).
  - Acessibilidade WCAG AA: skip link, `role="tablist"`/`role="tab"`, `aria-live="polite"`, alvos de toque `>= 44px`, contraste alto e grid Bento responsivo.
- **Endpoints HTTP em `src/auto_shorts/webapp.py`:**
  - `GET /analytics`
  - `GET /api/analytics/platforms`
  - `GET /api/trends/global?niche=all`
  - `GET /api/tiktok/cdp/status` e `POST /api/tiktok/cdp/cookies`
  - `GET /api/youtube/cdp/status` e `POST /api/youtube/cdp/cookies`

---

## 5. Operação no Termux & Testes

### Variáveis de ambiente (`.env`)
```env
AUTO_PILOT_ENABLED=1
WIFI_ONLY=1
TIKTOK_PUBLISH_MODE=cdp
YOUTUBE_PUBLISH_MODE=cdp
```

### Serviços `runit` no Termux
```bash
SVDIR=/data/data/com.termux/files/usr/var/service sv status autoshorts autoshorts-web autoshorts-tunnel
SVDIR=/data/data/com.termux/files/usr/var/service sv restart autoshorts autoshorts-web
```

### Validação automatizada
```bash
python -m pytest auto-shorts-android/tests --basetemp=auto-shorts-android/.pytest_tmp -q
```
Cobertura adicionada em `tests/test_pipeline.py` para cookies/status/lote CDP (TikTok e YouTube), otimização de legenda para o algoritmo do TikTok, cache de registro MCP, detecção de modo CDP no `webapp.py`, analytics multiplataforma, radar de tendências offline-safe e acessibilidade do painel `/analytics`.
