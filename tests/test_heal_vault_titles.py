import json
import sys
from pathlib import Path

# Add scripts directory
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from heal_vault_titles import heal_single_pack, is_title_problematic


def test_is_title_problematic():
    assert is_title_problematic("GTA 6 Ao Vivo: Gaules (Parte 1) | Gameplay #Shorts") is True
    assert is_title_problematic("Histórias Bizarras e Assustadoras do Reddit (r/nosleep) (Parte 10)") is True
    assert is_title_problematic("Nova espécie de perereca é descoberta em Minas Gerais | Plantão Economia") is True
    assert is_title_problematic("Carlos Alcaraz vence Zverev e conquista título inédito do ATP | Plantão Tech") is True
    assert is_title_problematic("Samsung agora permite bloquear apps individualmente | Plantão Tech") is False


def test_heal_single_pack(tmp_path):
    pack_data = {
        "title": "GTA 6 Ao Vivo: LipaoGamer (Parte 2) | Gameplay #Shorts",
        "caption": "GTA 6 Ao Vivo: LipaoGamer (Parte 2) | Gameplay #Shorts\n\nLipao jogando ao vivo lançamento!",
        "clip_summary": "A polícia veio com helicópteros e tanques durante a fuga espetacular.",
        "niche": "games_gta6",
    }
    json_path = tmp_path / "short_live_lipaogamer_1234_p02.publish.json"
    json_path.write_text(json.dumps(pack_data), encoding="utf-8")

    res = heal_single_pack(json_path, dry_run=False)
    assert res is not None
    old_t, new_t = res
    assert old_t == "GTA 6 Ao Vivo: LipaoGamer (Parte 2) | Gameplay #Shorts"
    assert new_t != old_t
    assert "LipaoGamer" in new_t

    updated = json.loads(json_path.read_text(encoding="utf-8"))
    assert updated["title"] == new_t
    assert updated["youtube_title"] == new_t
    assert new_t in updated["caption"]
