# AUDITORIA DE LICENÇAS E SEGURANÇA JURÍDICA

## 1. Política de Licenciamento
O AutoShorts opera estritamente com dependências permissivas (MIT, Apache 2.0, BSD) e binários dinamicamente vinculados de acordo com as diretrizes da LGPL 2.1 (FFmpeg).

## 2. Inventário de Licenças

| Pacote | Licença | Uso Comercial | Restrições |
|---|---|---|---|
| `pytest` | MIT | Permitido | Nenhuma restrição comercial |
| `aiohttp` | Apache 2.0 | Permitido | Preservação de notice |
| `requests` | Apache 2.0 | Permitido | Preservação de copyright |
| `autoshorts.c` | MIT | Proprietário / Permissivo | Código original AutoShorts |
| `ffmpeg` (binário) | LGPL 2.1+ | Permitido em chamadas CLI | Não estende GPL ao código Python hospedeiro |
