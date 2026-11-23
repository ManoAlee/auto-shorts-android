# AVALIAÇÃO DE FERRAMENTAS DO ECOSSISTEMA GITHUB

## 1. Ferramentas Auditadas
Foram analisadas ferramentas de referência open source para corte de vídeo, legendagem e automação:

| Repositório / Ferramenta | Licença | Utilidade Principal | Avaliação de Risco / Compatibilidade ARM64 |
|---|---|---|---|
| **FFmpeg** | LGPL 2.1+ / GPL | Transcodificação, filtros e geração de vídeo | Nativo excelente no Termux (aarch64 via pkg install ffmpeg). |
| **faster-whisper / Whisper.cpp** | MIT | Transcrição de áudio e alinhamento de timestamps | whisper.cpp com aceleração NEON roda com baixo consumo em ARM64. |
| **MoviePy** | MIT | Manipulação e renderização programática | Dependente de fork Python; lento em CPU pura se usado diretamente. Substituído por comandos FFmpeg diretos. |
| **Edge-TTS / Kokoro** | MIT / Apache 2.0 | Síntese de voz neural com entonação natural | Alta fidelidade; Edge-TTS consome zero RAM local (via endpoint Egress). |
| **CLI-Anything (HKUDS)** | MIT | Padronização de flags CLI e JSON estruturado | Padrão adotado 100% no AutoShorts (`--json`, `--help`, exit codes padronizados). |
