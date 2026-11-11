# Estudo de Entrega Multi-Portal e Sistema Auto-Evolutivo (`auto-shorts-android`)

## 1. Como Entregar nos Portais (Especificações, APIs, Limites e Riscos)

Baseado na engenharia reversa do `openshorts` (`social_metrics.py`, `cloud/autopilot.py`, `ffmpeg_utils.py`) e nas especificações atuais das APIs oficiais:

| Portal | Método de Entrega Recomendado | Requisitos e Especificações Técnicas | Limites / Quotas | Risco de Ban / Shadowban |
|---|---|---|---|---|
| **YouTube Shorts** | **YouTube Data API v3** (`videos.insert`) ou via agregador (Upload-Post / n8n) | Vertical `9:16`, ideal `30–58s`, `#Shorts` na descrição, áudio `-14 LUFS`, `METADATA_SCRUB` aplicado. | Pool padrão de `10.000` unidades/dia no Google Cloud (`videos.insert` + thumbnails + updates exige auditoria para aumentar cota). | Baixo via OAuth oficial; alto se subir cortes crus sem legenda/edição ("Conteúdo Reutilizado"). |
| **TikTok (Creator Rewards)** | **TikTok Content Posting API** (Inbox Draft ou Direct Post) ou agregador OAuth | **Obrigatório `>= 60s`** (preset `tiktok_rewards`: `62–95s`) para remunerar. MP4/MOV `9:16`, até `1 GB`. Token expira em `24h` (exige refresh). | ~15–25 posts/dia por conta; apps sem App Review só postam em modo `SELF_ONLY` (rascunho privado para revisão final). | Médio se usar automação de browser/UI; baixo usando API oficial / rascunho + postagem manual com áudio/capa. |
| **Instagram Reels** | **Meta Graph API** (`/{ig-user-id}/media` + `media_publish`) | Conta **Profissional (Creator/Business)** vinculada a Página FB. MP4 `9:16`, `<= 100 MB`, **`-movflags +faststart` obrigatório** (`moov` atom no início). | `50–100` posts em janela móvel de 24h; `200` chamadas/hora por token (token longo dura 60 dias). | Baixo via Graph API oficial; exige URL HTTPS temporária para a Meta puxar o MP4. |
| **Kwai & Shopee Vídeo** | **Fila Local Android (`~/storage/shared/Movies/AutoShorts`)** + `publish_pack.json` | Sem API pública aberta para postagem direta em massa no Brasil. Entregar MP4 pronto + texto (título, hashtags, link afiliado) pronto para copiar. | Respeitar cadência humana (2–4 vídeos/dia por conta nova). | Automação por toque/bot no app Android dá ban rápido — entrega assistida por fila é a mais segura. |

### Estratégia Prática de Entrega em 2 Camadas (Sem Risco de Bloqueio)
1. **Camada A — Entrega Local no Celular (`Android MediaStore`):** todo corte gerado é salvo pronto em `output/` (e opcionalmente copiado para `/sdcard/Movies/AutoShorts/` com um `publish_pack.json` contendo título, `hook_title`, legenda, CTA e hashtags).
2. **Camada B — Entrega Automatizada por Webhook/API (`publisher.py`):** se configurado `UPLOAD_POST_API_KEY` (mesmo padrão do `openshorts`) ou `PUBLISH_WEBHOOK_URL` (para o seu próprio **n8n** no `10.0.0.7` / `autom-linux`), o pipeline dispara automaticamente o agendamento respeitando horários de pico no Brasil (`12:00`, `18:30`, `21:00`).

---

## 2. Arquitetura do Sistema Automatizado Avançado que "Evolui e Estuda" (Closed-Loop)

Em vez de um script estático que corta sempre igual, implementamos um ciclo fechado inspirado no protocolo **Mahoraga** (`Observe → Detect → Diagnose → Hypothesize → Test → Apply → Verify → Learn`) em SQLite leve (`src/auto_shorts/evolution.py`):

```text
[1. Geração & Experimento]
   Cada corte registra em SQLite (`shorts_evolution.db`):
   - nicho, plataforma, layout (`blur_bg` | `center_crop` | `split_top_bottom`)
   - faixa de duração (`30-45s`, `45-58s`, `62-75s`, `75-95s`)
   - estilo de hook, palavras-chave usadas e `predicted_score`
         │
         ▼
[2. Entrega Multi-Portal]
   YouTube Shorts / TikTok / Reels / Fila Android
         │
         ▼ (após 24h–72h, respeitando REFRESH_AFTER=20h do openshorts)
[3. Coleta de Telemetria Real]
   - `views`, `avg_watch_pct` (retenção!), `likes`, `comments`, `shares`, `saves`
   - `engagement_score = log1p(views) * (0.5 + avg_watch_pct) + 4*shares + 3*saves`
         │
         ▼
[4. Aprendizado por Multi-Armed Bandit (UCB1)]
   - Calcula qual `layout` e qual `faixa de duração` dão maior retorno por nicho
   - Mantém 80% exploração dos vencedores + 20% teste de novas hipóteses
         │
         ▼
[5. Evolução Automática do Prompt & Pesos]
   - Injeta no prompt da LLM (`highlights.py`) os TOP 3 hooks vencedores reais
     e os padrões que floparam no seu canal para evitar repeti-los.
   - Atualiza automaticamente os pesos de palavras-chave do modo `--offline`.
```

### Por que isso funciona muito bem no Brasil?
1. Cada nicho responde diferente no algoritmo (ex.: em `financas`, `blur_bg` com gráfico/tabela + `62–75s` costuma reter melhor no TikTok Creator Rewards; em `desenvolvimento_pessoal`, `center_crop` + `35–50s` gera mais compartilhamentos no Reels).
2. O sistema **não depende de achismo**: em 2–3 semanas de postagens, o banco local identifica quais hooks, durações e layouts realmente convertem em retenção e views na sua conta.

