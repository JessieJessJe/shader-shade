from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

import weave
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
REFERENCE_SUMMARY_PATH = BASE_DIR / "notes" / "reference_particle_flow_summary.txt"

INTERFACE_CONTRACT = (
    "Shader interface contract (must follow exactly):\n"
    "- GLSL version: #version 330\n"
    "- Inputs: in vec2 v_uv;\n"
    "- Uniforms: sampler2D u_input, vec2 u_resolution, float u_time\n"
    "- Output: out vec4 f_color\n"
)

GLSL_COMPILE_RULES = (
    "GLSL compile rules (check these when fixing):\n"
    "- vec constructors must have EXACT component count: "
    "vec3(vec2,float) OK, vec3(vec2,vec2) WRONG (4 components)\n"
    "- Matrix multiply: matrix on LEFT only. mat2*vec2 OK, vec2*mat2 WRONG\n"
    "- Prefer dot-product hashes over matrix-based hashes to avoid mat errors\n"
    "- Cascading errors: fix the FIRST error only; later 'undeclared identifier' "
    "errors usually resolve once the root cause is fixed\n"
    "- Safe hash: fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453)\n"
)

DEFAULT_FRAGMENT_SHADER = """#version 330
uniform sampler2D u_input;
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
    vec3 target = texture(u_input, uv).rgb;
    vec3 color = mix(base, target, 0.2);
    f_color = vec4(color, 1.0);
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


def _load_reference_summary() -> str:
    if REFERENCE_SUMMARY_PATH.exists():
        return REFERENCE_SUMMARY_PATH.read_text(encoding="utf-8").strip()
    return ""


def _call_json_model(*, client: OpenAI, model: str, messages: list[dict]) -> Dict[str, object]:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


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

    prompt = (
        "You are a shader generation assistant. Return JSON only.\n"
        "Goal: produce a full GLSL fragment shader that runs with the provided vertex shader.\n"
        "Focus on procedural/noise-driven texture synthesis. No constraints beyond validity.\n"
        f"{INTERFACE_CONTRACT}\n"
        "Return JSON with keys: fragment_shader, notes.\n"
        f"Iteration {iteration + 1} of {total_iterations}.\n"
        f"Weights: {json.dumps(weights)}\n"
        f"Previous scores: {json.dumps(prev_scores or {})}\n"
        f"Previous shader: {json.dumps(prev_shader or '')}\n\n"
        "notes should be a short string explaining the change."
    )

    data = _call_json_model(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": "Return JSON only. Output must be valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    if not data:
        return {"fragment_shader": DEFAULT_FRAGMENT_SHADER, "notes": "JSON parse failed"}

    fragment_shader = data.get("fragment_shader")
    if not isinstance(fragment_shader, str) or "#version" not in fragment_shader:
        fragment_shader = DEFAULT_FRAGMENT_SHADER

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"fragment_shader": fragment_shader, "notes": notes}


@weave.op()
def run_discovery(*, reference_text: str | None) -> Dict[str, object]:
    """Phase A: read the full reference text, produce gap analysis + tailored prompts."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"gap_analysis": "", "initial_prompt": "", "edit_prompt": "", "notes": "OPENAI_API_KEY not set"}

    ref = reference_text or _load_reference_summary()
    if not ref:
        return {"gap_analysis": "", "initial_prompt": "", "edit_prompt": "", "notes": "No reference text provided"}

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    prompt = (
        "You are a shader analysis assistant. Return JSON only.\n\n"
        "I will give you a REFERENCE SHADER / TECHNIQUE description. "
        "Read it carefully and completely.\n\n"
        "Your job:\n"
        "1. UNDERSTAND what visual effect the reference produces.\n"
        "2. Classify the techniques into three buckets:\n"
        "   - SIMILAR: techniques we can reuse directly (e.g. particle rendering, noise, soft dots)\n"
        "   - DIFFERENT: things the reference does that we need to change (e.g. multipass, specific UV layout)\n"
        "   - BRIDGE NEEDED: adaptations required (e.g. flatten multipass into single-pass, add 3D surface)\n"
        "3. Based on your analysis, generate TWO tailored prompts:\n"
        "   a) initial_prompt: instructions for generating the FIRST shader. "
        "Be specific about which techniques to borrow, what to simplify, and what new techniques to add. "
        "Reference concrete functions/patterns from the reference text.\n"
        "   b) edit_prompt: instructions for EDITING a shader based on critique feedback. "
        "Describe the visual priorities and what aspects matter most for convergence.\n\n"
        f"{INTERFACE_CONTRACT}\n"
        "Return JSON with keys: gap_analysis (string with SIMILAR/DIFFERENT/BRIDGE NEEDED sections), "
        "initial_prompt (string), edit_prompt (string), notes (short summary string).\n\n"
        f"REFERENCE TEXT:\n{ref}\n"
    )

    data = _call_json_model(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": "Return JSON only. Output must be valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    return {
        "gap_analysis": data.get("gap_analysis", ""),
        "initial_prompt": data.get("initial_prompt", ""),
        "edit_prompt": data.get("edit_prompt", ""),
        "notes": data.get("notes", ""),
    }


@weave.op()
def generate_initial_shader(
    *,
    target_description: str | None,
    reference_text: str | None = None,
    discovery_context: str | None = None,
) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"fragment_shader": DEFAULT_FRAGMENT_SHADER, "notes": "OPENAI_API_KEY not set"}

    reference_summary = reference_text or _load_reference_summary()
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if discovery_context:
        prompt = (
            "You are a shader generation assistant. Return JSON only.\n"
            "Goal: generate an initial single-pass GLSL fragment shader that visually\n"
            "matches the target image as closely as possible.\n"
            "Do NOT map or sample the source image UVs as the primary structure.\n"
            "Use procedural structure; the source image is only a loose color/texture guide.\n"
            f"{INTERFACE_CONTRACT}\n"
            "Return JSON with keys: fragment_shader, notes.\n"
            f"Target description: {target_description or 'N/A'}\n\n"
            f"DISCOVERY-GUIDED INSTRUCTIONS (follow these closely):\n{discovery_context}\n\n"
            f"Reference summary:\n{reference_summary}\n"
            "notes should be a short string explaining the approach."
        )
    else:
        prompt = (
            "You are a shader generation assistant. Return JSON only.\n"
            "Goal: generate an initial single-pass GLSL fragment shader that visually\n"
            "matches the target image as closely as possible.\n"
            "Do NOT map or sample the source image UVs as the primary structure.\n"
            "Use procedural structure; the source image is only a loose color/texture guide.\n"
            "Simplify the multipass Shadertoy reference into a single-pass shader.\n"
            "Capture the core effect (soft particle flow + glow impression).\n"
            "Avoid Shadertoy buffers; do everything in one fragment shader.\n"
            f"{INTERFACE_CONTRACT}\n"
            "Return JSON with keys: fragment_shader, notes.\n"
            f"Target description: {target_description or 'N/A'}\n"
            f"Reference summary:\n{reference_summary}\n"
            "notes should be a short string explaining the approach."
        )

    data = _call_json_model(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": "Return JSON only. Output must be valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    fragment_shader = data.get("fragment_shader")
    if not isinstance(fragment_shader, str) or "#version" not in fragment_shader:
        fragment_shader = DEFAULT_FRAGMENT_SHADER

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"fragment_shader": fragment_shader, "notes": notes}


