# Development: Contributing Guide

We welcome contributions to AutoShorts! Please review these guidelines before submitting pull requests.

---

## 1. Development Workflow

1. **Fork & Branch:** Create a dedicated branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Implement Surgically:** Keep changes focused on a single responsibility.
3. **Write Tests:** Add unit tests covering new logic or bug fixes in `tests/`.
4. **Run Verification:** Confirm `PYTHONPATH=src pytest tests -q` passes 100%.
5. **Commit Cleanly:** Use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).

---

## 2. Commit Message Convention

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat: add new sports niche narrative profile`
- `fix: resolve subtitle safe-zone clipping on curved displays`
- `docs: update Sentinel Quality Gate mathematical formula`
- `test: add unit tests for RSS anti-stub filter`

---

## 3. Pull Request Requirements

Every pull request must:
- Fill out the [PULL_REQUEST_TEMPLATE.md](file:///c:/Users/alessandro.meneses.Automotion/Documents/01_Projetos_TI/linux-android/auto-shorts-android/.github/PULL_REQUEST_TEMPLATE.md).
- Pass all automated CI checks across Python 3.11, 3.12, and 3.13.
- Maintain zero hardcoded secrets or credentials.
- Preserve mobile ARM64 performance and memory bounds (<350 MB RAM).
