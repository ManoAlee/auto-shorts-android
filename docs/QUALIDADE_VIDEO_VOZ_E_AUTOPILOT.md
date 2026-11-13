# Qualidade de voz, vídeo e publicação automática

Este documento descreve os gates e o fluxo atual para produzir Shorts narrados e encaminhá-los às plataformas. “Automático” significa que o scheduler processa itens elegíveis respeitando configuração, sessão autenticada, conectividade e limites locais; não garante aprovação nem entrega pelas plataformas.

## Produção narrada

1. A entrada é transformada em roteiro e metadados. Notícias sem resumo factual suficiente e matérias que são apenas listas de compras/ofertas são rejeitadas pelo radar para evitar narração genérica ou afirmações sem fonte.
2. O narrador normaliza texto em PT-BR e sintetiza por blocos. No Android, Kokoro ONNX é o caminho offline. A voz configurada como Thalita usa a voz Kokoro `pf_dora`; a telemetria deve mostrar o identificador efetivamente usado, não apenas o nome comercial da configuração. A taxa é limitada a uma faixa segura para o runtime Android e pausas entre frases preservam cadência.
3. O pipeline cria vídeo vertical 9:16 com cenas de apoio escolhidas pelo nicho. A seleção de B-roll limita fundos incompatíveis com o tema de notícias e IA/tecnologia; a rotação UCB1 é baseada na avaliação técnica disponível, e não deve ser interpretada como prova de preferência do público.
4. Legendas e roteiro são comparados antes da publicação. Para itens marcados como `narrated_original`, cobertura abaixo do limite configurado (85%) bloqueia a entrada na fila. Assim, legenda ausente ou muito divergente não passa como conteúdo pronto.
5. A validação de mídia e o Opus Scorecard complementam os gates de texto. Eles ajudam a detectar problemas técnicos e visuais; uma nota automática não substitui revisão editorial, direitos de uso ou confirmação de que o conteúdo representa corretamente a fonte.

## Metadados por plataforma

O sidecar `.publish.json` pode manter campos específicos para evitar reaproveitar uma legenda incompatível entre redes:

| Campo | Uso |
| --- | --- |
| `tiktok_caption` | Legenda preparada para TikTok. |
| `instagram_caption` | Legenda preparada para Instagram. |
| `youtube_title` | Título do Short no YouTube. |
| `youtube_description` | Descrição do Short no YouTube. |

Os publicadores usam os metadados próprios quando disponíveis e preservam fallback para os campos legados. Confira título, descrição, hashtags, origem e configurações de audiência antes de ampliar uma campanha.

## Scheduler e publicação

- O scheduler e o autopublish são configuráveis pela API/UI. O modo automático só publica conteúdo que esteja na fila, tenha passado pelos gates e esteja liberado pelos controles de cadência e limites diários.
- O ciclo respeita cooldown e limites configurados por plataforma. Um item em espera continua pendente; uma chamada ao ciclo não significa que houve publicação.
- TikTok e YouTube podem usar seus fluxos CDP nativos, que dependem do Chromium e de uma sessão válida no dispositivo. O YouTube também dispõe de integração pela Data API conforme configuração.
- O adaptador de Instagram presente neste projeto usa `instagrapi`; ele não é a Meta Graph API oficial. A disponibilidade depende de sessão e comportamento do serviço, e deve ser monitorada.
- `WIFI_ONLY=1`, quando habilitado e suportado no Termux, bloqueia tentativas fora de Wi-Fi. Erros de autenticação ou listagem do Google Drive pausam o ciclo relacionado; não são tratados como pasta vazia.
- Autopublicação não assegura alcance, taxa de entrega, ausência de restrições ou aprovação da plataforma. Use as interfaces oficiais e respeite as regras, direitos autorais, limites e permissões de cada conta.

## Diagnóstico e operação

Antes de investigar uma falha, confira estado do scheduler, fila e sidecar, logs do publicador, rede/Wi-Fi, validade da sessão e limites de cadência. Para Drive, valide o remote `rclone` e as permissões de pasta. Nunca registre tokens, cookies, `rclone.conf` ou segredos nos logs ou no Git.

Uma rodada completa da suíte local passou com 101 testes. No Termux, os 18 testes focados de qualidade e integração Drive passaram; `compileall` também passou. A suíte completa do telefone não foi aprovada: um teste que inicia Chromium/CDP falhou porque o endpoint CDP não abriu em uma porta efêmera. Portanto, a regressão CDP no aparelho continua pendente de validação em ambiente com Chromium disponível.

Para executar as verificações locais:

```bash
python -m pytest tests -q
node --check src/auto_shorts/frontend/studio.js
```

Documentação complementar: [IA local e Google Drive no Termux](IA_E_GOOGLE_DRIVE_NO_TERMUX.md) e [CDP, analytics e piloto automático](CDP_ANALYTICS_E_PILOTO_AUTOMATICO.md).
