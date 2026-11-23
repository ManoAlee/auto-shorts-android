# RECUPERAÇÃO TRANSACIONAL DE JOBS E PERSISTÊNCIA

## 1. Modelo Transacional de Duas Fases (2PC)
Para evitar corrupção de estado durante quedas de energia ou desconexões de rede, todas as tarefas de produção e publicação utilizam commits atômicos em disco:
1. Os dados da tarefa são gravados em arquivo temporário (`output/omega_tasks/<task_id>.tmp`).
2. O arquivo é validado estruturalmente.
3. É executado um rename atômico (`os.replace`) para o arquivo final `.json`.

## 2. Recuperação Automática de Tarefas Pendentes
Ao iniciar o sistema ou após um reinício de serviço:
- O orquestrador escaneia `output/omega_tasks/` e `output/studio_evidence/`.
- Tarefas que se encontravam em estado transitório (`UPLOADING` ou `IN_PROGRESS`) são reavaliadas.
- Tarefas interrompidas são reiniciadas a partir do último checkpoint estável, sem duplicar downloads ou renderizações completas.
