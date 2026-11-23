# Arquitetura do Sistema — AUTO SHORTS SENTINEL

## 1. Visão Arquitetural

O Sentinel Pre-Render foi projetado seguindo uma arquitetura em camadas orientada a contratos imutáveis, executada de forma sequencial para garantir **zero memory drop** em ambientes móveis Android ARM64 (Termux).

```mermaid
flowchart TD
    subgraph INPUT["1. Camada de Entrada"]
        CB["ContentBrief"]
        SC["SceneContracts (0..N)"]
        SM["StoryboardManifest"]
    end

    subgraph ANALYSIS["2. Motores de Inspeção Multimodal"]
        TCE["TitleConsistencyEngine<br/>• Promessas Numéricas<br/>• Entidades Tópicas<br/>• Matriz Claim->Evidence"]
        SIE["ScriptIntelligenceEngine<br/>• Força do Gancho (0-3s)<br/>• Arco Narrativo 3 Atos<br/>• Cadência WPM (130-165)<br/>• Anti-Slop IA"]
        SSA["SemanticSceneAligner<br/>• Tags Ativo vs Narração<br/>• Detecção de Contradições<br/>• Penalidade Repetição"]
    end

    subgraph REVIEW["3. Personas Sequenciais de Revisão"]
        P1["Creative Director"]
        P2["Script Editor"]
        P3["Visual Analyst"]
        P4["Audio Director"]
        P5["Motion Reviewer"]
        P6["Fact-Check Editor"]
        P7["Platform Specialist"]
        P8["QA Orchestrator"]
    end

    subgraph GATES["4. 10 Quality Gates"]
        QG["Avaliação Ponderada<br/>Gate 01 a Gate 10"]
    end

    subgraph DECISION{"5. Veredito"}
        PASS["PASS (Score >= 75%)"]
        REVIEW_REQ["REQUIRES_REVIEW"]
        FAIL["FAIL (Score < 50%)"]
    end

    subgraph HEALING["6. Autocorreção Guiada por Evidências"]
        EGRE["EvidenceGuidedRevisionEngine<br/>• Retitulação / Recalibração<br/>• Reflow de Legendas<br/>• Substituição de B-Roll<br/>(Max 3 Iterações)"]
    end

    subgraph PREVIEW["7. Geração de Artefatos de Inspeção"]
        HTML["Storyboard HTML Responsivo"]
        PROXY["Proxy Video (360x640 @ 15fps)"]
        REP["SentinelReport JSON"]
    end

    INPUT --> ANALYSIS
    ANALYSIS --> REVIEW
    REVIEW --> GATES
    GATES --> DECISION
    DECISION -->|PASS| PREVIEW
    DECISION -->|FAIL ou REQUIRES_REVIEW| EGRE
    EGRE -->|Pacote Corrigido| ANALYSIS
```

---

## 2. Invariantes de Execução em ARM64 / Termux

Para operar dentro dos limites rigorosos de hardware do Samsung Galaxy A55 5G (Android 14, 8GB RAM compartilhada com o sistema):

1. **Sequential Persona Execution:** As 8 personas de avaliação nunca são executadas em threads concorrentes pesadas. Cada persona opera sobre a mesma estrutura de dados em memória, consumindo menos de 5MB por ciclo de inferência.
2. **Zero-Drop Memory Cap:** O consumo de pico de RSS da orquestração nunca ultrapassa **150MB**, evitando o gatilho do Low Memory Killer (LMK) do kernel Android.
3. **Non-Blocking Proxies:** Quando um proxy de vídeo é solicitado, ele usa a resolução ultra-leve de `360x640` com framerate de `15fps` e `-crf 32` em `-preset ultrafast`. Isso reduz o tempo de renderização para menos de 3 segundos e evita superaquecimento da CPU.
4. **Contratos Fortemente Tipados:** Nenhuma informação transita como string solta ou dicionário arbitrário. Todos os dados são governados pelas dataclasses em `contracts.py`.
