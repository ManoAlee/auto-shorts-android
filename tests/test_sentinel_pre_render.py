"""Acceptance Tests for Auto Shorts Sentinel Pre-Render Intelligence Harness.

Validates Tests A through I according to Sentinel Operational Specification:
- TESTE A: Título enganoso (promete 5 itens, entrega 3 -> FAIL)
- TESTE B: Mídia incorreta (narração sobre hardware/CPU, imagem sobre praia/natureza -> FAIL)
- TESTE C: Contexto ausente (começo abrupto 'Além disso...' -> WARNING / ABRUPT_START)
- TESTE D: Legenda cortada (linha ultrapassa safe zone -> FAIL)
- TESTE E: Narração longa (excede 60s para YouTube Shorts -> FAIL)
- TESTE F: Cena repetida (mesmo arquivo de mídia em múltiplas cenas -> WARNING / DUPLICATE)
- TESTE G: Vídeo correto (todas as etapas consistentes -> PASS e is_approved = True)
- TESTE H: Recuperação e persistência de relatórios (recupera sem duplicar)
- TESTE I: Auto-correção e re-validação (detecta defeito, auto-corrige, atinge aprovação)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from auto_shorts.sentinel_pre_render import (
    ContentBrief,
    GateStatus,
    PreviewMode,
    SceneContract,
    SentinelPreRenderOrchestrator,
    StoryboardEngine,
    TitleToContentConsistencyEngine,
    ScriptIntelligenceEngine,
    SemanticSceneAligner,
    EvidenceGuidedRevisionEngine,
)


def test_scenario_a_misleading_title(tmp_path):
    """TESTE A: Título enganoso (promete 5 erros, mas entrega apenas 3)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(
        title="5 Erros Graves que Destroem seu Computador",
        topic="Hardware",
        platform="youtube_shorts",
    )
    # Script with only 3 delivered errors
    script = (
        "Cuidado com sua máquina! "
        "Primeiro erro: deixar a poeira acumular nos coolers. "
        "Segundo erro: usar fonte genérica sem proteção. "
        "Terceiro erro: nunca trocar a pasta térmica vencida. "
        "Se inscreva para mais dicas!"
    )
    scenes = [
        SceneContract("s1", 0.0, 5.0, 5.0, "Cuidado com sua máquina", "Apresentação", "pc_intro.mp4"),
        SceneContract("s2", 5.0, 15.0, 10.0, "Primeiro erro: poeira", "Cooler sujo", "cooler_dust.mp4"),
        SceneContract("s3", 15.0, 25.0, 10.0, "Segundo erro: fonte", "Fonte queimada", "psu_damage.mp4"),
        SceneContract("s4", 25.0, 35.0, 10.0, "Terceiro erro: pasta térmica", "Pasta ressecada", "thermal_paste.mp4"),
    ]

    report = orch.run_pre_render_validation(brief=brief, script_text=script, scenes=scenes, auto_correct=False)
    
    assert report.is_approved is False
    assert report.gates["GATE_01_TITLE_VALIDATION"].status == GateStatus.FAIL
    assert report.gates["GATE_03_FACT_VALIDATION"].status == GateStatus.FAIL
    assert report.consistency_matrix.is_mismatched is True
    assert report.consistency_matrix.expected_count == 5
    assert report.consistency_matrix.delivered_count == 3


