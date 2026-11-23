# Especificação de Visual QA e Repositório de Evidências

## 1. O Conceito de Visual QA Pós-Publicação
Uma publicação na web não deve ser declarada como concluída apenas porque uma chamada de rede retornou código HTTP 200. É essencial auditar a **página real do consumidor final**.

O **Visual QA Inspector** (`src/auto_shorts/omega_cdp/visual_qa.py`) executa o fechamento do ciclo de garantia de qualidade (Closed-Loop Verification):
1. Aguarda o tempo necessário para o processamento de vídeo nos servidores da plataforma (geralmente entre 10s e 45s).
2. Carrega a URL pública do vídeo (`youtube.com/shorts/<id>`, `tiktok.com/@creator/video/<id>`, `instagram.com/reel/<id>`).
3. Aguarda a renderização completa dos componentes de interface (`document.readyState === 'complete'`).
4. Captura uma fotografia digital de alta fidelidade (JPEG 85% de qualidade) do player de vídeo.
5. Inspeciona o título público exibido, a presença de capa e a inexistência de mensagens de indisponibilidade ou erro 404.
6. Emite o documento estruturado `evidence.json`.

---

## 2. Estrutura do Diretório de Evidências
Cada tarefa possui um repositório isolado de auditoria:

```text
output/evidence/
  └── omega_youtube_173460_a1b2c3/
        ├── visual_qa_ev_173460_f8e9d0.jpg   <-- Screenshot real do Short ao vivo
        └── evidence.json                     <-- Metadados de auditoria técnica
```

### Exemplo de Registro Estruturado (`evidence.json`):
```json
{
  "evidence_id": "ev_173460_f8e9d0",
  "task_id": "omega_youtube_173460_a1b2c3",
  "platform": "youtube",
  "url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
  "screenshot_path": "output/evidence/omega_youtube_173460_a1b2c3/visual_qa_ev_173460_f8e9d0.jpg",
  "page_title": "Luffy Nova Transformacao One Piece - YouTube",
  "verified_status": "ONLINE",
  "title_matches": true,
  "discrepancies": [],
  "timestamp": 173460124.582,
  "metadata": {
    "file_size_bytes": 184520
  }
}
```

---

## 3. Critérios de Aprovação e Rejeição Visual
* **ONLINE (Aprovado):** Player carregado, reprodução de vídeo disponível, título compatível com a produção local, sem telas de erro. Tarefa transiciona para `VERIFIED`.
* **UNAVAILABLE (Falha):** Título indica vídeo indisponível, processamento travado, ou página 404. Tarefa transiciona para `FAILED` com justificativa registrada no histórico.
