# REGISTRO CIRÚRGICO DE BUGS E DEFEITOS CORRIGIDOS

## 1. Tabela de Correções Implementadas

| ID | Sintoma Original | Causa Raiz Técnica | Correção Aplicada |
|---|---|---|---|
| **BUG-01** | Termux fechava sozinho sem log de erro. | Android LMK `reason=3 (LOW_MEMORY)` disparado por 8 processos Chromium zumbis consumindo 1.6GB. | `preexec_fn=os.setsid`, terminação por PGID (`os.killpg`), `malloc_trim(0)` e whitelist do One UI. |
| **BUG-02** | Queda de rede / SSH ao mudar de Wi-Fi ou desconectar USB. | IP DHCP instável e suspensão seletiva USB do Windows desfazendo `adb forward`. | `autoshorts_sentinel.ps1` no startup do Windows e IP estático na malha Tailscale. |
| **BUG-03** | Erro 501 Unsupported Method em requisições HEAD no player de vídeo. | Falta de implementação do método `do_HEAD` em `webapp.py`. | Adicionado `def do_HEAD(self): return self.do_GET()` em `AppHandler`. |
| **BUG-04** | Erro `ERR_CONNECTION_RESET` no navegador ao tentar avançar o vídeo. | Leitura síncrona total de arquivos MP4 grandes em buffer único. | Streaming RFC 7233 em chunks de 64KB com suporte a `206 Partial Content`. |
| **BUG-05** | `OSError: Address already in use` ao reiniciar o servidor web. | Falta de flags de reuso de socket ao religar a porta 8787. | Configurado `SO_REUSEPORT` e `SO_REUSEADDR` em `_StudioHTTPServer`. |
| **BUG-06** | `NameError: name 're' is not defined` em `publisher.py:646`. | Chamada a `re.sub` sem importação de `re` no topo do módulo. | Adicionado `import re` no escopo superior de `publisher.py`. |
| **BUG-07** | `AssertionError` de `is_internet_online` em `test_pipeline.py`. | Função `is_internet_online` ausente na compilação do C11 Aegis. | Implementada rotina `static int is_internet_online(void)` em `native-c/autoshorts.c`. |
| **BUG-08** | Quebra de texto de legendas nas bordas do TikTok e Shorts. | Ausência de restrição de safe zones verticais 9:16. | Criação de `SafeZoneSpec` delimitando caixa `(60, 220, 940, 1540)` e estilo ASS. |
