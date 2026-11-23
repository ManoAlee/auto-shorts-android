# Runbook: Blindagem de Bateria e Políticas One UI 6 / Android 17

## 1. Contexto do Hardware e do Sistema Operacional
- **Dispositivo:** Samsung Galaxy A55 5G (`SM-A556E`)
- **SoC:** Samsung Exynos 1480 (`s5e8845`) — 4x Cortex-A78 @ 2.75 GHz + 4x Cortex-A55 @ 2.0 GHz
- **GPU:** AMD Xclipse 530 (RDNA 2)
- **RAM:** 8 GB LPDDR5 + 8 GB zRAM swap
- **Sistema:** Android 17 / One UI 6 (SDK 37)

A interface One UI da Samsung possui um dos gerenciadores de bateria mais agressivos do ecossistema Android, suspendendo processos em background após períodos curtos de inatividade da tela e impondo cotas estritas de CPU a processos bifurcados (Phantom Process Killer).

---

## 2. Comandos de Blindagem Aplicados via ADB

Os seguintes comandos foram aplicados de forma definitiva através da ponte ADB conectada ao dispositivo:

### A. Prevenção de Suspensão de Tela e CPU Conectado ao USB
```bash
adb shell settings put global stay_on_while_plugged_in 7
```
*Valor `7`*: Combinação binária `BATTERY_PLUGGED_AC (1) | BATTERY_PLUGGED_USB (2) | BATTERY_PLUGGED_WIRELESS (4)`.
*Efeito:* O processador e a tela não entram em sono profundo (deep sleep) enquanto o dispositivo estiver recebendo alimentação.

### B. Manutenção de Conexão Wi-Fi Ativa no Standby
```bash
adb shell settings put global wifi_sleep_policy 2
adb shell settings put global wifi_suspend_optimizations_enabled 0
```
*Efeito:* Desativa as otimizações de suspensão do chip Wi-Fi, impedindo a perda da rota local e do IP na rede local.

### C. Desativação do Phantom Process Killer
```bash
adb shell "/system/bin/device_config put activity_manager max_phantom_processes 2147483647"
```
*Efeito:* Eleva o limite máximo de processos filhos secundários permitidos pelo Android para o valor máximo de inteiro de 32 bits, impedindo que o Android mate os workers do FFmpeg, Runit e Whisper.

### D. Whitelist de Economia de Bateria (DeviceIdle)
```bash
adb shell dumpsys deviceidle whitelist +com.termux
adb shell dumpsys deviceidle whitelist +com.termux.boot
```
*Efeito:* Isenta completamente o Termux e o plugin de boot do Doze Mode do Android.

### E. Concessão de Permissões Críticas de AppOps
```bash
adb shell cmd appops set com.termux RUN_IN_BACKGROUND allow
adb shell cmd appops set com.termux RUN_ANY_IN_BACKGROUND allow
adb shell cmd appops set com.termux WAKE_LOCK allow
```

---

## 3. Procedimento de Restauração em Caso de Reinicialização
Após um reboot completo do aparelho:
1. O aplicativo **Termux:Boot** inicializa automaticamente o script `~/.termux/boot/start-autoshorts.sh`.
2. O script adquire `termux-wake-lock`.
3. Dispara o gerenciador de serviços Runit (`runsvdir ~/service`).
4. Os 4 serviços essenciais sobem em menos de 2 segundos:
   - `autoshorts` (motor de produção e scheduler)
   - `autoshorts-web` (Web Studio na porta 8787)
   - `autoshorts-tunnel` (túnel Cloudflare para acesso global)
   - `sshd` (OpenSSH server na porta 8022)
