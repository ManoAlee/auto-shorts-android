# COMPATIBILIDADE DE FERRAMENTAS COM ANDROID / ARM64

## 1. Matriz de Compatibilidade Técnica

| Componente | Suporte x86_64 | Suporte aarch64 (Termux) | Desempenho / Gargalo no Celular | Mitigação Adotada |
|---|---|---|---|---|
| **C11 Aegis Engine** | Total (GCC/Clang) | Total (Clang Termux) | < 5ms tempo de resposta, 4MB RAM | Compilação direta via `clang -O3` |
| **Chromium Headless** | Total | Nativo via `pkg install x11-repo && pkg install chromium` | Zygote fork consome até 1.6GB se não isolado | Process groups (`os.killpg`) e cleanup agressivo |
| **Python 3.12+** | Total | Total | Interpretação rápida, módulos C pré-compilados | Sem PyTorch pesado na RAM |
| **FFmpeg** | Total | Total (aarch64) | Codificação H.264 consome CPU; ideal em threads moderadas | Limitação a `-threads 4` para preservar estabilidade térmica |
