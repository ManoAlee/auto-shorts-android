# Catálogo de Ferramentas Open-Source (GitHub) para o Ecossistema

Além dos 6 repositórios clonados em `refs/` (`LibreCuts`, `losslesscut-android`, `openshorts`, `AI-Youtube-Shorts-Generator`, `whisper.cpp`, `auto-editor`), estas ferramentas open-source completam a pilha para **roteiros faceless, narração em PT-BR (inclusive teorias de animes/mangás), agendamento multi-portal e orquestração**:

## 1. Narração e Roteiro Faceless (Ideais para Animes, Teorias e Curiosidades)

| Projeto / Pacote | O que faz | Roda direto no Termux (Galaxy A55)? | Caso de Uso Principal |
|---|---|---|---|
| **`edge-tts`** (`rany2/edge-tts`) | Biblioteca Python pura que gera áudio neural gratuito (ex.: `pt-BR-AntonioNeural`, `pt-BR-FranciscaNeural`) com timestamps SRT sem chave paga | **Sim (leve, Python puro)** | Narrar teorias de anime/mangá, notícias de tecnologia e histórias faceless no celular (já integrado em `src/auto_shorts/narrator.py`) |
| **`Chatterbox`** (`resemble-ai/chatterbox`) | TTS open-source (MIT) com controle de **exagero emocional** e clonagem com ~10s de áudio, compatível com português e API OpenAI (`CHATTERBOX_API_URL`) | Servidor GPU/Linux (`10.0.0.7`) | Voz com máxima emoção e naturalidade humana para canais faceless |
| **`F5-TTS-pt-br`** (`SWivid/F5-TTS` + `firstpixel/F5-TTS-pt-br`) | Modelo flow-matching com ajuste fino dedicado para **Português do Brasil** | Servidor GPU/Linux | Clonagem de voz em PT-BR com entonação natural |
| **`CosyVoice 3` / `Fish-Speech`** | Síntese multilíngue com controle de estilo/emoção por instrução | Servidor GPU/Linux | Narração expressiva em múltiplos estilos |
| **`NarratoAI`** (`linyqh/NarratoAI`) | Clonado em `refs/NarratoAI` — análise narrativa/comentário de vídeos longos + roteiro + voz + legendas | Servidor Linux/PC | Resumos/teorias comentadas de filmes, animes e documentários |
| **`Kokoro-82M`** (`hexgrad/kokoro`) | Modelo TTS open-weight ultra leve (82M parâmetros) com qualidade próxima a APIs pagas | Melhor em servidor Linux/PC (ou ARM64 via ONNX leve) | Narração 100% offline para canais em inglês ou multilíngue |
| **`MoneyPrinterTurbo`** (`harry0703/MoneyPrinterTurbo`) | Clonado em `refs/MoneyPrinterTurbo` — gera roteiro via LLM + busca B-roll grátis (Pexels/Pixabay) + `edge-tts` + legendas Whisper + MP4 `9:16` | Pesado para o celular (melhor no seu `autom-linux` / PC); padrão de `edge-tts` `SubMaker` já portado para o celular | Fábrica de vídeos faceless automáticos sem aparecer |
| **`short-video-maker`** (`gyoridavid/short-video-maker`) | Pipeline REST + **servidor MCP** usando Kokoro TTS, Whisper, Pexels e Remotion/FFmpeg | Servidor Linux/Docker | Disparar criação de vídeos via agentes / n8n |

## 2. Agendamento e Entrega Multi-Portal (Self-Hosted)

| Projeto | Stack | Diferenciais | Onde rodar |
|---|---|---|---|
| **`Postiz`** (`gitroomhq/postiz-app`) | Next.js + Node + Postgres + Redis + Temporal | Suporta **TikTok, Instagram, YouTube** e 30+ redes; possui **API pública, nós n8n e servidor MCP** + *auto-plugs* (comentário automático com link de afiliado) | Servidor (`10.0.0.7` / Docker) recebendo os MP4s via `PUBLISH_WEBHOOK_URL` |
| **`Mixpost`** (`inovector/mixpost`) | Laravel + Vue 3 + MySQL/Postgres | Painel limpo, biblioteca de mídia e variações de legenda por rede | Servidor Linux/Docker |
| **`llama.cpp`** (`ggml-org/llama.cpp`) | C/C++ nativo (`pkg install llama-cpp` no Termux) | Já instalado no seu Galaxy A55; roda **Qwen2.5-1.5B-Instruct (`Q4_K_M`)** localmente expondo API OpenAI em `127.0.0.1:8080/v1` | **Direto no celular (Termux)** |

## 3. Arquitetura Híbrida Recomendada (Celular + Servidor)
- **No Samsung Galaxy A55 (Termux):** roda `auto-shorts-android` (`yt-dlp` + `ffmpeg 8.1.2` + `libass` + `llama-cpp` / `edge-tts` + `evolution.db`), produzindo os MP4s `9:16` higienizados com `-14 LUFS`, hook no topo e legendas queimadas.
- **No seu servidor Linux (`10.0.0.7` / `autom-linux`) com Docker + n8n + Postiz:** recebe o `publish_pack.json` + MP4 via `PUBLISH_WEBHOOK_URL` (ou Tailscale), agenda nos melhores horários do Brasil (`12:00`, `18:30`, `21:00`) e devolve as métricas para alimentar o `shorts_evolution.db`.

