# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "shader-widget",
#     "weave",
#     "python-dotenv",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full", app_title="Shader Showcase")


@app.cell
def _():
    import marimo as mo
    import json
    import os
    from collections import defaultdict
    from datetime import datetime
    from pathlib import Path

    from shader_widget import ShaderWidget

    MARIMO_DIR = Path(__file__).parent
    DATA_PATH = MARIMO_DIR / "data" / "shader_traces.json"
    PROJECT_ROOT = MARIMO_DIR.parent
    return (
        DATA_PATH,
        PROJECT_ROOT,
        ShaderWidget,
        datetime,
        defaultdict,
        json,
        mo,
        os,
    )


@app.cell
def _(DATA_PATH, PROJECT_ROOT, os):
    # Load .env for WANDB_API_KEY
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    has_api_key = bool(os.getenv("WANDB_API_KEY"))
    has_cached_data = DATA_PATH.exists()
    return has_api_key, has_cached_data


@app.cell
def _(datetime, defaultdict, json, os):
    def fetch_and_cache(data_path) -> int:
        """Fetch shader traces from W&B Weave and save as local JSON.

        Returns the number of records saved.
        """
        import weave

        project = os.getenv("WEAVE_PROJECT", "shader-agent")
        client = weave.init(project)
        project_id = client._project_id()

        def _op_ref(name):
            return f"weave:///{project_id}/op/{name}:*"

        shader_calls = client.get_calls(
            filter={
                "op_names": [
                    _op_ref("generate_initial_shader"),
                    _op_ref("edit_shader"),
                ]
            },
            sort_by=[{"field": "started_at", "direction": "desc"}],
            limit=50,
        )

        shaders_raw = []
        trace_ids = set()
        for call in shader_calls:
            op_name = (
                call.op_name.split("/op/")[-1].split(":")[0]
                if "/op/" in call.op_name
                else call.op_name
            )
            output = call.output if isinstance(call.output, dict) else {}
            started = call.started_at
            if isinstance(started, datetime):
                started = started.isoformat()
            trace_ids.add(call.trace_id)
            shaders_raw.append({
                "id": call.id,
                "op": op_name,
                "trace_id": call.trace_id,
                "timestamp": started,
                "glsl": output.get("fragment_shader", ""),
                "notes": output.get("notes", ""),
                "critique": None,
            })

        if trace_ids:
            critique_calls = client.get_calls(
                filter={
                    "op_names": [_op_ref("critique_images")],
                    "trace_ids": list(trace_ids),
                },
                sort_by=[{"field": "started_at", "direction": "desc"}],
                limit=200,
            )
            critiques_by_trace = defaultdict(list)
            for call in critique_calls:
                text = call.output if isinstance(call.output, str) else ""
                if text:
                    critiques_by_trace[call.trace_id].append(text)
            for s in shaders_raw:
                crits = critiques_by_trace.get(s["trace_id"])
                if crits:
                    s["critique"] = crits[0]

        shaders_raw.sort(key=lambda s: s.get("timestamp", ""))

        data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(data_path, "w") as f:
            json.dump(shaders_raw, f, indent=2, default=str)

        return len(shaders_raw)
    return (fetch_and_cache,)


@app.cell
def _(DATA_PATH, has_api_key, has_cached_data, mo):
    fetch_button = mo.ui.run_button(label="Fetch from W&B")

    if has_api_key:
        status = "Ready to fetch" if not has_cached_data else f"Cached data found at `{DATA_PATH.name}`"
        _ui = mo.vstack([
            mo.md(f"**W&B connection:** {status}"),
            mo.hstack([
                fetch_button,
                mo.md("_Press to pull latest traces from Weave (overwrites cache)_"),
            ]),
        ])
    elif has_cached_data:
        _ui = mo.md(f"Using cached data from `{DATA_PATH.name}`. Set `WANDB_API_KEY` to refresh.")
    else:
        _ui = mo.callout(
            mo.md("No cached data and no `WANDB_API_KEY` found. Set the key in `.env` and press Fetch."),
            kind="warn",
        )

    _ui
    return (fetch_button,)


@app.cell
def _(DATA_PATH, fetch_and_cache, fetch_button, has_api_key, json, mo):
    # If the Refresh button was just pressed and we have an API key, fetch fresh data
    if fetch_button.value and has_api_key:
        _n = fetch_and_cache(DATA_PATH)
        mo.output.append(mo.md(f"Fetched **{_n}** records and saved to `{DATA_PATH.name}`"))

    mo.stop(not DATA_PATH.exists(), mo.md("No data available. Use the Fetch button above."))

    with open(DATA_PATH) as _f:
        _all_shaders = json.load(_f)

    shaders = [s for s in _all_shaders if s.get("glsl")]

    # Group into runs: split at each generate_initial_shader
    runs = []
    _current_run = []
    for _s in shaders:
        if _s["op"] == "generate_initial_shader":
            if _current_run:
                runs.append(_current_run)
            _current_run = [_s]
        else:
            _current_run.append(_s)
    if _current_run:
        runs.append(_current_run)
    return (runs,)


@app.cell
def _(mo):
    mo.md("""
    # Shader Showcase

    "
        f"**{len(shaders)}** generated shaders across **{len(runs)}** runs.

    "
        "Each run starts with an initial generation, then iteratively refines "
        "using VLM critique and perceptual scoring.
    """)
    return


@app.cell
def _(mo, runs):
    # Dropdown to select a run
    run_options = {
        f"Run {i+1} — {r[0].get('timestamp', '?')[:19]} — {len(r)} iterations": i
        for i, r in enumerate(runs)
    }
    run_picker = mo.ui.dropdown(
        options=run_options,
        value=list(run_options.keys())[0] if run_options else None,
        label="Select run",
    )
    run_picker
    return (run_picker,)


@app.cell
def _(ShaderWidget, mo, run_picker, runs):
    mo.stop(run_picker.value is None)

    selected_run = runs[run_picker.value]

    # Build a grid of shader cards
    cards = []
    for i, s in enumerate(selected_run):
        label = f"Iteration {i}"
        widget = mo.ui.anywidget(ShaderWidget(
            glsl=s["glsl"],
            width=200,
            height=200,
        ))

        card = mo.vstack([
            mo.md(f"<small>{label}</small>"),
            widget,
        ])
        cards.append(card)

    # Grid layout: 4 columns
    grid_rows = []
    for row_start in range(0, len(cards), 4):
        row = cards[row_start:row_start + 4]
        grid_rows.append(mo.hstack(row, gap=0.1, justify="start"))

    mo.vstack(grid_rows, gap=0)
    return s, selected_run


@app.cell
def _(mo, s, selected_run):
    # Detail view: expandable critique + GLSL for each iteration
    accordions = {}
    for _i, _s in enumerate(selected_run):
        _label = "Initial" if _s["op"] == "generate_initial_shader" else f"Edit {_i}"
        _critique = _s.get("critique") or "_No critique_"
        _notes = _s.get("notes") or "_No notes_"
        _glsl = s.get("glsl", "")

        detail = mo.md(
            f"### Critique\n{_critique}\n\n"
            f"### Agent Notes\n{_notes}\n\n"
            f"### GLSL\n```glsl\n{_glsl}\n```"
        )
        accordions[f"{_label} — {s.get('timestamp', '?')[:19]}"] = detail

    mo.accordion(accordions)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
