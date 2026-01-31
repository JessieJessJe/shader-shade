from __future__ import annotations

import json
import os
from typing import Dict, Optional

import weave
from openai import OpenAI

DEFAULT_FRAGMENT_SHADER = """#version 330
uniform vec2 u_resolution;
uniform float u_time;

in vec2 v_uv;
out vec4 f_color;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

void main() {
    vec2 uv = v_uv;
    float n = noise(uv * 4.0 + u_time * 0.05);
    vec3 base = vec3(n);
    f_color = vec4(base, 1.0);
}
"""

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
def generate_shader(
    *,
    iteration: int,
    total_iterations: int,
    weights: Dict[str, float],
    prev_scores: Optional[Dict[str, float]],
    prev_shader: Optional[str],
) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"fragment_shader": DEFAULT_FRAGMENT_SHADER, "notes": "OPENAI_API_KEY not set"}

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    prompt = {
        "role": "user",
        "content": (
            "You are a shader generation assistant. Return JSON only.\n"
            "Goal: produce a full GLSL fragment shader that runs with the provided vertex shader.\n"
            "Focus on procedural/noise-driven texture synthesis. No constraints beyond validity.\n"
            "Required interface:\n"
            "- Version: #version 330\n"
            "- Inputs: in vec2 v_uv;\n"
            "- Uniforms: vec2 u_resolution, float u_time\n"
            "- Output: out vec4 f_color\n"
            "Do NOT sample or reference the uploaded image (no u_input usage).\n"
            "Return JSON with keys: fragment_shader, notes.\n"
            f"Iteration {iteration + 1} of {total_iterations}.\n"
            f"Weights: {json.dumps(weights)}\n"
            f"Previous scores: {json.dumps(prev_scores or {})}\n"
            f"Previous shader: {json.dumps(prev_shader or '')}\n\n"
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
        return {"fragment_shader": DEFAULT_FRAGMENT_SHADER, "notes": "JSON parse failed"}

    fragment_shader = data.get("fragment_shader")
    if not isinstance(fragment_shader, str) or "#version" not in fragment_shader:
        fragment_shader = DEFAULT_FRAGMENT_SHADER

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"fragment_shader": fragment_shader, "notes": notes}
