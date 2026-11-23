# Atlas Studio: Controle de Qualidade Audiovisual em 5 Dimensões (QA 5D)

## 1. Princípio de Aceitação
No Auto Shorts, nenhum vídeo é elegível para distribuição automática sem ser submetido e aprovado pelo **Auditor 5D** (`src/auto_shorts/validator.py` e `native-c/autoshorts.c`).

O objetivo é garantir retenção máxima, conformidade algorítmica com YouTube Shorts, TikTok e Reels, e prevenir penalizações por baixa resolução, áudio distorcido ou legendas sobrepostas.

---

## 2. As 5 Dimensões Auditadas

| Dimensão | Requisito Técnico | Tolerância de Aceite | Ação em Caso de Falha |
| :--- | :--- | :--- | :--- |
| **1. Estrutura ISO-BMFF** | Header `ftyp` compatível (`mp42/isom`), atom `moov` íntegro posicionado no início para fast-start | Obrigatório (Fail-Closed) | Re-muxing via `ffmpeg -c copy -movflags +faststart` |
| **2. Geometria Vertical** | Proporção exata 9:16 (1080x1920 ou 720x1280), framerate entre 24 e 60 FPS | Tolerância zero para letterboxing não intencional | Crop e re-escalonamento com aceleração de hardware |
| **3. Volume e Loudness (EBU R128)** | Integrated Loudness entre -14 e -16 LUFS, True Peak <= -1.0 dBFS | Volume médio de diálogo entre -12 dB e -18 dB | Normalização de áudio em 2 passos (`loudnorm`) |
| **4. Integridade de Legendas** | Densidade mínima de 1.5 a 4.0 palavras por segundo; zero sobreposição temporal | Tolerância de jitter < 30ms | Re-alinhamento BPE e re-cálculo de timestamps |
| **5. Duração e Ritmo de Retenção** | Tempo total entre 15.0s e 59.5s; corte do primeiro silêncio nos primeiros 1.2s | Obrigatório para qualificação Shorts | Poda cirúrgica do head/tail do áudio |

---

## 3. Exemplo de Relatório Estruturado de Validação (JSON)

```json
{
  "valid": true,
  "file": "clip_ia_tech_01.mp4",
  "dimensions": {
    "iso_bmff": {
      "ftyp": "mp42",
      "fast_start": true,
      "passed": true
    },
    "geometry": {
      "width": 1080,
      "height": 1920,
      "aspect_ratio": "9:16",
      "fps": 30.0,
      "passed": true
    },
    "loudness": {
      "integrated_lufs": -14.2,
      "true_peak_db": -1.1,
      "mean_volume_db": -16.4,
      "passed": true
    },
    "subtitles": {
      "total_cues": 28,
      "words_per_second": 2.8,
      "overlaps": 0,
      "passed": true
    },
    "timing": {
      "duration_sec": 42.18,
      "hook_silence_cut_sec": 0.45,
      "passed": true
    }
  },
  "quality_score": 98,
  "ready_for_distribution": true
}
```
