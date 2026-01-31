# Shader Agent MVP

This repository is a Phase I implementation of a self-improving shader agent. The app uploads a texture image, iteratively generates GLSL fragment shaders, renders them offscreen, scores similarity (FFT/edge/gram), and surfaces the best iteration.

## Phase I Plan (Current)
- Goal: 3–5 iteration loop that visibly improves outputs and logs each step.
- Renderer: offscreen moderngl with a fixed vertex shader and agent-generated fragment shaders.
- Scoring: weighted FFT + edge + gram scores (fixed weights via UI).
- Observability: Weave traces for shader generation calls and iteration metadata.
- UI: upload → run → iteration gallery → best output + shader code.

## How It Works
1. Upload image → stored in `assets/uploads/`.
2. For each iteration:
   - Agent generates a full GLSL fragment shader (JSON output).
   - Renderer compiles and renders offscreen.
   - Scores are computed against the input image.
3. Best-scoring output is shown with its shader code.

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
- `backend/`: FastAPI app, agent, renderer, scoring.
- `frontend/`: static UI.
- `assets/`: uploads and renders (ignored by git).

## Next Phase (Optional)
- Add shader corpus ingestion (Browserbase).
- Add retrieval and similarity search (Redis).
