# Atlas Omega: Especificação do Harness HKUDS / CLI-Anything

## 1. O Padrão CLI-Anything para Agentes Autônomos
Baseado na especificação arquitetural do **HKUDS/CLI-Anything** (`https://github.com/HKUDS/CLI-Anything`), este padrão transforma qualquer aplicação complexa em uma interface de comando estruturada, idempotente e autodocumentada para agentes de inteligência artificial.

### Princípios Cardeais:
1. **JSON-First Output:** Todo subcomando suporta o modificador `--json`, emitindo dados estruturados em JSON puro em stdout (e logs em stderr).
2. **Códigos de Saída Semânticos (Exit Codes):**
   - `0`: Sucesso absoluto (Success).
   - `1`: Erro operacional recuperável / estado degradado.
   - `2`: Parâmetros inválidos ou erro de sintaxe de linha de comando.
   - `3`: Falha crítica de serviço ou inacessibilidade de dependência.
3. **Auto-Cura Transacional:** Estados em falha mantêm checkpoints persistidos em disco com capacidade de retomada atômica (rollback / retry).

---

## 2. Máquina de Estados e Recuperação de Jobs (`job_recovery.py`)
Toda produção audiovisual é representada como um grafo direcionado acíclico com **14 estados finitos**:

```text
CREATED -> QUEUED -> DISCOVERING -> DOWNLOADING -> DOWNLOADED ->
TRANSCRIBING -> SCRIPTING -> GENERATING_AUDIO -> RENDERING ->
VALIDATING -> READY -> PUBLISHING -> PUBLISHED

Estados de Exceção:
[RENDERING / TRANSCRIBING] --- (Falha / LMK Kill) ---> RENDER_FAILED / RECOVERABLE
RECOVERABLE ---> RECOVERING ---> QUEUED (Retry com contador atômico)
```

### Garantias de Consistência (Two-Phase Commit):
- Cada transição de estado grava o checkpoint em um arquivo temporário com prefixo e sufixo (`output/jobs/<job_id>.tmp`).
- Após o `fsync`, realiza `os.replace` atômico sobre o arquivo final (`output/jobs/<job_id>.json`).
- Quedas abruptas de energia ou SIGKILL do sistema nunca corrompem o estado de jobs anteriores.

---

## 3. Matriz de Comandos CLI-Anything

```bash
# Diagnóstico completo de saúde e hardware (JSON)
$ python main.py health --json

# Listagem de jobs ativos e histórico
$ python main.py jobs list --json

# Identificação de produções interrompidas aptas para recuperação
$ python main.py jobs recoverable --json

# Status ao vivo do motor e scheduler
$ python main.py status --json

# Auditoria estrutural de vídeo gerado
$ python main.py audit output/clip_01.mp4 --json
```
