# La Shader is Shading

This repository contains two phases of the shader agent:
- **Phase I (legacy):** noise-focused loop with hand-crafted scoring.
- **Phase II (current):** reference-grounded, VLM-guided loop with LPIPS tracking, discovery phase, and multi-frame rendering.

## Phase II (Current)

### Overview
An agentic system that takes a target image and a reference shader description, automatically discovers the gap between them, generates tailored prompts, and iteratively produces a shader that captures the target's visual qualities. Vision model guides iteration; LPIPS scores track progress.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 PHASE A: DISCOVERY                      │
│                                                         │
│  Reference text (from textarea)                         │
│         │                                               │
│         ▼                                               │
│  ┌─────────────┐                                        │
│  │ GAP ANALYSIS │  (LLM classifies techniques)          │
│  └──────┬──────┘                                        │
│         ▼                                               │
│  SIMILAR | DIFFERENT | BRIDGE NEEDED                    │
│         │                                               │
│         ▼                                               │
│  ┌──────────────────┐                                   │
│  │ GENERATE PROMPTS │  → initial_prompt, edit_prompt    │
│  └────────┬─────────┘                                   │
└───────────┼─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│              PHASE B: ITERATION LOOP                    │
│                                                         │
│  ┌──────────────┐                                       │
│  │ GENERATE/EDIT │  (LLM + discovery prompts + feedback)│
│  └──────┬───────┘                                       │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │ RENDER FRAMES │  → N frames at u_time 0..1           │
│  └──────┬───────┘                                       │
│    ┌────┴────┐                                          │
│    ▼         ▼                                          │
│ ┌──────┐ ┌─────────┐                                    │
│ │LPIPS │ │ VISION  │  (scores all frames; critiques     │
│ │MULTI │ │ CRITIQUE│   best frame only)                 │
│ └───┬──┘ └────┬────┘                                    │
│     ▼         ▼                                         │
│ ┌───────────────────┐                                   │
│ │   LOG TO WEAVE    │                                   │
│ └─────────┬─────────┘                                   │
│           ▼                                             │
│     ┌───────────┐     No                                │
│     │ Converged? ├──────→ feedback to GENERATE/EDIT     │
│     └─────┬─────┘                                       │
│       Yes │                                             │
│           ▼                                             │
│     ┌──────────┐                                        │
│     │  OUTPUT  │                                        │
│     └──────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

### Key Features

#### Discovery Phase
Before iterations begin, the LLM reads the full reference text and produces:
- **Gap analysis**: classifies reference techniques as SIMILAR (reuse), DIFFERENT (change), BRIDGE NEEDED (adapt)
- **Tailored prompts**: custom instructions for initial generation and subsequent edits, replacing generic static prompts

#### Multi-Frame Rendering
Shaders animate over time via `u_time`. Instead of scoring a single static frame:
- Renders **N frames** per iteration at evenly spaced `u_time` values (0/N, 1/N, ..., (N-1)/N)
- GL context is created once and reused across all frames within an iteration
- LPIPS scores every frame; reports the **best (minimum)** score
- VLM critique sees only the best frame
- Frontend displays all frames as a cycling animation

#### SSE Streaming
The `/api/run` endpoint streams Server-Sent Events instead of returning a single JSON blob:
- `input_image` → immediately
- `discovery` → after gap analysis completes
- `iteration` → one per iteration, as each finishes
- `best` → final best result
- `done` → signals completion

The UI updates progressively as events arrive.

### Backend Modules

| Module | Purpose |
|--------|---------|
| `backend/app.py` | FastAPI orchestrator, SSE streaming endpoint |
| `backend/agent.py` | LLM shader generation, editing, discovery, compile repair |
| `backend/render.py` | Offscreen ModernGL rendering (single + multi-frame) |
| `backend/metrics.py` | LPIPS perceptual similarity (singleton model, multi-frame scoring) |
| `backend/vision.py` | VLM-based image critique via GPT-4 Vision |

### Frontend

Vanilla JS + CSS. Dark theme with cyan accent.

| Section | Description |
|---------|-------------|
| Input | Image upload, iterations count, frames count |
| Reference Shader | Textarea for reference text (persisted in localStorage) |
| Discovery | Gap analysis output (SIMILAR/DIFFERENT/BRIDGE NEEDED) |
| Iterations | Grid of iteration cards with frame cycling animation |
| Agent Notes | Per-iteration LLM notes |
| Best Output | Single best frame across all iterations |

### Shader Interface Contract

All generated shaders must follow:
```glsl
#version 330
uniform sampler2D u_input;
uniform vec2 u_resolution;
uniform float u_time;
in vec2 v_uv;
out vec4 f_color;
```

### API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the frontend |
| `/api/health` | GET | Health check, reports LPIPS availability |
| `/api/upload` | POST | Upload target image (multipart) |
| `/api/run` | POST | Run the pipeline (SSE stream) |

#### `/api/run` payload
```json
{
  "image_id": "latest",
  "iterations": 5,
  "num_frames": 8,
  "reference_text": "..."
}
```

#### SSE events
- `event: input_image` — `{ "input_image": "<url>" }`
- `event: discovery` — `{ "gap_analysis": "...", "notes": "..." }`
- `event: iteration` — `{ "iteration": 1, "lpips_score": 0.12, "lpips_scores": [...], "best_frame_index": 3, "render_paths": [...], "render_path": "...", "shader_code": "...", "critique": "...", "agent_notes": "..." }`
- `event: best` — `{ "score": 0.12, "render_path": "...", "shader_code": "...", "metric": "lpips" }`
- `event: done` — `{}`

## Phase I (Legacy)
- Goal: 3–5 iteration loop that visibly improves outputs and logs each step.
- Renderer: offscreen moderngl with a fixed vertex shader and agent-generated fragment shaders.
- Scoring: weighted FFT + edge + gram scores (removed in Phase II).
- Observability: Weave traces for shader generation calls and iteration metadata.

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
```
backend/
  app.py          # FastAPI orchestrator + SSE streaming
  agent.py        # LLM: discovery, generation, editing, repair
  render.py       # Offscreen ModernGL rendering (multi-frame)
  metrics.py      # LPIPS scoring (singleton model, multi-frame)
  vision.py       # VLM critique via GPT-4 Vision
frontend/
  index.html      # UI markup
  app.js          # Interactive logic + SSE consumer + frame cycling
  styles.css      # Dark theme styling
  reference_particle_flow_summary.txt  # Default reference text
assets/
  uploads/        # User-uploaded images (gitignored)
  renders/        # Generated shader frames (gitignored)
notes/
  phase2_implementation_plan.md
  reference_particle_flow_summary.txt
```
