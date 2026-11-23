# ATLAS STUDIO — AUTONOMOUS CREATIVE PRODUCTION & HARNESS ENGINE

## 1. Visão Geral
O **Atlas Studio** é o subsistema de direção criativa, engenharia reversa audiovisual, controle de qualidade automatizado e orquestração multiagente lógica do AutoShorts. Ele transforma a produção de vídeos curtos verticais (9:16) em uma esteira de engenharia auditável, orientada por contratos formais e validada por múltiplos portões de qualidade (Gates A a G).

## 2. Estrutura Documental
- [Arquitetura](architecture/): Reconstrução reversa, harness multiagente de 13 personas e diagramas de componentes.
- [Pesquisa Técnica](research/): Análise de ferramentas GitHub, compatibilidade com ARM64 e licenças.
- [Direção Criativa](creative/): Diretrizes editoriais, design system audiovisual, templates e especificação das personas.
- [Controle de Qualidade](quality/): Matriz QA, portões de qualidade (Gates A a G) e Scorecard 7D.
- [Confiabilidade & SRE](reliability/): Diagnóstico do Android LMK, supervisão C11 Aegis e recuperação transacional.
- [Relatórios Executivos](reports/): Relatório executivo da operação e registro detalhado de bugs corrigidos.

## 3. Padrões Operacionais
- **CLI-Anything Compliant**: Todos os comandos suportam `--json` e flags estruturadas (`main.py studio presets --json`, `main.py studio pipeline --json`).
- **RAM Conscious**: Orquestração multiagente sequencial e cooperativa, sem instanciar múltiplos LLMs pesados na memória do smartphone.
- **Fail-Closed Gateways**: Nenhum vídeo é publicado sem validação estrita dos Quality Gates críticos.
