# ORQUESTRAÇÃO MULTIAGENTE LÓGICA (13 PERSONAS)

## 1. Princípio Arquitetural
Para executar com estabilidade em um smartphone ARM64 (Samsung Galaxy A55 5G) sem sobrecarregar a memória RAM de 8GB, o sistema adota **Personas Lógicas Sequenciais** em vez de carregar múltiplos modelos de 7B/14B parâmetros simultaneamente.

Cada persona é um módulo determinístico de validação e transformação orientado a contratos (`AgentTaskContract`).

## 2. Catálogo das 13 Personas Lógicas

| # | Persona | Função Primária | Entregável / Contrato |
|---|---|---|---|
| **P01** | Chief Creative Officer | Estratégia, nicho e viabilidade de produção | Orçamento de retenção e autorização técnica |
| **P02** | Showrunner / Editor-in-Chief | Linha editorial e eliminação de redundância | Estrutura de 3 atos (Gancho, Conflito, CTA) |
| **P03** | Viral Content Strategist | Hipótese de retenção dos 2s e título SEO | Gancho de abertura e título otimizado |
| **P04** | Senior Screenwriter | Roteiro natural em PT-BR | Roteiro livre de clichês e marcadores de fala |
| **P05** | Creative Director | Design System Audiovisual e Presets | Aplicação de cores, fontes e safe zones |
| **P06** | Senior Video Editor | Reenquadramento vertical e ritmo | Cortes justificados e sincronização visual |
| **P07** | Motion Graphics Director | Legendas cinéticas e lower thirds | Script ASS com kinetic word highlighting |
| **P08** | Audio Post-Production Director | Equalização, ducking e EBU R128 | Áudio mixado em -14 LUFS com ducking |
| **P09** | Visual QA & CV Engineer | Inspeção de quadros e telas pretas | Amostragem de frames e validação de safe zones |
| **P10** | Platform Distribution Engineer | Parâmetros multiplataforma | Conformidade de duração (Shorts <=60s, TikTok >=60s) |
| **P11** | Android Native & Reliability | SRE, memória RAM e processo Aegis | Auditoria de LMK e telemetria de runtime |
| **P12** | Copyright & Fact-Check Editor | Segurança legal e integridade factual | Verificação de fontes e licenças de mídia |
| **P13** | Principal Harness Architect | Consolidação de Quality Gates A-G | Scorecard 7D e liberação para aprovação humana |

## 3. Estrutura do Contrato de Tarefa (`AgentTaskContract`)
Cada execução gera um artefato imutável em `output/studio_evidence/studio_harness_<job_id>.json` contendo:
- `task_id`, `job_id`, `agent_role`, `objective`
- `inputs`, `constraints`, `dependencies`
- `acceptance_criteria`, `evidence_paths`
- `status` (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `REJECTED`)
- `completed_at` (timestamp de alta resolução)
