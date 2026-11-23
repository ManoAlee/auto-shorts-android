# Alinhamento Visual-Semântico de Cenas — AUTO SHORTS SENTINEL

## 1. O Problema da Desconexão Visual

Em produções automatizadas, é comum que sistemas ingênuos selecionem vídeos de B-Roll aleatórios ou baseados em palavras soltas fora de contexto (ex: o narrador diz *"vamos navegar pela arquitetura do microprocessador"* e o sistema exibe um barco navegando no mar).

O `SemanticSceneAligner` (`src/auto_shorts/sentinel_pre_render/semantic_scene_aligner.py`) elimina esse defeito comparando o **intento semântico da narração** com os **metadados e tags visuais do ativo de mídia**.

---

## 2. Regras de Inspeção

### A. Coeficiente de Sobreposição de Tags
Calcula a interseção entre os termos significativos da narração e as tags cadastradas no acervo de mídia do Auto Shorts (em `assets/video_vault/`).
- Pontuação baseada em similaridade de Jaccard e correspondência de radicais de substantivos.

### B. Detecção de Contradições Flagrantes
O motor possui uma matriz determinística de incompatibilidade de domínios:
- **Domínio Tecnologia / Código / Hardware:** Incompatível com tags como `praia`, `natureza`, `futebol`, `festa`.
- **Domínio Esportes / Treino:** Incompatível com tags como `servidor`, `laboratorio`, `escritorio_fechado`.
- **Domínio Culinária:** Incompatível com tags como `transito`, `foguete`, `combate`.

Se uma contradição flagrante for identificada, o Gate 04 falha imediatamente (`VISUAL_CONTRADICTION_DETECTED`).

### C. Penalidade por Fadiga Visual & Repetição
Se o mesmo vídeo de B-Roll for alocado em duas ou mais cenas consecutivas dentro do mesmo Short (de 30 a 60 segundos), é aplicada penalidade de repetição para forçar variedade visual.

---

## 3. Substituição Guiada por Evidências

Quando uma cena é reprovada por incompatibilidade semântica, o motor sugere os ativos alternativos mais compatíveis presentes no diretório `assets/`, preparando o terreno para a intervenção do `revision_engine.py`.
