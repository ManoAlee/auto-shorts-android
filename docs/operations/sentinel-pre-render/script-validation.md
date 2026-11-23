# Inteligência de Roteiro e Análise de Arco — AUTO SHORTS SENTINEL

## 1. Objetivos do Motor

O `ScriptIntelligenceEngine` (`src/auto_shorts/sentinel_pre_render/script_intelligence.py`) avalia a eficácia narrativa e comunicacional do texto antes da gravação de voz (TTS) ou renderização visual.

---

## 2. Critérios de Avaliação

### A. Potência do Gancho (0 a 3 Segundos)
O primeiro período do texto é inspecionado à procura de:
- **Provocação Curiosa:** Perguntas instigantes, revelações contra-intuitivas ou quebra de padrão.
- **Início Imediato:** Inicia diretamente no assunto, sem preâmbulos mortos.
- **Detecção de Clichês de IA (Anti-Slop):** Expressões como *"Você já se perguntou..."*, *"No vídeo de hoje..."*, *"Prepare-se para descobrir..."* recebem penalidade severa imediata.

### B. Arco Narrativo dos Três Atos
O roteiro é segmentado em três proporções estruturais:
1. **Ato 1: Gancho & Promessa (15-20% iniciais):** Define o valor do vídeo para o espectador.
2. **Ato 2: Desenvolvimento & Revelação (60-70% centrais):** Conteúdo palpável, densidade informativa e progressão sem enrolação.
3. **Ato 3: Resolução & Call To Action (15-20% finais):** Fechamento coeso e chamada para ação suave ou final surpreendente.

### C. Cadência e Ritmo (WPM)
O motor calcula a duração prevista da narração baseando-se na contagem de palavras em português:
- **Taxa Alvo:** 130 a 165 WPM (Palavras Por Minuto).
- Roteiros abaixo de 110 WPM são sinalizados como sonolentos/lentos (`PACING_TOO_SLOW`).
- Roteiros acima de 190 WPM são sinalizados como ininteligíveis/acelerados (`PACING_TOO_FAST`).

---

## 3. Exemplo de Saída Analítica

```json
{
  "hook_score": 85.0,
  "hook_analysis": "Gancho direto focado em dor real de produtividade.",
  "narrative_arc_score": 90.0,
  "has_clear_beginning": true,
  "has_clear_middle": true,
  "has_clear_ending": true,
  "slop_penalty": 0.0,
  "words_per_minute": 142.5,
  "pacing_status": "OPTIMAL",
  "recommended_cuts": []
}
```
