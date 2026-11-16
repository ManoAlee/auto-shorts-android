import pytest
from auto_shorts.viral_intelligence import (
    AntiSlopHumanizer,
    VIRAL_HOOK_FORMULAS,
    build_zeigarnik_loop_cta,
    generate_beat_sheet,
    score_hook,
)


def test_anti_slop_humanizer_removes_invisible_and_cliches():
    # Invisible chars and AI cliches
    raw = "No mundo de hoje\u200b, vamos mergulhar\ufeff neste vídeo você vai aprender o segredo revolucionário!"
    cleaned = AntiSlopHumanizer.clean(raw)

    assert "\u200b" not in cleaned
    assert "\ufeff" not in cleaned
    assert "No mundo de hoje" not in cleaned
    assert "vamos mergulhar" not in cleaned
    assert "revolucionário" not in cleaned
    assert len(cleaned) > 0


def test_score_hook_strong():
    # High stakes, concrete numbers, direct address, under 12 words
    spoken = "Pare de errar isso agora! Esse único erro te custou R$ 18.000."
    on_screen = "ERRO DE R$ 18.000"
    res = score_hook(spoken, on_screen)

    assert res.composite_score >= 70.0
    assert res.grade in ("STRONG", "VIABLE")
    assert res.matched_formula == "Cost Confession"
    assert not res.has_greeting_penalty
    assert res.length_words <= 14


def test_score_hook_penalizes_robot_greeting_and_fluff():
    # Monotonous robot opening
    spoken = "Olá pessoal, bom dia, sejam bem-vindos ao meu canal, hoje vamos falar sobre..."
    res = score_hook(spoken)

    assert res.has_greeting_penalty
    assert res.composite_score < 50.0
    assert res.grade == "WEAK"
    assert any("saudação" in s.lower() for s in res.suggestions)


def test_dual_hook_generation():
    spoken, banner = AntiSlopHumanizer.generate_dual_hook(
        hook_title="O maior erro que destrói sua conta em 24 horas",
        spoken_first_line="Se você cometer esse erro, sua conta cai em 24h.",
    )

    assert len(banner.split()) <= 6
    assert banner.isupper()
    assert "24" in banner or "ERRO" in banner
    assert "24h" in spoken


def test_beat_sheet_pacing():
    beats = generate_beat_sheet(35.0)
    assert len(beats) == 5
    assert beats[0].name == "HOOK"
    assert beats[0].end_sec <= 2.8
    assert beats[-1].name == "LOOP"


def test_zeigarnik_loop_cta():
    loop_line = build_zeigarnik_loop_cta("Nunca cometa esse erro financeiro.")
    assert "nunca cometa" in loop_line.lower() or "erro" in loop_line.lower()


def test_mcp_viral_tools():
    from auto_shorts.autoshorts_mcp import _build_internal_registry

    reg = _build_internal_registry()
    assert "viral.score_hook" in reg
    assert "viral.anti_slop" in reg
    assert "viral.beat_sheet" in reg
    assert "viral.list_formulas" in reg

    # Call viral.score_hook
    hook_tool = reg["viral.score_hook"]["handler"]
    h_res = hook_tool({"spoken_text": "Pare de gastar dinheiro à toa! Isso custou R$ 5000.", "on_screen_text": "PREJUÍZO DE 5 MIL"})
    assert h_res["composite_score"] >= 65.0
    assert h_res["grade"] in ("STRONG", "VIABLE")

    # Call viral.anti_slop
    slop_tool = reg["viral.anti_slop"]["handler"]
    s_res = slop_tool({"text": "No mundo de hoje vamos mergulhar nesta dica revolucionária!"})
    assert s_res["changed"] is True
    assert "No mundo de hoje" not in s_res["cleaned"]

    # Call viral.beat_sheet
    beat_tool = reg["viral.beat_sheet"]["handler"]
    b_res = beat_tool({"duration_sec": 40.0})
    assert len(b_res["beats"]) == 5

    # Call viral.list_formulas
    form_tool = reg["viral.list_formulas"]["handler"]
    f_res = form_tool({})
    assert len(f_res["formulas"]) >= 8
