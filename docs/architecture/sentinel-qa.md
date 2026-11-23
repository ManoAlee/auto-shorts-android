# Sentinel Pre-Render QA Architecture

The **AutoShorts Sentinel** subsystem is a pre-render multimodal validation engine. It evaluates content briefs, scripts, audio tracks, and storyboard manifests *before* committing CPU and battery resources to full video rendering.

---

## 1. The 10 Quality Gates

| Gate ID | Name | Threshold | Description |
|---|---|---|---|
| `GATE_01` | **Title Relevance** | Score >= 70 | Validates semantic similarity between title CTR hooks and story content. |
| `GATE_02` | **Hook Energy** | Score >= 75 | Evaluates Act 1 words, curiosity gap, and first 3 seconds retention triggers. |
| `GATE_03` | **Narrative Coherence** | Score >= 70 | Verifies standard 3-act narrative progression (Hook, Tension, Payoff). |
| `GATE_04` | **Scene Framing** | Score >= 70 | Checks vertical 9:16 safe zones, UI occlusion margins, and text density. |
| `GATE_05` | **Pacing & Cadence** | Score >= 70 | Analyzes speech words-per-minute (WPM target: 140-175 WPM for mobile). |
| `GATE_06` | **Visual Contrast** | Score >= 70 | Ensures subtitle legibility over dynamic backgrounds (contrast ratio >= 4.5:1). |
| `GATE_07` | **Audio Balance** | Score >= 75 | Verifies speech peak levels (-1 dBTP) and signal-to-noise separation. |
| `GATE_08` | **Thumbnail Promise** | Score >= 70 | Matches poster visual promise with the opening hook to prevent bait-and-switch. |
| `GATE_09` | **SEO & Discovery** | Score >= 65 | Audits niche hashtags, description metadata, and search visibility tags. |
| `GATE_10` | **Safety & Tone** | Score >= 80 | Detects false-positive tragedy obituaries and enforces community guidelines. |

---

## 2. Mathematical Scoring Formula

The overall Sentinel quality score ($S_{total}$) is calculated as a weighted normalized sum across all 10 gate scores ($g_i$) with corresponding weights ($w_i$):

$$S_{total} = \sum_{i=1}^{10} w_i \cdot g_i \quad \text{where} \quad \sum_{i=1}^{10} w_i = 1.0$$

### Decision Boundaries:
- **`APPROVE` ($S_{total} \ge 75$):** Passed all essential gates; safe to render.
- **`REMEDIATE` ($60 \le S_{total} < 75$):** Trigger automated heuristic repairs (e.g. rewrite hook, rebalance WPM, adjust subtitle styling) and re-validate.
- **`REJECT` ($S_{total} < 60$):** Discard invalid story pack; abort render immediately without wasting CPU cycles.

---

## 3. Integration Point in Pipeline

In `src/auto_shorts/world_news.py`:
```python
from .sentinel_pre_render import SentinelPreRenderOrchestrator

orchestrator = SentinelPreRenderOrchestrator(out_dir=out_path / "sentinel")
eval_result = orchestrator.run_pre_render_validation(
    brief=brief,
    manifest=manifest,
    audio_path=audio_path,
    project_id=project_id,
)

if eval_result.decision == "REJECT":
    raise ValueError(f"Sentinel Pre-Render Rejection: {eval_result.summary}")
```
All evaluation logs and gate metrics are permanently serialized into `output/sentinel/reports/<project_id>_report.json` and attached to the video's `.publish.json` metadata bundle.
