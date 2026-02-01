# Shader Agent MVP

This repository contains two phases of the shader agent:
- **Phase I (legacy):** noise-focused loop with hand-crafted scoring.
- **Phase II (current):** reference-grounded, VLM-guided loop with LPIPS tracking.

## Phase II (Current)
- Goal: 3–5 iteration loop driven by vision model critique.
- Reference: a simplified single-pass version of a Shadertoy example.
- Renderer: offscreen moderngl with a fixed vertex shader and agent-edited fragment shaders.
- Evaluation: VLM provides qualitative critique; LPIPS tracks progress (lower is better).
- Observability: Weave traces for render/critique/edit steps and artifacts.
- UI: upload → run → iteration gallery → best LPIPS output + shader code.

## Phase I (Legacy)
- Goal: 3–5 iteration loop that visibly improves outputs and logs each step.
- Renderer: offscreen moderngl with a fixed vertex shader and agent-generated fragment shaders.
- Scoring: weighted FFT + edge + gram scores (removed in Phase II).
- Observability: Weave traces for shader generation calls and iteration metadata.
- UI: upload → run → iteration gallery → best output + shader code.

## How It Works
1. Upload image → stored in `assets/uploads/`.
2. For each iteration:
   - Agent generates a full GLSL fragment shader (JSON output).
   - Renderer compiles and renders offscreen.
   - LPIPS is computed against the input image.
3. Best LPIPS output is shown with its shader code.

## Quick Start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

### Environment
Create `.env` with:
```
OPENAI_API_KEY=...
WANDB_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
WEAVE_PROJECT=shader-agent
```

## Repo Layout
- `backend/`: FastAPI app, agent, renderer, metrics.
- `frontend/`: static UI.
- `assets/`: uploads and renders (ignored by git).

## Next Phase (Optional)
- Add shader corpus ingestion (Browserbase).
- Add retrieval and similarity search (Redis).
