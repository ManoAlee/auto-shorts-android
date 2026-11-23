# Operations: Incident Runbook

Standard operating procedures for maintaining video vault integrity and service uptime.

---

## 1. Vault Healing & Metadata Repair

### Scenario:
Video titles or hashtags in the vault become corrupted, mismatched, or out of sync with video topics.

### Procedure:
Run the dedicated vault healing utility:
```bash
python scripts/heal_vault_titles.py
```
This utility:
1. Inspects all `.publish.json` files in `output/`.
2. Validates video topics against story captions and niche keywords.
3. Strips duplicated headline text from Act 2 narration bodies.
4. Updates JSON metadata atomically without re-rendering video MP4s.

---

## 2. Orphaned Media Purge

### Scenario:
Failed renders or aborted jobs leave incomplete temporary files consuming disk space.

### Procedure:
Run the clean-slate storage sweep:
```bash
python scripts/wipe_and_protect_vault.py --clean-orphans
```

---

## 3. Termux Environment Migration & Reinstallation

### Scenario:
Migrating AutoShorts to a new Android device or recovering from a corrupted Termux environment.

### Procedure:
```bash
git clone https://github.com/ManoAlee/auto-shorts-android.git
cd auto-shorts-android
bash scripts/migrate_termux_github.sh
```
The migration script automatically restores directory permissions, re-links B-roll catalogs, and validates Python dependencies.
