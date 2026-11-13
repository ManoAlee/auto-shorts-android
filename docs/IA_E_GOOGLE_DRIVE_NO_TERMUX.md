# IA local e Google Drive no Termux

## Como a IA roda hoje

- O aparelho é `aarch64`, com 7,25 GiB de RAM total e cerca de 3 GiB disponíveis durante a inspeção.
- Está instalado `qwen2.5-1.5b-instruct-q4_k_m.gguf` (aprox. 1,1 GiB) e o binário `llama-cli`.
- `llama-server` não está ativo continuamente. O app usa inferência sob demanda via `llama-cli` em tarefas compatíveis, evitando manter o modelo residente e disputar RAM com FFmpeg, Kokoro e o Android.
- Uma execução real no celular gerou a resposta de prova a cerca de 16,4 tokens/s; a recomendação de modelo agora considera a RAM livre e dá preferência ao GGUF instalado.
- A síntese de voz offline é feita pelo Kokoro ONNX PT-BR. `active_model` agora distingue o modelo realmente servido de arquivos GGUF apenas instalados.
- Notícias sem um resumo factual suficiente deixam de receber texto genérico inventado; o radar tenta a próxima matéria com resumo. Os roteiros locais usam a manchete e o resumo da fonte, sem alegações prontas sobre mercado ou impacto no Brasil.
- O radar ignora listas de compras e ofertas; na tela do acervo, a descrição agora extrai o texto falado em vez de copiar título, CTA e hashtags. Títulos de cortes respeitam limites sem truncar palavras ou o número da parte.
- O acervo inspecionado tinha 45 vídeos, 38 títulos únicos e 5 grupos com títulos repetidos. A interface agora distingue nota técnica automática de resultado real e oferece registro manual de visualizações, retenção, curtidas, compartilhamentos e salvamentos.
- O banco tinha 110 cortes avaliados pelo motor e nenhum com feedback de audiência (0%). A rotação UCB1 de fundos reflete avaliação técnica visual, não desempenho de público; o novo formulário e endpoint gravam métricas reais para orientar futuras recomendações.

## Google Drive: fluxo e pastas

O conector existente é o `rclone` configurado no Termux. Não é o conector Google Drive da skill de Workspace, que depende de outra autenticação.

1. O Sentinel consulta `gdrive:Animes_Para_Cortar`.
2. O arquivo é baixado para o processamento local; o vídeo original processado vai para `gdrive:Animes_Processados`.
3. Shorts e capas passam a ser organizados em `gdrive:Shorts_Finalizados/<categoria>/<AAAA-MM-DD>/`.
4. Se o rclone ou a pasta falhar, a listagem agora sinaliza erro. O Sentinel pausa esse ciclo em vez de interpretar erro de autenticação como “pasta vazia” e iniciar uma busca alternativa na web.

O teste real de leitura em 13/11/2026 conectou ao Drive: `Animes_Para_Cortar` estava vazio; `Shorts_Finalizados` já tinha pastas `Animes`, `Geral`, `Noticias_Tech` e arquivos antigos na raiz. A integração foi validada sem enviar, mover ou excluir arquivos.

## Ação necessária: client ID do rclone

O rclone no aparelho avisou que usa o `client_id` compartilhado do próprio rclone. A documentação oficial informa que esse cliente será desativado durante 2026; a própria listagem no aparelho mostrou o aviso. Configure um OAuth client próprio no Google Cloud e atualize o remote `gdrive` com `rclone config`, preservando a pasta de configuração e o token atual até confirmar a nova autorização. Não coloque `client_secret`, `token` ou `rclone.conf` no Git nem em logs.

Procedimento oficial: [rclone Google Drive — criar seu próprio client ID](https://rclone.org/drive/#making-your-own-client-id). Este projeto não tenta trocar credenciais automaticamente.

## Decisões de execução local

- `llama.cpp` suporta AArch64 e a documentação descreve opções específicas de Android; otimização com outro backend só deve ocorrer após medir o binário instalado no telefone. Referência: [build e backends oficiais do llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- Kokoro ONNX permite síntese por blocos e tempos de pausa entre sentenças; o fluxo atual usa blocos curtos para manter o uso de memória e permite ajustes graduais de prosódia. Referência: [API oficial do kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx).
- O benchmark de CPU heurística não é uma medição da velocidade de geração do Qwen. Para uma decisão de trocar modelo, aumentar contexto ou iniciar servidor permanente, registre TTFT, tokens/segundo, memória livre e duração de uma amostra real no mesmo aparelho.

## Verificações

- `tests/test_ai_drive_quality.py` cobre notícias sem resumo, filtro de ofertas, títulos, extração de resumos, RAM segura, caminhos do rclone, falhas do Drive, feedback observado, seleção de B-roll por nicho, cobertura de legenda, voz real do Kokoro e metadados por plataforma.
- `python -m pytest tests -q` passou com 101 testes.
- `python -m compileall -q src/auto_shorts tests/test_ai_drive_quality.py` passou.
- `git diff --check` apontou apenas linhas em branco finais já presentes em outros arquivos modificados; os arquivos desta mudança não tiveram erro de whitespace.

## Projetos de referência pesquisados

- [llama.cpp](https://github.com/ggml-org/llama.cpp): compatível com AArch64/Android; é a base mais próxima do fluxo Termux instalado. A prioridade é melhorar prompts e telemetria antes de aumentar o modelo.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx): geração ONNX local, adequada ao caminho de voz offline já usado pelo app.
- [AutoClip](https://github.com/artbyjazi/autoclip) e [Chopify](https://github.com/mehbul/chopify): boas referências para revisão humana, processamento retomável e organização por projeto; seus stacks não devem ser copiados para o Android sem avaliar consumo, dependências e compatibilidade com Termux.