@weave.op()
def edit_shader(
    *,
    current_shader: str,
    critique_text: str,
    target_description: str | None,
    reference_text: str | None = None,
    discovery_context: str | None = None,
) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"fragment_shader": current_shader, "notes": "OPENAI_API_KEY not set"}

    reference_summary = reference_text or _load_reference_summary()
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if discovery_context:
        prompt = (
            "You are a shader editing assistant. Return JSON only.\n"
            "Goal: modify the shader to better match the target image.\n"
            "Do NOT map or sample the source image UVs as the primary structure.\n"
            "Use procedural structure; the source image is only a loose color/texture guide.\n"
            "Apply the critique, keep the interface contract unchanged.\n"
            f"{INTERFACE_CONTRACT}\n"
            f"Target description: {target_description or 'N/A'}\n"
            f"Critique:\n{critique_text}\n\n"
            f"DISCOVERY-GUIDED PRIORITIES (use these to decide what to fix first):\n{discovery_context}\n\n"
            f"Reference summary:\n{reference_summary}\n"
            "Return JSON with keys: fragment_shader, notes.\n"
            "notes should be a short string explaining the change."
        )
    else:
        prompt = (
            "You are a shader editing assistant. Return JSON only.\n"
            "Goal: modify the shader to better match the target image.\n"
            "Do NOT map or sample the source image UVs as the primary structure.\n"
            "Use procedural structure; the source image is only a loose color/texture guide.\n"
            "Apply the critique, keep the interface contract unchanged.\n"
            f"{INTERFACE_CONTRACT}\n"
            f"Target description: {target_description or 'N/A'}\n"
            f"Critique:\n{critique_text}\n"
            f"Reference summary:\n{reference_summary}\n"
            "Return JSON with keys: fragment_shader, notes.\n"
            "notes should be a short string explaining the change."
        )

    data = _call_json_model(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": "Return JSON only. Output must be valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    fragment_shader = data.get("fragment_shader")
    if not isinstance(fragment_shader, str) or "#version" not in fragment_shader:
        fragment_shader = current_shader

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"fragment_shader": fragment_shader, "notes": notes}


@weave.op()
def fix_compile_errors(*, shader: str, compile_error: str) -> Dict[str, object]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"fragment_shader": shader, "notes": "OPENAI_API_KEY not set"}

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    prompt = (
        "You are a shader repair assistant. Return JSON only.\n"
        "Fix compile errors without changing the visual intent.\n"
        f"{INTERFACE_CONTRACT}\n"
        f"{GLSL_COMPILE_RULES}\n"
        f"Compile error:\n{compile_error}\n"
        "Return JSON with keys: fragment_shader, notes.\n"
    )

    data = _call_json_model(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": "Return JSON only. Output must be valid JSON."},
            {"role": "user", "content": prompt},
            {"role": "user", "content": shader},
        ],
    )

    fragment_shader = data.get("fragment_shader")
    if not isinstance(fragment_shader, str) or "#version" not in fragment_shader:
        fragment_shader = shader

    notes = data.get("notes", "") if isinstance(data.get("notes"), str) else ""
    return {"fragment_shader": fragment_shader, "notes": notes}