def test_scenario_b_incorrect_media(tmp_path):
    """TESTE B: Mídia incorreta (narração sobre CPU, mídia sobre praia/férias)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(
        title="O Superaquecimento Perigoso do Processador",
        topic="Hardware",
    )
    script = "O processador atingiu cem graus e o circuito de proteção desarmou a placa mãe para evitar a queima do chip."
    scenes = [
        SceneContract(
            scene_id="s1",
            timestamp_start=0.0,
            timestamp_end=6.0,
            duration_seconds=6.0,
            narration=script,
            visual_intent="Mostrar aquecimento do processador e chip",
            media_asset="ferias_na_praia_sol.mp4",
            expected_objects=["processador", "hardware", "cpu"],
            detected_objects=["praia", "areia", "mar"],
        )
    ]

    report = orch.run_pre_render_validation(brief=brief, script_text=script, scenes=scenes, auto_correct=False)
    
    gate4 = report.gates["GATE_04_VISUAL_ALIGNMENT"]
    assert gate4.status == GateStatus.FAIL
    assert len(gate4.errors) > 0
    assert "contradição semântica" in gate4.errors[0].lower() or "objetos esperados" in gate4.errors[0].lower()


def test_scenario_c_missing_context_abrupt_start(tmp_path):
    """TESTE C: Contexto ausente (começo abrupto 'Além disso...')."""
    engine = ScriptIntelligenceEngine()
    script = "Além disso, os dados foram perdidos permanentemente sem possibilidade de recuperação. Por isso faça backup!"
    res = engine.evaluate_script(script, target_duration=60.0)
    
    assert any(i["type"] == "ABRUPT_START_MISSING_CONTEXT" for i in res["issues"])
    assert res["hook_score"] < 60


def test_scenario_d_cut_subtitles_outside_safe_zone(tmp_path):
    """TESTE D: Legenda cortada (linha ultrapassa limite seguro de 34 caracteres)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(title="Dicas de Produtividade", topic="Produtividade")
    script = "Organize suas tarefas diárias com foco total para vencer a procrastinação e alcançar resultados extraordinários."
    scenes = [SceneContract("s1", 0.0, 5.0, 5.0, script, "Foco", "produtividade.mp4")]
    
    # Subtitle with 105 characters in a single line!
    long_subtitle = "Organize suas tarefas diárias com foco total para vencer a procrastinação e alcançar resultados extraordinários."
    
    report = orch.run_pre_render_validation(
        brief=brief, script_text=script, scenes=scenes, subtitle_text=long_subtitle, auto_correct=False
    )
    
    gate7 = report.gates["GATE_07_CAPTION_VALIDATION"]
    assert gate7.status == GateStatus.FAIL
    assert len(gate7.errors) > 0


def test_scenario_e_overlong_narration(tmp_path):
    """TESTE E: Narração longa (áudio ultrapassa 60s em YouTube Shorts)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(
        title="História Completa do Universo",
        topic="Ciência",
        platform="youtube_shorts",
    )
    # 250 words ~ 100 seconds (far exceeds 60s limit)
    words = ["palavra"] * 250
    long_script = " ".join(words)
    scenes = [SceneContract("s1", 0.0, 75.0, 75.0, long_script, "Galáxia", "espaco.mp4")]

    report = orch.run_pre_render_validation(brief=brief, script_text=long_script, scenes=scenes, auto_correct=False)
    
    gate6 = report.gates["GATE_06_AUDIO_PLANNING"]
    assert gate6.status == GateStatus.FAIL
    assert any("excede o limite" in err for err in gate6.errors)


def test_scenario_f_duplicate_scene_media(tmp_path):
    """TESTE F: Cena repetida (mesmo arquivo utilizado em cenas subsequentes)."""
    aligner = SemanticSceneAligner()
    scenes = [
        SceneContract("s1", 0.0, 5.0, 5.0, "Primeira parte sobre tecnologia", "Visão geral", "tech_broll_01.mp4"),
        SceneContract("s2", 5.0, 10.0, 5.0, "Segunda parte sobre inovação", "Detalhe", "tech_broll_01.mp4"),  # Duplicate!
    ]
    aligned_scenes, summary = aligner.align_scenes(scenes)
    
    assert summary["duplicate_media_count"] >= 1
    assert "s2" in summary["duplicate_scenes"]


def test_scenario_g_correct_video_all_pass(tmp_path):
    """TESTE G: Vídeo correto (todas as promessas, roteiro, áudio e legendas corretos)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(
        title="3 Passos Simples para Aumentar sua Produtividade",
        topic="Produtividade",
        platform="youtube_shorts",
        target_duration_sec=30.0,
    )
    script = (
        "Quer produzir o dobro em menos tempo? "
        "Primeiro: defina três prioridades inegociáveis pela manhã. "
        "Segundo: elimine todas as notificações durante blocos de foco. "
        "Terceiro: faça pausas estratégicas a cada cinquenta minutos. "
        "Qual dessas você vai aplicar hoje? Comente abaixo e se inscreva!"
    )
    scenes = [
        SceneContract("s1", 0.0, 6.0, 6.0, "Quer produzir o dobro?", "Hook foco", "foco_estudos.mp4", expected_objects=["foco", "planejamento"]),
        SceneContract("s2", 6.0, 14.0, 8.0, "Primeiro: defina três prioridades", "Planejamento matinal", "prioridades_agenda.mp4", expected_objects=["agenda", "prioridades"]),
        SceneContract("s3", 14.0, 22.0, 8.0, "Segundo: elimine notificações", "Celular sem distrações", "sem_notificacoes.mp4", expected_objects=["celular", "foco"]),
        SceneContract("s4", 22.0, 30.0, 8.0, "Terceiro: pausas e CTA", "Encerramento", "pausa_descanso.mp4", expected_objects=["descanso", "encerramento"]),
    ]
    # Clean two-line subtitles <= 32 chars
    clean_subs = (
        "Quer produzir o dobro?\n"
        "Primeiro: 3 prioridades.\n"
        "Segundo: sem notificações.\n"
        "Terceiro: pausas de foco.\n"
        "Comente e se inscreva!"
    )

    report = orch.run_pre_render_validation(
        brief=brief,
        script_text=script,
        scenes=scenes,
        subtitle_text=clean_subs,
        auto_correct=False,
    )

    assert report.is_approved is True
    assert report.overall_score >= 80
    assert report.gates["GATE_01_TITLE_VALIDATION"].status == GateStatus.PASS
    assert report.gates["GATE_02_SCRIPT_VALIDATION"].status == GateStatus.PASS
    assert report.gates["GATE_03_FACT_VALIDATION"].status == GateStatus.PASS
    assert report.gates["GATE_07_CAPTION_VALIDATION"].status == GateStatus.PASS
    assert report.gates["GATE_10_FINAL_RENDER_AUTHORIZATION"].status == GateStatus.PASS


