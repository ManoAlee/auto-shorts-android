"""Visual QA Inspector — Autonomous post-publish verification, visual evidence capture, and metadata reconciliation."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .engine import OmegaCDPEngine
from .models import PublishState, PublishTask, VisualEvidence

logger = logging.getLogger("autoshorts.omega_cdp.visual_qa")


class VisualQAInspector:
    """Inspeciona visualmente a publicação ao vivo no navegador e gera evidência fotográfica estruturada."""

    def __init__(self, evidence_dir: Path | str = "output/evidence") -> None:
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def inspect_publication(
        self,
        task: PublishTask,
        engine: OmegaCDPEngine,
    ) -> VisualEvidence:
        """Navega até a URL pública do vídeo, captura screenshot e valida metadados visuais."""
        target_url = task.remote_url
        if not target_url or not target_url.startswith(("http://", "https://")):
            raise ValueError(f"Tarefa {task.task_id} nao possui URL remota valida: {target_url}")

        evidence_id = f"ev_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task_evidence_dir = self.evidence_dir / task.task_id
        task_evidence_dir.mkdir(parents=True, exist_ok=True)
        screenshot_file = task_evidence_dir / f"visual_qa_{evidence_id}.jpg"

        # 1. Navegar até a publicação oficial
        engine.navigate(target_url, wait_complete=True)
        time.sleep(2.0)  # Aguardar renderização de componentes de player web

        # 2. Captura de evidência visual
        engine.capture_screenshot(screenshot_file, quality=85)

        # 3. Inspeção de DOM e metadados
        live_title = engine.get_title()
        discrepancies: List[str] = []

        # Detecção de páginas de erro (ex: 404, vídeo removido)
        if any(err in live_title.lower() for err in ("não disponível", "not available", "404", "error", "removido")):
            discrepancies.append(f"Pagina indica video indisponivel: '{live_title}'")
            verified_status = "UNAVAILABLE"
            title_matches = False
        else:
            verified_status = "ONLINE"
            # Verificar se palavras centrais do título aparecem na página
            expected_words = set(w.lower() for w in task.title.split() if len(w) > 3)
            page_text = str(engine.eval_js("document.body?.innerText || ''")).lower()
            matches_count = sum(1 for w in expected_words if w in page_text or w in live_title.lower())
            title_matches = matches_count >= max(1, len(expected_words) // 2)
            if not title_matches:
                discrepancies.append(f"Titulo local '{task.title}' nao foi localizado no texto da pagina ao vivo.")

        evidence = VisualEvidence(
            evidence_id=evidence_id,
            task_id=task.task_id,
            platform=task.platform.value if hasattr(task.platform, "value") else str(task.platform),
            url=target_url,
            screenshot_path=str(screenshot_file),
            page_title=live_title,
            verified_status=verified_status,
            title_matches=title_matches,
            discrepancies=discrepancies,
            timestamp=time.time(),
            metadata={"file_size_bytes": screenshot_file.stat().st_size if screenshot_file.exists() else 0},
        )

        # Persistir relatório atômico da evidência
        report_file = task_evidence_dir / "evidence.json"
        report_file.write_text(json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Atualizar tarefa
        task.visual_evidence_id = evidence_id
        if verified_status == "ONLINE":
            task.state = PublishState.VERIFIED
        else:
            task.state = PublishState.FAILED
            task.last_error = f"Inspecao visual falhou: {'; '.join(discrepancies)}"
        task.updated_at = time.time()

        logger.info("Evidencia visual gerada para tarefa %s: %s (Status: %s)", task.task_id, evidence_id, verified_status)
        return evidence
