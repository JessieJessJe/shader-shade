from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import weave
from openai import OpenAI

DEFAULT_PARAMS = {"frequency": 3.0, "blend": 0.3, "time_scale": 0.05}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _init_weave() -> None:
    if os.getenv("WEAVE_DISABLED") in {"1", "true", "TRUE"}:
        return
    if not os.getenv("WANDB_API_KEY"):
        print("[weave] WANDB_API_KEY not set; tracing disabled")
        return
    project = os.getenv("WEAVE_PROJECT", "shader-agent")
    try:
        weave.init(project)
    except Exception as exc:  # pragma: no cover - best-effort init
        print(f"[weave] init failed: {exc}")


_init_weave()


@weave.op()
def generate_params(
    *,
    iteration: int,
    total_iterations: int,
    weights: Dict[str, float],
    prev_scores: Optional[Dict[str, float]],
    prev_params: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"params": DEFAULT_PARAMS.copy(), "notes": "OPENAI_API_KEY not set"}

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    prompt = {
        "role": "user",
        "content": (
            "You are a shader tuning assistant. Return JSON only.\n"
            "Goal: noise-first tuning. Adjust noise params to better match texture stats.\n"
            f"Iteration {iteration + 1} of {total_iterations}.\n"
            f"Weights: {json.dumps(weights)}\n"
            f"Previous scores: {json.dumps(prev_scores or {})}\n"
            f"Previous params: {json.dumps(prev_params or DEFAULT_PARAMS)}\n\n"
            "Return JSON with keys: frequency, blend, time_scale, notes.\n"
            "Ranges: frequency 0.5-12.0, blend 0.1-0.95, time_scale 0.0-0.2.\n"
            "notes should be a short string explaining the change."
        ),
    }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return JSON only. Output must be valid JSON.",
            },
            prompt,
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"params": DEFAULT_PARAMS.copy(), "notes": "JSON parse failed"}

    freq = _safe_float(data.get("frequency"), DEFAULT_PARAMS["frequency"])
    blend = _safe_float(data.get("blend"), DEFAULT_PARAMS["blend"])
    time_scale = _safe_float(data.get("time_scale"), DEFAULT_PARAMS["time_scale"])

    params = {
        "frequency": _clamp(freq, 0.5, 12.0),
        "blend": _clamp(blend, 0.1, 0.95),
        "time_scale": _clamp(time_scale, 0.0, 0.2),
    }

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"params": params, "notes": notes}