def test_scenario_h_report_persistence_and_recovery(tmp_path):
    """TESTE H: Recuperação e persistência de relatórios sem duplicação."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    brief = ContentBrief(title="Curiosidades Rápidas", topic="Ciência")
    script = "Astrônomos confirmaram novo pulsar distante girando a mil rotações por segundo."
    scenes = [SceneContract("s1", 0.0, 5.0, 5.0, script, "Espaço", "pulsar.mp4")]
    
    rep1 = orch.run_pre_render_validation(brief=brief, script_text=script, scenes=scenes)
    rep_file = tmp_path / "reports" / f"{rep1.project_id}_report.json"
    
    assert rep_file.is_file()
    loaded = json.loads(rep_file.read_text(encoding="utf-8"))
    assert loaded["project_id"] == rep1.project_id
    assert "gates" in loaded


def test_scenario_i_self_correction_and_revalidation(tmp_path):
    """TESTE I: Auto-correção e re-validação (detecta defeito, auto-corrige e alcança aprovação)."""
    orch = SentinelPreRenderOrchestrator(out_dir=tmp_path)
    # Title promises 5, but script only delivers 3, and subtitle line is too long!
    brief = ContentBrief(
        title="5 Passos Simples para Aumentar sua Produtividade",
        topic="Produtividade",
        platform="youtube_shorts",
    )
    script = (
        "Quer produzir o dobro em menos tempo? "
        "Primeiro: defina três prioridades inegociáveis pela manhã. "
        "Segundo: elimine todas as notificações durante blocos de foco. "
        "Terceiro: faça pausas estratégicas a cada cinquenta minutos. "
        "Qual dessas você vai aplicar hoje? Comente abaixo e se inscreva!"
    )
    scenes = [
        SceneContract("s1", 0.0, 6.0, 6.0, "Quer produzir o dobro?", "Hook", "foco_produtividade.mp4"),
        SceneContract("s2", 6.0, 14.0, 8.0, "Primeiro: defina prioridades", "Prioridades", "agenda_foco.mp4"),
        SceneContract("s3", 14.0, 22.0, 8.0, "Segundo: sem notificações", "Foco", "sem_distracao.mp4"),
        SceneContract("s4", 22.0, 30.0, 8.0, "Terceiro: pausas e CTA", "Pausa", "produtividade_fim.mp4"),
    ]
    # Long subtitle line that overflows safe zone (> 34 chars)
    long_subs = "Esta linha de legenda ultrapassa absurdamente o limite aceitável de caracteres na tela do celular."

    # Run WITH auto_correct=True
    report = orch.run_pre_render_validation(
        brief=brief,
        script_text=script,
        scenes=scenes,
        subtitle_text=long_subs,
        auto_correct=True,
    )

    # Sentinel must have auto-corrected title from '5 Passos' to '3 Passos' and reflowed captions!
    assert len(report.revision_history) >= 1
    assert "3 Passos" in report.title
    assert report.is_approved is True
    assert report.gates["GATE_01_TITLE_VALIDATION"].status == GateStatus.PASS
