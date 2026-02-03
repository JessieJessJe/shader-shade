"""Fetch shader generation traces from W&B Weave and save locally as JSON.

Run once:
    python marimo/fetch_traces.py

Requires WANDB_API_KEY in environment or .env file.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import weave

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "shader_traces.json"
WEAVE_PROJECT = os.getenv("WEAVE_PROJECT", "shader-agent")
LIMIT = 30


def get_op_ref(client: weave.WeaveClient, op_name: str) -> str:
    """Build a Weave op ref URI with wildcard version."""
    project_id = client._project_id()
    return f"weave:///{project_id}/op/{op_name}:*"


def fetch_traces() -> list[dict]:
    print(f"Connecting to Weave project: {WEAVE_PROJECT}")
    client = weave.init(WEAVE_PROJECT)

    # --- Fetch shader generation calls ---
    print(f"Fetching last {LIMIT} shader calls...")
    shader_calls = client.get_calls(
        filter={
            "op_names": [
                get_op_ref(client, "generate_initial_shader"),
                get_op_ref(client, "edit_shader"),
            ]
        },
        sort_by=[{"field": "started_at", "direction": "desc"}],
        limit=LIMIT,
    )

    # Collect shader data and trace IDs
    shaders = []
    trace_ids = set()
    for call in shader_calls:
        op_name = call.op_name.split("/op/")[-1].split(":")[0] if "/op/" in call.op_name else call.op_name
        output = call.output if isinstance(call.output, dict) else {}
        glsl = output.get("fragment_shader", "")
        notes = output.get("notes", "")
        trace_id = call.trace_id
        trace_ids.add(trace_id)

        started = call.started_at
        if isinstance(started, datetime):
            started = started.isoformat()

        shaders.append({
            "id": call.id,
            "op": op_name,
            "trace_id": trace_id,
            "timestamp": started,
            "glsl": glsl,
            "notes": notes,
            "critique": None,
        })

    # --- Fetch critique calls to correlate by trace_id ---
    if trace_ids:
        print(f"Fetching critique calls for {len(trace_ids)} traces...")
        critique_calls = client.get_calls(
            filter={
                "op_names": [get_op_ref(client, "critique_images")],
                "trace_ids": list(trace_ids),
            },
            sort_by=[{"field": "started_at", "direction": "desc"}],
            limit=200,
        )

        # Group critiques by trace_id (take the latest per trace)
        critiques_by_trace: dict[str, list[str]] = defaultdict(list)
        for call in critique_calls:
            critique_text = call.output if isinstance(call.output, str) else ""
            if critique_text:
                critiques_by_trace[call.trace_id].append(critique_text)

        # Attach critique to each shader
        # Match by trace_id: each shader iteration gets the critique from
        # the same trace. Multiple critiques per trace are joined.
        for shader in shaders:
            tid = shader["trace_id"]
            if tid in critiques_by_trace:
                # Use the latest critique for this trace
                shader["critique"] = critiques_by_trace[tid][0]

    # Sort by timestamp ascending (oldest first for gallery browsing)
    shaders.sort(key=lambda s: s.get("timestamp", ""))

    return shaders


def main() -> None:
    shaders = fetch_traces()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(shaders, f, indent=2, default=str)

    print(f"\nSaved {len(shaders)} shader records to {OUTPUT_PATH}")

    # Summary
    with_critique = sum(1 for s in shaders if s["critique"])
    with_glsl = sum(1 for s in shaders if s["glsl"])
    print(f"  - With GLSL code: {with_glsl}")
    print(f"  - With critique:  {with_critique}")


if __name__ == "__main__":
    main()
