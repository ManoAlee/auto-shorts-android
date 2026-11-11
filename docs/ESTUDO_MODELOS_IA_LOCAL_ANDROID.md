# Modelos de IA Locais Recomendados para Samsung Galaxy A55 5G (`SM-A556E`)

## 1. Perfil Real de Hardware Medido no Dispositivo

| Recurso | Especificação Medida (`termux`) | Impacto na Escolha de Modelos |
|---|---|---|
| **SoC / CPU** | Exynos 1480 (`aarch64`), **4x Cortex-A78 @ 2.75 GHz** + **4x Cortex-A55 @ 2.05 GHz** | Instruções `asimddp` (ARM dot-product), `fp16` e `atomics` aceleram modelos GGUF `Q4_K_M` / `Q4_0` nos 4 núcleos A78. |
| **Memória RAM** | `7.3 GiB` total · **`~2.7 GiB` livres** (Android 16 + One UI consomem ~4.4 GiB) | **Limite seguro de RAM por modelo: <= 2.0 GB** para não disparar ZRAM swap thrashing nem OOM Killer do Android 16. |
| **Swap (ZRAM)** | `8.0 GiB` | Evite depender de swap durante inferência (derruba tok/s em 5x–10x). |
| **Armazenamento** | `58 GB` livres (`/data/data/com.termux/files`) | Espaço de sobra para múltiplos modelos GGUF + GGML + cache de vídeos. |
| **GPU** | Xclipse 530 (RDNA2) | Termux oferece `llama-cpp-backend-vulkan` e `llama-cpp-backend-opencl` (opcional para testes; CPU A78 + `asimddp` costuma ser mais estável). |

---

## 2. Modelos de LLM Locais (para Ranking de Cortes, Hooks e Scripts)

Todos rodam via `llama-cpp` (`llama-server` expondo API compatível com OpenAI em `http://127.0.0.1:8080/v1`, compatível nativamente com `OPENAI_BASE_URL` deste projeto!).

| Tier | Modelo | Quantização | Tamanho / RAM | Velocidade Esperada (A78) | Indicação para este Projeto |
|---|---|---|---|---|---|
| **1º Recomendado (Sweet Spot)** | **Qwen2.5-1.5B-Instruct** | `Q4_K_M` | ~1.1 GB (~1.5 GB em RAM com `-c 2048`) | Rápido (~10–18 tok/s) | Melhor equilíbrio entre tamanho em RAM, compreensão de **português**, obediência a **JSON estrito** e criação de `hook_title`. |
| **2º (Ultra Leve / Bateria)** | **Llama-3.2-1B-Instruct** | `Q4_K_M` | ~0.8 GB (~1.2 GB RAM) | Muito rápido (~15–25 tok/s) | Ideal para rodar em lote na bateria ou com outros apps abertos. |
| **3º (Qualidade Máxima no A55)** | **Qwen2.5-3B-Instruct** ou **Llama-3.2-3B-Instruct** | `Q4_K_M` | ~1.9–2.0 GB (~2.5 GB RAM) | Moderado (~5–10 tok/s) | Teto máximo confortável para 8 GB de RAM. Feche apps pesados antes de rodar. |
| **4º (Multimodal/Texto Google)** | **Gemma-2-2B-it** | `Q4_K_M` | ~1.6 GB (~2.1 GB RAM) | Bom (~8–14 tok/s) | Ótima escrita criativa em PT-BR para hooks e CTAs. |
| **Evitar no A55** | Modelos **7B / 8B+** (mesmo Q4) | `Q4_K_M` | ~4.5–5.5 GB | < 1–2 tok/s + risco OOM | Excede os ~2.7 GB livres; o Android 16 encerra o processo. |

---

## 3. Modelos de Transcrição Local (Speech-to-Text via `whisper.cpp`)

| Modelo GGML | Tamanho | Uso de RAM | Qualidade em PT-BR | Recomendação |
|---|---|---|---|---|
| `ggml-tiny-q5_1.bin` | ~32 MB | ~150 MB | Razoável (melhor para áudio limpo) | Testes rápidos ou bateria baixa |
| **`ggml-base-q5_1.bin`** | **~60 MB** | **~250 MB** | **Boa (melhor custo/benefício)** | **Padrão recomendado no celular** |
| `ggml-small-q5_1.bin` | ~190 MB | ~550 MB | Muito boa (ótimo com sotaques/gírias BR) | Usar quando conectado na tomada e sem LLM carregado junto |

> **Regra de Ouro no Galaxy A55:** não rode `whisper-cli` (small) e `llama-server` (3B) **ao mesmo tempo** em RAM. Execute o pipeline sequencialmente (transcreve primeiro, libera RAM, depois ranqueia/corta) — exatamente como `pipeline.py` foi desenhado!

---

## 4. Regras de Tuning no Exynos 1480

- **Threads (`-t 4`):** o Exynos 1480 tem **4 núcleos Cortex-A78** de alto desempenho e 4 Cortex-A55 econômicos. Fixar `-t 4` concentra o trabalho nos 4 núcleos rápidos evitando contenção de cache e aquecimento excessivo (`-t 8` frequentemente piora latência e esquenta).
- **Contexto (`-c 2048`):** suficiente para transcrições em blocos sem inflar o KV-cache em RAM.
- **Integração direta com o `auto-shorts-android`:**
  ```bash
  export OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
  export OPENAI_API_KEY="local"
  export OPENAI_MODEL="qwen2.5-1.5b"
  python main.py "URL_DO_VIDEO" --niche financas --platform tiktok_rewards
  ```

