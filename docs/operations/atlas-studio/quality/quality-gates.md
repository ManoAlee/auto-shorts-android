# PROTOCOLO DOS QUALITY GATES (GATES A A G)

## 1. Definição dos Portões

- **GATE A — CODE & SYSTEM**: Verifica se o host Android/Termux está saudável, sem pressão crítica de memória RAM (`pressure != CRITICAL`) e com espaço em disco suficiente.
- **GATE B — MEDIA INTEGRITY** *(Crítico / Bloqueante)*: Valida através de ffprobe se o arquivo MP4 contém streams válidos de vídeo vertical 9:16 e áudio AAC estéreo.
- **GATE C — VISUAL VALIDATION**: Avalia se o preset estético está configurado e se o arquivo possui amostragem visual consistente (sem corrupção de codec).
- **GATE D — AUDIO VALIDATION**: Confere conformidade com EBU R128 (-14 LUFS) e ausência de silêncio anormal prolongado (> 2.0s).
- **GATE E — EDITORIAL REVIEW**: Valida comprimento do título (8 a 98 caracteres), descrição e ausência de clichês proibidos de IA.
- **GATE F — PLATFORM COMPLIANCE** *(Crítico / Bloqueante)*: Garante conformidade com o limite máximo de tempo da plataforma alvo (<= 60.0s para Shorts, <= 90.0s para Reels).
- **GATE G — HUMAN APPROVAL**: Registra aprovação formal do operador ou chancela automática do sistema de acordo com a política de publicação ativa.

## 2. Regra de Decisão
Um vídeo só é classificado como `is_approved = True` quando:
1. `Gate B (Media Integrity)` **PASSOU**.
2. `Gate F (Platform Compliance)` **PASSOU**.
3. A nota geral ponderada do **Scorecard 7D** é maior ou igual a **70/100**.
