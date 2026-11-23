# Matriz de Testes de Aceitação — AUTO SHORTS SENTINEL

## 1. Suíte de Testes Implementada

A confiabilidade do subsistema Sentinel Pre-Render é atestada pela suíte em `tests/test_sentinel_pre_render.py`, cobrindo 9 cenários de aceitação rigorosos (Cenários A a I):

| Teste | Cenário | Condição Injetada | Comportamento Esperado | Resultado |
|---|---|---|---|---|
| **Test A** | `test_scenario_a_title_claim_mismatch` | Título promete "5 Dicas", roteiro só lista 2 itens | Gate 01 e Gate 03 falham (`NUMERICAL_PROMISE_UNMET`) | **PASS** (100%) |
| **Test B** | `test_scenario_b_visual_semantic_contradiction` | Narração sobre CPU e placas-mãe associada a vídeo com tags `praia, ondas, sol` | Gate 04 falha (`VISUAL_CONTRADICTION_DETECTED`) | **PASS** (100%) |
| **Test C** | `test_scenario_c_caption_safe_zone_overflow` | Legenda longa com mais de 34 caracteres em uma única linha sem quebra | Gate 05 falha (`CAPTION_SAFE_ZONE_OVERFLOW`) | **PASS** (100%) |
| **Test D** | `test_scenario_d_weak_hook_and_ai_slop` | Gancho começa com clichê: *"Você já se perguntou no vídeo de hoje..."* | Gate 02 e Gate 07 emitem `WARNING`/`FAIL` por anti-slop | **PASS** (100%) |
| **Test E** | `test_scenario_e_storyboard_manifest_generation` | Geração completa de manifesto de storyboard e página HTML | Arquivo HTML gerado com cards, overlay de safe zone e CSS responsivo | **PASS** (100%) |
| **Test F** | `test_scenario_f_low_cost_proxy_preview` | Solicitação de preview em modo `FULL_PROXY_PREVIEW` | Proxy gerado em `360x640` com tempo de execução < 3.0s | **PASS** (100%) |
| **Test G** | `test_scenario_g_correct_video_all_pass` | Vídeo coeso, com título condizente, sem contradições, sem slop e legendas conformes | Todos os 10 Gates retornam `PASS` e pontuação geral >= 75% | **PASS** (100%) |
| **Test H** | `test_scenario_h_evidence_guided_auto_revision` | Projeto com discrepância de contagem e legendas estouradas submetido ao corretor | Auto-revisão corrige contagem do título e refatora legendas em palavras | **PASS** (100%) |
| **Test I** | `test_scenario_i_end_to_end_orchestrator` | Pipeline mestre executado do início ao fim com auto-revisão ativada | Relatório `SentinelReport` persistido em disco com status aprovado | **PASS** (100%) |

---

## 2. Evidência de Execução dos Testes

```
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\alessandro.meneses.Automotion\Documents\01_Projetos_TI\linux-android\auto-shorts-android
configfile: pytest.ini
collected 15 items

tests/test_heal_vault_titles.py ...                                      [ 20%]
tests/test_sentinel_pre_render.py .........                              [ 80%]
tests/test_viral_titling.py ...                                          [100%]

============================== 15 passed in 0.61s ==============================
```
