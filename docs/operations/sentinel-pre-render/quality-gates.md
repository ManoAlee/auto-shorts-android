# Os 10 Quality Gates Multimodais — AUTO SHORTS SENTINEL

## 1. Definição dos Gates de Qualidade

Antes que qualquer projeto seja liberado para renderização final, ele deve ser submetido à avaliação do `SentinelQualityGatesEngine` (`src/auto_shorts/sentinel_pre_render/quality_gates_sentinel.py`), que audita 10 Quality Gates obrigatórios:

| Gate | Nome | Foco de Inspeção | Critério de Aprovação |
|---|---|---|---|
| **Gate 01** | `Title-to-Content Consistency` | Correspondência entre título e narração | Score >= 75%, sem entidades centrais ausentes |
| **Gate 02** | `Hook & First 3 Seconds Power` | Retenção imediata nos primeiros 3s | Score >= 70%, sem aberturas lentas ou mortas |
| **Gate 03** | `Narrative Arc & Pacing` | Estrutura dos 3 atos e WPM | WPM entre 120 e 175, início-meio-fim presentes |
| **Gate 04** | `Visual-Semantic Cohesion` | Alinhamento de imagens com fala | Zero contradições flagrantes, sobreposição >= 60% |
| **Gate 05** | `Safe Zone & Framing Compliance` | Legendas e enquadramento vertical | Linhas <= 34 caracteres, dentro das margens |
| **Gate 06** | `Audio & Speech Synchronization` | Ritmo de locução e pausas | Duração compatível com tempo de tela |
| **Gate 07** | `Anti-Slop & Editorial Tone` | Filtragem de clichês e tom robótico | Zero expressões banidas de IA no gancho |
| **Gate 08** | `Thumbnail / Cover Promise` | Alinhamento da promessa visual | Capa/thumb compatível com o tema central |
| **Gate 09** | `Platform Fit & Durations` | Duração e formato para a rede | Duração total entre 15s e 60s, formato 9:16 |
| **Gate 10** | `Auto-Revision Readiness` | Capacidade de autocorreção | Erros detectados possuem solução prescrita |

---

## 2. Tabela de Vereditos

- **`PASS`**: Pontuação geral >= 75% e nenhum gate crítico com falha bloqueante. O projeto segue diretamente para renderização final.
- **`REQUIRES_REVIEW`**: Pontuação geral entre 50% e 74%. Dispara o motor de autocorreção (`revision_engine.py`) para tentar resolver as divergências automaticamente antes de notificar o operador.
- **`FAIL`**: Pontuação geral < 50% ou violação de contrato irreversível (ex: contradição visual severa com ausência total de ativos no acervo). Renderização bloqueada para evitar desperdício de recursos.
