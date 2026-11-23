# Especificação Técnica: Aegis Native C11 Engine

## 1. Visão Geral e Princípios de Engenharia
O **Aegis Native C11 Engine** (`native-c/autoshorts.c`) foi concebido como um núcleo binário estático e ultra-resiliente para monitorar a saúde do sistema sem as despesas de tempo e memória de interpretadores de alto nível.

No Android/Termux, invocar o interpretador Python (`python -c ...`) consome entre 80MB e 120MB de memória RAM e entre 400ms e 800ms de CPU por chamada. Em situações de pressão de memória crítica, o ato de invocar Python para diagnosticar a memória poderia ser o gatilho final para o OOM Kill.

O Aegis C11 resolve isso com:
- **Zero alocações dinâmicas volumosas**: Buffer de stack e páginas reutilizáveis.
- **Sub-5ms de tempo de execução total**.
- **Consumo de RAM residente < 1.2 MB**.
- **Conformidade HKUDS/CLI-Anything**: Saída JSON pura quando passado o argumento `--json`.

---

## 2. Componentes e Implementação de Baixo Nível

### A. Sondas de Rede Não-Bloqueantes Zero-Fork
A verificação de portas locais (WebStudio `:8787` e OpenSSH `:8022`) é implementada diretamente em sockets POSIX com flags não-bloqueantes (`O_NONBLOCK` e `select`):

```c
int flags = fcntl(s, F_GETFL, 0);
fcntl(s, F_SETFL, flags | O_NONBLOCK);
int rc = connect(s, res->ai_addr, (int)res->ai_addrlen);
if (rc != 0 && errno == EINPROGRESS) {
    fd_set wfds;
    FD_ZERO(&wfds);
    FD_SET(s, &wfds);
    struct timeval tv = { .tv_sec = timeout_ms / 1000, .tv_usec = (timeout_ms % 1000) * 1000 };
    if (select(s + 1, NULL, &wfds, NULL, &tv) > 0) {
        int err = 0;
        socklen_t len = sizeof(err);
        if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &len) == 0 && err == 0) {
            connected = 1;
        }
    }
}
```

### B. Parser Nativo de `/proc/meminfo`
Para dispensar dependências externas, o binário lê e faz parsing direto da tabela de memória do kernel Linux:
- `MemTotal`
- `MemAvailable` (com fallback para `MemFree` + buffers/cached)
- Cálculo determinístico de status de pressão:
  - `NORMAL`: Memória disponível >= 500 MB
  - `CONSTRAINED`: Memória disponível entre 250 MB e 499 MB
  - `CRITICAL`: Memória disponível < 250 MB

### C. Timers Monotônicos de Alta Precisão
Utiliza `clock_gettime(CLOCK_MONOTONIC, &ts)` para medição de janelas de tempo imunes a saltos de relógio de parede (NTP).

---

## 3. Interface de Comandos e Contrato JSON

### Verificação de Saúde:
```bash
$ autoshorts health --json
{
  "status": "HEALTHY",
  "timestamp_mono": 173460.124,
  "services": {
    "webapp": {"port": 8787, "alive": true},
    "sshd": {"port": 8022, "alive": true}
  },
  "memory": {
    "total_mb": 7428,
    "available_mb": 3592,
    "pressure": "NORMAL"
  }
}
```

### Auditoria de ISO-BMFF:
```bash
$ autoshorts audit output/clip_01.mp4
[Aegis Audit] File: output/clip_01.mp4 (Size: 18420102 bytes)
  -> ftyp: mp42/isom (OK)
  -> moov: Present (Metadata parsed)
  -> Aspect Ratio: 9:16 Vertical (1080x1920)
  -> Duration: 44.20s (Compliant: 15s - 60s)
  -> Result: PASS (Audit Code: 0)
```
