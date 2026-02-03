# Phase 3 MVP: Shader Gallery in Marimo

## Overview

Three deliverables:
1. **`shader-widget`** — a publishable anywidget package for rendering GLSL fragment shaders in marimo
2. **`shader_showcase.py`** — marimo notebook with W&B fetch + local-cache browsing (dev tool)
3. **`shaders_gallery.py`** — self-contained marimo notebook for publishing on molab (no external deps beyond `anywidget`/`traitlets`)

---

## Deliverable 1: `shader-widget` package

### File structure

```
shader-widget/
├── pyproject.toml          # package metadata, deps: anywidget, traitlets
├── README.md               # usage docs with GLSL contract
├── src/
│   └── shader_widget/
│       ├── __init__.py     # re-export ShaderWidget
│       └── widget.py       # ShaderWidget class with _esm JS inline
```

### Widget design

```python
class ShaderWidget(anywidget.AnyWidget):
    glsl = traitlets.Unicode("").tag(sync=True)    # full fragment shader source
    width = traitlets.Int(512).tag(sync=True)
    height = traitlets.Int(512).tag(sync=True)
```

### JS (`_esm`) responsibilities

- Create `<canvas>` element, attach to `el`
- Init WebGL2 context
- **Vertex shader:** fullscreen quad, output `v_uv = in_pos * 0.5 + 0.5` (matches existing contract)
- **Fragment shader preprocessing:** take `model.get("glsl")`, replace `#version 330` with `#version 300 es\nprecision highp float;`
- **Uniform binding:** `u_resolution` (vec2), `u_time` (float)
- **`u_input` texture:** bind a 1x1 black pixel placeholder (so shaders referencing it don't crash)
- **Animation loop:** `requestAnimationFrame`, increment time
- **Reactivity:** `model.on("change:glsl", recompile)` — recompiles shader when Python changes the trait
- **Cleanup:** return function that calls `cancelAnimationFrame`, releases GL resources
- **Error handling:** catch compile errors, show in error div below canvas

### GLSL compatibility

The stored shaders use this exact contract (from `backend/agent.py:18-24`):
```glsl
#version 330
uniform sampler2D u_input;
uniform vec2 u_resolution;
uniform float u_time;
in vec2 v_uv;
out vec4 f_color;
```

The widget's WebGL2 environment uses GLSL ES 3.0. Translation needed:
- `#version 330` → `#version 300 es` + `precision highp float;`
- Everything else is identical — same uniform names, same in/out names

The widget's vertex shader outputs `v_uv` identically to `backend/render.py:12-20`.

### Install for local dev

```bash
pip install -e ./shader-widget
```

---

## Deliverable 2: `shader_showcase.py` (dev notebook)

### Location

`marimo/shader_showcase.py`

### Purpose

Development notebook with W&B fetch capability. Reads from local JSON cache by default; fetching is behind an optional "Refresh" button.

### Dependencies (marimo sandbox)

```python
# /// script
# dependencies = ["marimo", "shader-widget", "weave", "python-dotenv"]
# ///
```

### Cell architecture (9 cells)

1. **Imports + config** — `mo`, `json`, `Path`, `ShaderWidget`, `DATA_PATH`, `PROJECT_ROOT`
2. **Env loading** — loads `.env`, exports `has_api_key`, `has_cached_data`
3. **Fetch helper** — defines `fetch_and_cache(data_path) -> int` with all W&B logic (not called, just exported)
4. **Refresh button UI** — `mo.ui.run_button`, shows connection status
5. **Load data** — if button pressed and API key set, calls `fetch_and_cache`; always reads from JSON cache; exports `shaders`, `runs`
6. **Header** — title + shader/run counts
7. **Run picker** — `mo.ui.dropdown` to select a run
8. **Shader grid** — 4-column grid of 256px `ShaderWidget` cards with critique summary
9. **Detail accordion** — expandable critique, notes, and GLSL per iteration

### Reactive flow

Button press → Cell 5 re-runs → fetch → save JSON → reload → `shaders`/`runs` update → Cells 6-9 cascade. On normal startup, data loads from cache with no API call.

---

## Deliverable 3: `shaders_gallery.py` (publishable notebook)

### Location

`marimo/shaders_gallery.py`

### Purpose

Lightweight, self-contained notebook designed for publishing on molab. No W&B, no dotenv, no `shader-widget` package — the `ShaderWidget` class is defined inline.

### Dependencies (marimo sandbox)

```python
# /// script
# dependencies = ["marimo", "anywidget", "traitlets"]
# ///
```

### Cell architecture (6 cells)

1. **Imports + ShaderWidget** — `mo`, `json`, `Path`, `anywidget`, `traitlets`; defines `ShaderWidget` class inline with full WebGL2 `_esm`; sets `DATA_PATH`
2. **Header** — title, description, and "How to use" guide
3. **Load data** — reads `shader_traces.json`, filters to entries with GLSL, exports flat `shaders` list
4. **Slider** — `mo.ui.slider` from 0 to `len(shaders) - 1` (dynamic), full-width
5. **Shader display** — side-by-side layout: 512px live WebGL widget on left, scrollable panel with agent notes + GLSL source on right
6. *(empty utility cell)*

### Key design decisions

- **Flat list, no run grouping** — single slider over all shaders for simplicity
- **One shader at a time** — only one WebGL context active for performance
- **Inline widget** — no external `shader-widget` dependency; fully self-contained for molab
- **Scrollable right panel** — GLSL + notes in a `max-height: 520px` scrollable div to keep layout stable

### Reactive flow

Slider drag → display cell re-runs → new `ShaderWidget` rendered with selected shader's GLSL.

---

## Cached data shape (`marimo/data/shader_traces.json`)

```json
[
  {
    "id": "call_id",
    "op": "edit_shader",
    "trace_id": "...",
    "timestamp": "2025-...",
    "glsl": "#version 330\n...",
    "notes": "...",
    "critique": "SIMILARITY SCORE: 7\n..."
  }
]
```

---

## Implementation order

1. **shader-widget package** — scaffolding + widget class + JS
2. **shader_showcase.py** — notebook with integrated fetch + gallery
3. **shaders_gallery.py** — standalone gallery for molab publishing

---

## Verification

### shader-widget
1. `pip install -e ./shader-widget` — installs without error

### shader_showcase.py
1. `marimo edit marimo/shader_showcase.py` — opens without errors
2. Shaders load from local JSON on startup (no W&B API call)
3. Dropdown shows runs, selecting one renders shader cards with live WebGL
4. "Refresh" button fetches from W&B when pressed (if API key set)
5. Detail accordion shows critique, notes, and GLSL

### shaders_gallery.py
1. `marimo edit marimo/shaders_gallery.py` — opens without errors
2. Shaders load from local JSON on startup
3. Slider browses all shaders; live WebGL renders on left, notes + GLSL on right
4. No external package dependencies beyond `anywidget` and `traitlets`
