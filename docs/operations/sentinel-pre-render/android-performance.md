# Desempenho e Limites em Android Termux ARM64 — AUTO SHORTS SENTINEL

## 1. Perfil de Recursos do Ambiente Alvo

- **Dispositivo Primário:** Samsung Galaxy A55 5G
- **Arquitetura:** ARM64 (aarch64), SoC Exynos 1480 (4x 2.75 GHz Cortex-A78 + 4x 2.0 GHz Cortex-A55)
- **Sistema Operacional:** Android 14 com Termux v0.118+
- **Ambiente Python:** Python 3.11 / 3.12 em Termux Userspace
- **Restrições:** Ausência de GPU dedicada para encoding NVENC; aceleração via CPU (libx264) ou OpenMAX restrita; gerenciamento agressivo de background pelo Android OOM/LMK.

---

## 2. Diretrizes de Engenharia para Termux

### A. Limite Rigoroso de Memória RSS (< 150MB)
Em ambientes Android, processos em background ou sessões do Termux que alocam súbitos picos de memória (> 300MB) são imediatamente eliminados pelo Low Memory Killer (LMK).
- O Sentinel realiza auditorias de texto e metadados usando estruturas leves (`dataclasses`).
- Imagens são carregadas sob demanda e liberadas da memória após a extração dos descritores ou thumbnail.

### B. Controle Térmico e de Threads
Renderizações prolongadas em smartphones causam estrangulamento térmico (*thermal throttling*), reduzindo a velocidade dos núcleos da CPU para menos de 40% da capacidade nominal.
- No modo `FULL_PROXY_PREVIEW`, o FFmpeg é executado com `-threads 2` e `-preset ultrafast`.
- A resolução de `360x640` consome apenas ~5% da energia que seria gasta na renderização de 1080x1920, permitindo dezenas de validações sucessivas sem aquecer o smartphone.

### C. Isolamento de Processos e Limpeza de Lixo
- Todos os arquivos temporários criados para visualizações são armazenados em `output/sentinel/previews/` com nomenclatura determinística e limpos automaticamente após o ciclo de vida do projeto.
- Nenhuma chamada ao FFmpeg fica orfã como processo zumbi no Termux.
