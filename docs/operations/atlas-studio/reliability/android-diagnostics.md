# DIAGNÓSTICO DO ANDROID LOW MEMORY KILLER (LMK)

## 1. Causa Raiz da Interrupção de Processos (RCA)
A investigação forense realizada via `adb shell dumpsys activity exit-info com.termux` identificou que o encerramento espontâneo do Termux era disparado pelo kernel Android:
- **Motivo**: `reason=3 (LOW_MEMORY)`
- **Sub-motivo**: `sub_reason=0`
- **Importance**: `125` (Foreground Service / Background)

### Mecanismo de Falha
Ao iniciar automação de navegador via Chromium, o binário realizava forks múltiplos de processos utilitários e zygote (`--type=utility`, `--type=zygote`), alocando mais de 1.6 GB de RAM física. Com a memória livre do smartphone caindo abaixo do limite de segurança do Samsung One UI (~150MB), o driver LMK disparava `SIGKILL` em todo o grupo de processos do Termux.

## 2. Mitigações Definitivas Aplicadas
1. **Isolamento de Process Group (`os.setsid`)**:
   - Todo processo filho é gerado em seu próprio PGID, permitindo terminação cirúrgica em cascata com `os.killpg(pgid, signal.SIGTERM/SIGKILL)`.
2. **Coleta de Lixo de Heap Nativo**:
   - Invocação periódica de `ctypes.CDLL(None).malloc_trim(0)` para devolver páginas não utilizadas ao sistema operacional.
3. **Whitelist de Bateria e Processos Fantasmas**:
   - `deviceidle whitelist +com.termux`
   - `settings put global max_phantom_processes 2147483647`
