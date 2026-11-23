# Storyboard Engine — AUTO SHORTS SENTINEL

## 1. Princípio do Storyboard-First

Tradicionalmente, a renderização de um vídeo vertical em 1080x1920 com legendas animadas e trilha sonora custa de 15 a 45 segundos de CPU em processadores ARM64 móveis.

O `StoryboardEngine` (`src/auto_shorts/sentinel_pre_render/storyboard_engine.py`) viabiliza a aprovação prévia em menos de **300 milissegundos**, sem codificar um único frame de vídeo final.

---

## 2. Artefatos Gerados

### A. Storyboard HTML Responsivo
Gera um arquivo de inspeção estático `{project_id}_storyboard.html` em `output/sentinel/storyboards/`.
O arquivo possui:
- Layout responsivo em grid com formato 9:16 para simular a tela do smartphone.
- Visualização do frame estático ou thumbnail representativo da cena.
- **Overlay de Safe Zone:** Retângulo pontilhado indicando a área livre de sobreposições dos botões de like/compartilhar e legenda nativa do TikTok, Instagram e YouTube.
- Texto da narração e tempo estimado de cada cena.
- Badges de tags e tipo de movimento de câmera programado (`zoom_in`, `pan_left`, etc.).

### B. Prancha de Contato (Contact Sheet)
Quando aplicável, agrupa os frames extraídos de cada cena em uma única imagem concatenada para revisão instantânea por agentes ou operadores humanos.

---

## 3. Exemplo Visual da Interface do Storyboard

O arquivo HTML exportado permite navegação interativa e inspeção detalhada de cada cena:
- Identificador da Cena (`Scene 01 [HOOK]`, `Scene 02`, etc.).
- Duração em segundos.
- Texto da locução correspondente.
- Conformidade de safe zone.
