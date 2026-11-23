# SUPERVISÃO DE PROCESSOS COM MOTOR C11 AEGIS

## 1. Princípio do C11 Aegis Engine
Para garantir que o monitoramento do sistema não consuma recursos de CPU e memória adicionais, foi desenvolvido um binário nativo em C11 (`native-c/autoshorts.c`), compilado diretamente com Clang ARM64 e instalado em `$PREFIX/bin/autoshorts`.

## 2. Características de Engenharia
- **Zero-Fork Socket Checking**: Inspeção de conectividade via sockets TCP não-bloqueantes (`O_NONBLOCK` + `select` com timeout de 200ms), sem invocar shells externos ou curl.
- **Relógio Monotônico**: Uso estrito de `clock_gettime(CLOCK_MONOTONIC)` para evitar falhas com ajustes de fuso horário ou NTP.
- **Leitura Direta de Kernel**: Leitura determinística de `/proc/meminfo` e `/proc/loadavg` para auditoria de saúde em menos de 5 milissegundos.
- **Saída JSON Estruturada**: `autoshorts health --json` fornece o estado do sistema pronto para ingestão pelo agente e pela UI.
