# Repository Guidelines

## Project Structure & Module Organization
- Current contents: `brainstorm.txt` (project concept and architecture notes). No source code or tests yet.
- When implementation starts, keep top-level folders predictable: `src/` for application code, `tests/` for automated tests, and `assets/` for images/shader samples.
- Store experiments and scratch work in `notes/` or `research/` to keep `src/` focused on shipped code.

## Build, Test, and Development Commands
- No build or run commands are defined yet.
- When adding tooling, prefer simple entry points such as:
  - `npm run dev` or `python -m <module>` for local development.
  - `npm test` or `pytest` for automated tests.
- Document the canonical commands in `README.md` once they exist.

## Coding Style & Naming Conventions
- No formatter or linter is configured yet.
- Until standards are added, keep style consistent within each file and favor clear, descriptive names (e.g., `texture_signature`, `render_shader`).
- If you introduce a formatter (e.g., Prettier, black, gofmt), run it on touched files before committing.

## Testing Guidelines
- No testing framework is set up.
- If tests are added, keep naming explicit (e.g., `test_similarity_score.py`, `shader_eval.test.ts`).
- Aim to cover core loop pieces: image analysis, shader synthesis, render pipeline, and evaluation metrics.

## Commit & Pull Request Guidelines
- No commit message convention is established (there is no Git history in this repo).
- Suggested default: Conventional Commits (`feat:`, `fix:`, `docs:`) to keep history readable.
- For pull requests, include a short summary, testing notes, and screenshots or sample renders when visuals change.

## Agent-Specific Notes
- This repo is currently a planning document. If you add implementation, keep changes small and incremental so the architecture in `brainstorm.txt` remains aligned with the code.
