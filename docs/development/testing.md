# Development: Automated Testing Guide

AutoShorts maintains a comprehensive test suite covering core story generation, Sentinel pre-render quality gating, Web Studio REST APIs, and multiplatform publishing contracts.

---

## 1. Test Directory Structure

```text
tests/
├── test_api_videos.py          <- Web Studio REST API video listing & metadata
├── test_contracts.py           <- StoryboardManifest, ContentBrief data contracts
├── test_mahoraga.py            <- Mahoraga 3-act story generation & tragedy filters
├── test_sentinel_pre_render.py <- 10 Sentinel Quality Gates & acceptance scenarios
├── test_titling.py             <- Viral titling & CTR hook heuristics
├── test_webapp.py              <- Web Studio HTTP server & endpoint routing
└── test_world_news.py          <- RSS ingestion, anti-stub filtering, story pack synthesis
```

---

## 2. Running Tests

### Standard Test Execution:
```bash
PYTHONPATH=src pytest tests -q
```

### Running Sentinel Pre-Render Acceptance Tests:
```bash
PYTHONPATH=src pytest tests/test_sentinel_pre_render.py -v
```

### Generating Coverage Reports:
```bash
PYTHONPATH=src pytest tests --cov=auto_shorts --cov-report=term-missing
```

---

## 3. Test Writing Conventions

- **Fast & Deterministic:** Unit tests must not depend on live external network connections (mock RSS feeds and external APIs).
- **Temporary Directories:** Always use `tmp_path` fixtures for filesystem tests to prevent polluting `output/`.
- **ARM64 Compatibility:** Never introduce platform-specific binaries in tests without corresponding OS/arch guards.
