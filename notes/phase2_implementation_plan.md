# Phase 2 Implementation Plan (Reference-Grounded, VLM-Guided)

## Goal
Make the example in `Phase 2 Plan New.docx` work end-to-end:
take a target image and a Shadertoy reference, generate a single‑pass
GLSL shader, iterate with VLM critique, track LPIPS in Weave, and
output the best shader.

## Scope (MVP)
- Single-pass fragment shader only (no multipass buffers).
- One fixed reference shader (Particle Flow) used as grounding.
- VLM critique drives edits; LPIPS only for tracking (not control).
- Compile error recovery + fix-it loop.

## Assumptions
- Existing render loop can compile arbitrary fragment shader strings.
- OpenAI API is used for shader generation and edits.
- VLM API available for image critique.
- Weave is optional but enabled when WANDB_API_KEY is set.

## Milestones & Tasks

### 1) Define Shader Interface Contract
**Objective:** Prevent incompatible GLSL from breaking renders.
- Inputs: `in vec2 v_uv;`
- Uniforms: `sampler2D u_input`, `vec2 u_resolution`, `float u_time`
- Output: `out vec4 f_color`
- GLSL version: `#version 330`

Deliverables:
- A single prompt block used across generation/edit steps that enforces
  the contract.
- Minimal validation: reject shaders missing `#version 330` or `f_color`.

### 2) Reference Simplification (Prompt-Only)
**Objective:** Convert multipass Shadertoy reference to single-pass.
- Include an instruction in the initial generation prompt:
  - "Simplify this multipass reference into a single-pass shader that
    captures the core effect (soft particle flow + glow impression)."
  - "Avoid Shadertoy buffers; do everything in one fragment shader."
- Provide the reference summary + key functions (from doc) as context.

Deliverables:
- Initial generation prompt that includes:
  - Interface contract
  - Reference summary + key techniques
  - Target image description (if available)

### 3) VLM Critique Step
**Objective:** Produce actionable, structured feedback.
- Use the structured critique prompt (Structure, Edges, Texture, Color).
- Require output sections:
  - WHAT'S WORKING
  - WHAT NEEDS TO CHANGE
  - SUGGESTED GLSL FIXES (2–3 items)

Deliverables:
- `critique_images(target, output) -> critique_text`
- Stored per-iteration critique in Weave.

### 4) Edit Step (LLM Shader Revision)
**Objective:** Apply critique to shader code.
- Input: current shader code + critique text + reference summary.
- Output: full shader code (valid JSON field).
- Include "do not change interface contract" instruction.

Deliverables:
- `edit_shader(shader, critique, reference) -> fragment_shader`

### 5) LPIPS Tracking
**Objective:** Track convergence with a numeric metric.
- LPIPS (torch + lpips) is logged only; does not gate iterations.

Deliverables:
- `compute_lpips(target, output) -> float`
- If LPIPS unavailable, return `None` and log fallback score.

### 6) Compile Error Recovery
**Objective:** Keep the loop running when shader fails.
- If compilation fails:
  1) Log error text.
  2) Send error + shader to LLM with "fix compile errors only".
  3) Retry render once.
  4) Fallback to last known good shader.

Deliverables:
- Error recovery wrapper in the render loop.

### 7) Weave Logging
**Objective:** Make demo traceable.
- Log per iteration:
  - shader code
  - rendered image
  - critique text
  - lpips score
  - compile status
  - delta lpips

Deliverables:
- Weave ops around render, critique, edit, and LPIPS.

## Module-by-Module Implementation Mapping

### `backend/app.py`
- Orchestrate the new loop:
  - call `generate_initial_shader(...)` (ref-simplification prompt)
  - call `render_iteration(...)`
  - call `critique_images(...)` (VLM)
  - call `edit_shader(...)`
  - call `compute_lpips(...)` (or fallback)
- Track and return per-iteration artifacts:
  - `compile_error`, `critique_text`, `lpips_score`, `render_path`
- Maintain `last_good_shader` and the compile-repair attempt.

### `backend/agent.py`
- Add two prompt functions:
  - `generate_initial_shader(...)` (includes ref simplification)
  - `edit_shader(...)` (applies critique to current shader)
- Keep `generate_shader` or replace with the two-phase interface.
- Enforce strict JSON response format for all LLM calls.

### `backend/render.py`
- No major changes expected:
  - Ensure it throws clear exceptions on compile errors.
  - Optionally add a small helper to validate required uniforms.

### `backend/metrics.py`
- Provide LPIPS helper.

### `frontend/app.js` + `frontend/index.html`
- Add fields for:
  - critique text per iteration
  - LPIPS score (or fallback metric)
  - compile status
- Optional: display the reference shader name/summary in UI.

### `notes/` and `assets/`
- Store the reference summary (from doc) in a text file so it can be
  injected into prompts without re-parsing `.docx`.
- Store one target image in `assets/uploads/` for the example run.

## Core Technical Challenges & Solutions

### Challenge 1: Shadertoy multipass reference vs single-pass renderer
**Risk:** Reference uses buffers; current pipeline cannot render them.
**Solution:** Prompt-level simplification to single-pass; include
explicit "no buffers" constraint and provide distilled techniques.

### Challenge 2: VLM critique too vague or inconsistent
**Risk:** Edits drift or oscillate.
**Solution:** Use structured critique prompt; require 2–3 concrete code
level suggestions and keep the critique short.

### Challenge 3: Shader compilation failures
**Risk:** Loop breaks early, no outputs.
**Solution:** Add compile-repair loop, and fallback to last known good
shader while logging the error.

### Challenge 4: LPIPS dependency weight
**Risk:** Torch install or runtime is slow/unreliable.
**Solution:** Make LPIPS optional; skip ranking if unavailable.

### Challenge 5: Overly broad prompts producing invalid GLSL
**Risk:** Missing interface or unsupported features.
**Solution:** Harden the interface contract and include a strict “return
JSON only” response format. Validate minimal fields before render.

## Acceptance Criteria (Example-First)
- One end-to-end run completes 4–5 iterations without crashing.
- At least one iteration produces a visible improvement.
- Weave shows critique + LPIPS trend (or fallback metric).

## Out of Scope (for this MVP)
- Retrieval across many Shadertoy shaders.
- Multipass buffer support.
- Automatic reference selection.
