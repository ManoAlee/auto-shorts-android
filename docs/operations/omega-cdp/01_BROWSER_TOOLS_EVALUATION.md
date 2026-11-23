# Avaliação de Ferramentas e Protocolos de Automação de Navegadores

## 1. Escopo da Avaliação
Investigação técnica das ferramentas de referência para o subsistema **OMEGA CDP CONTROL ENGINE**, considerando a infraestrutura mista:
- **Dispositivo Primário:** Samsung Galaxy A55 5G (Android 17 / Termux aarch64, Chromium 157.0.8103.50, Node v24.22.2, Python 3.14.10)
- **Workstation Auxiliar:** Windows 11 Desktop (Edge / Chrome x64, Node v24.18.0, Python 3.13)

---

## 2. Matriz Comparativa de Ferramentas

| Ferramenta / Protocolo | Licença | Suporte Android/Termux | Suporte Windows | Consumo Típico de RAM | Veredito Arquitetural |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chrome DevTools Protocol (CDP)** | BSD-3-Clause | 100% Nativo (zero deps) | 100% Nativo | < 25 MB (in-process) | **ADOPT (Núcleo Principal)** |
| **Playwright (`@playwright/test`)** | Apache 2.0 | Complexo (sem driver aarch64 Android) | 100% Nativo | ~250 MB | **ADAPT (Worker Windows / E2E)** |
| **Puppeteer (`puppeteer-core`)** | Apache 2.0 | Viável via `puppeteer.connect` | 100% Nativo | ~120 MB | **REFERENCE (Fallback Node)** |
| **Selenium WebDriver** | Apache 2.0 | Frágil (chromedriver mismatch) | 100% Nativo | ~180 MB | **REJECT (Obsoleto)** |
| **Lighthouse** | Apache 2.0 | Viável via Node | 100% Nativo | ~300 MB | **ADOPT (Auditoria de UI)** |
| **Chrome DevTools MCP** | Apache 2.0 | Viável via Stdio / Node | 100% Nativo | ~60 MB | **ADOPT (Inspeção por Agentes)** |

---

## 3. Diretriz de Engenharia
1. **No Android / Termux:**
   O pipeline audiovisual e as operações de publicação em tempo real utilizam a camada **Omega Native CDP** em Python puro. Isso garante latência mínima (< 5ms de IPC), zero binários externos proprietários e consumo mínimo de memória RAM, respeitando as restrições do Android Low Memory Killer (LMK).
2. **Na Workstation Windows (Desktop Worker):**
   O ambiente Windows pode atuar como um **Visual QA Worker** opcional, executando Playwright e Chromium com interface gráfica completa para inspeção visual aprofundada, gravação de vídeos de auditoria e resolução interativa de desafios de autenticação (MFA / 2FA).
3. **Segurança do Endpoint:**
   O Chromium sempre escuta estritamente em `127.0.0.1` com porta dinâmica efêmera (`--remote-debugging-port=<ephemeral>`). Nenhuma porta de depuração é exposta na rede externa ou na Internet.
