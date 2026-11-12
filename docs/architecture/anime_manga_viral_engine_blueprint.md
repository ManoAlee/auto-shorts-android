# Blueprint Arquitetural: Motor Viral 2026 de Animes, Mangás & Cultura Pop
> **AutoShorts Studio v2 — Módulo de Animação 2.5D, Análise Crítica & Notícias Virais**  
> *Data: Novembro de 2026 | Arquitetura: Alessandro Meneses & DeepMind Agentic Team*

---

## 1. Diagnóstico do Print do TikTok & Modos de Postagem

No print enviado do aplicativo TikTok:
- **O que está acontecendo:** O vídeo do GTA Ramp chegou perfeitamente à tela final de publicação do TikTok, porém o campo **"Adicionar descrição..."** está vazio e sem hashtags.
- **Por que isso acontece tecnicamente no TikTok:**
  1. **Modo Inbox (`/v2/post/publish/inbox/video/init/`):** A API do TikTok **proíbe propositalmente** a injeção do objeto `post_info` (legenda e hashtags) quando o vídeo é enviado para a Caixa de Entrada. O TikTok desenhou a Inbox como "transferência de mídia bruta" para o criador editar os efeitos finais.
  2. **Modo Direto (`/v2/post/publish/video/init/`):** Apenas o endpoint direto suporta `post_info.title`. Nele, a legenda e todas as hashtags são publicadas **100% automaticamente** sem nenhuma intervenção manual.
- **Como resolver agora:**
  - **No modo Inbox:** No AutoShorts Studio (`http://192.168.10.210:8787`), cada card tem o botão dourado **`📋 Legenda`**. Basta tocar nele (copia tudo com 1 clique) e, na tela do print, dar um toque longo em "Adicionar descrição..." e clicar em **Colar**.
  - **No modo Direct Post:** Ao selecionar o modo direto no estúdio, o robô posta sozinho no feed público/privado com a legenda já embutida.

---

## 2. O Segredo dos Vídeos Virais de Anime & Séries em 2026

Os vídeos de maior retenção (85%+ de taxa de visualização completa) no TikTok, Reels e Shorts em 2026 seguem o formato de **Video Essay Cinematográfico 9:16**.

### Estrutura de Retenção Hipnótica (Neuro-Storytelling)

```
[00:00 - 00:03] O GANCHO CURIOSO (Hook Visual + Frase Choque)
                Ex: "O Oda revelou o maior segredo de One Piece e quase ninguém percebeu..."
                Visual: Corte rápido de cena dramática com impact lines + som de 'Whoosh'.

[00:03 - 00:15] A TESE / O MISTÉRIO (Setup & Contexto)
                Ex: "No capítulo 1110, três detalhes mudam tudo o que sabíamos sobre os Gorosei."
                Visual: Mangá com leitura dinâmica 2.5D da direita para a esquerda.

[00:15 - 00:40] A ESCALAÇÃO & REVELAÇÃO (Payoff & Comparação)
                Ex: Paralelo entre o mangá original e a cena do anime em câmera lenta.
                Visual: Transição com efeito de quebra de vidro, zoom-in nos olhos do personagem.

[00:40 - 00:55] O CLÍMAX & PERGUNTA PARA COMENTÁRIOS (Call to Action Orgânico)
                Ex: "Você acha que ele sobrevive a isso? Comenta aí quem vence essa luta."

[00:55 - 01:00] O LOOP INFINITO (Seamless Audio Loop)
                A frase final se conecta perfeitamente com a frase inicial do vídeo.
```

---

## 3. Arquitetura do Motor Gráfico 2.5D & Manga Pan-and-Scan

Transformar páginas estáticas de mangá ou clipes 16:9 em uma experiência imersiva 9:16 vertical requer **composição em camadas no FFmpeg**:

### A. Tri-Layer Composition (Sem Tarjas Pretas)
1. **Camada 0 (Fundo / Background):** Vídeo em loop ou a própria cena esticada para 1080x1920 com `boxblur=25:5` e saturação levemente reduzida.
2. **Camada 1 (Cena Principal / Foreground Panel):** O quadro do mangá ou clipe de anime em formato flutuante, com cantos arredondados, sombra projetada (drop shadow) e borda sutil com neon suave.
3. **Camada 2 (FX Dinâmicos / Procedural Overlays):** Linhas de velocidade de anime (Speed Lines / Impact Lines) em momentos de clímax, partículas flutuantes e vinheta cinematográfica.

### B. Filtro FFmpeg: Manga Right-to-Left Pan & Scan
Como mangás japoneses são lidos da direita para a esquerda, um zoompan estático arruina a narrativa. O pipeline calcula o scroll cinematográfico:

```bash
# Efeito Ken Burns Japonês (Right to Left + Zoom Suave)
ffmpeg -loop 1 -i manga_page.jpg -filter_complex \
"[0:v]scale=2160:3840,zoompan=z='min(zoom+0.0015,1.25)':x='iw*(1-on/300)':y='ih/4':d=300:s=1080x1920:fps=30[v]" \
-map "[v]" -t 10 -c:v libx264 -pix_fmt yuv420p manga_animated.mp4
```

### C. Ducking de Áudio Profissional
A voz da narração (Kokoro-82M) comanda o volume da trilha de fundo (Lo-Fi / Épica Orquestral). Quando a voz fala, o fundo diminui automaticamente em -18dB:

```bash
ffmpeg -i voiceover.wav -i soundtrack.mp3 -filter_complex \
"[1:a]volume=0.35[bgm]; \
 [0:a][bgm]sidechaincompress=threshold=0.08:ratio=6:attack=10:release=350[outa]" \
-map 0:v -map "[outa]" -c:v copy output_ducked.mp4
```

---

## 4. Pipeline de Coleta de Notícias & Cultura Pop via MCPs

Integrando com as ferramentas do ecossistema:

1. **AniList & Kitsu API (Radar de Animes):** Captura em tempo real os animes em alta da temporada, sinopses e datas de lançamento.
2. **TMDB / Rotten Tomatoes (Séries & Filmes):** Coleta trailers, notas da crítica e polêmicas de lançamentos da Netflix, HBO, Disney+ e cinemas.
3. **Agent-Reach & Jina Reader (Varredura Social):** Rastreia discussões quentes no X/Twitter, Reddit (r/anime, r/boxoffice, r/television) e YouTube para extrair teorias virais.
4. **LLM Storyteller (Gemini / Claude / DeepSeek):** Escreve o roteiro com tom sarcástico, analítico ou empolgado, formatando o texto com marcações de cena `[ZOOM_IN]`, `[SHOCK_EFFECT]`, `[MANGA_PAN]`.

---

## 5. Próximos Passos de Implementação (Roadmap)

- [x] **Fase 1: Higienização & Frontend Ágil (Concluído)**
  - Acervo limpo com exclusão em massa e 1-clique.
  - UI moderna com busca instantânea e badges de status.
- [ ] **Fase 2: Motor de Manga & Anime (Próxima Sprint)**
  - Criação do módulo `src/auto_shorts/anime_engine.py` com gerador de 2.5D Parallax e Speed Lines.
  - Integração do parser de leitura da direita para a esquerda.
- [ ] **Fase 3: Radar Cultural Automático**
  - Conector com AniList e TMDB para sugerir pautas virais diárias no painel do Copiloto IA.
