# ENGENHARIA REVERSA DO SISTEMA DE PRODUÇÃO AUDIOVISUAL

## 1. Mapeamento do Pipeline Legado vs Atlas Studio
A investigação do AutoShorts original revelou um pipeline monolítico sequencial onde a falha em qualquer sub-etapa (download, TTS, Whisper, FFmpeg, publicação) resultava em descarte do trabalho ou processos zumbis consumindo RAM.

```
Legado (Frágil):
Topic -> LLM Script -> gTTS/Kokoro -> FFmpeg Raw -> Hardcoded Upload
(Sem safe zones, sem validação LUFS, sem contratos de persona, sem isolamento de processo)

Atlas Studio (Resiliente & Modular):
Topic -> [P1..P4 Editorial] -> [P5 Design System] -> [P6..P8 Produção Audiovisual] 
      -> [P9..P12 QA & Compliance] -> [P13 Harness Quality Gates A-G] -> [Omega CDP / Review Gateway]
```

## 2. Pontos Críticos Isolados na Engenharia Reversa
1. **Quebra de Safe Zones Verticais (9:16)**:
   - No pipeline legado, legendas e textos de título colidiam com a barra lateral de botões do TikTok/Shorts (Like, Comentário, Compartilhar) e o rodapé da descrição.
   - *Solução Reversa*: Implementação de `SafeZoneSpec` delimitando o retângulo útil `(60, 220, 940, 1540)` em resolução 1080x1920.

2. **Inconsistência de Loudness (EBU R128)**:
   - Áudios de voz eram mixados sem controle de True Peak e ducking dinâmico, causando distorção ou voz inaudível sobre trilhas de ação.
   - *Solução Reversa*: Normalização em -14.0 LUFS, ducking em curva de -16dB a -18dB e True Peak limitado em -1.0 dBFS.

3. **Clichês de Abertura e Fadiga Algorítmica**:
   - Roteiros gerados por LLM puro iniciavam com saudações mortas ("No vídeo de hoje vamos ver..."), derrubando a retenção nos primeiros 2 segundos.
   - *Solução Reversa*: Persona 03 e Persona 04 com validador determinístico contra clichês e formulação de gancho de curiosidade imediato.
