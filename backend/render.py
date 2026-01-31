from __future__ import annotations

from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

OUTPUT_SIZE = (256, 256)


VERTEX_SHADER = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330
uniform sampler2D u_input;
uniform float u_time;
uniform float u_freq;
uniform float u_blend;

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
    float n = noise(uv * u_freq + u_time * 0.05);
    vec3 base = vec3(n);
    vec3 target = texture(u_input, uv).rgb;
    vec3 color = mix(base, target, u_blend);
    f_color = vec4(color, 1.0);
}
"""


def render_iteration(
    *,
    image_path: Path,
    iteration: int,
    total_iterations: int,
    params: dict,
    output_dir: Path,
) -> tuple[Path, str, Image.Image, Image.Image]:
    input_img = Image.open(image_path).convert("RGB").resize(OUTPUT_SIZE)
    input_arr = np.asarray(input_img, dtype=np.uint8)

    ctx = moderngl.create_standalone_context()
    fbo = ctx.simple_framebuffer(OUTPUT_SIZE)
    fbo.use()

    program = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)

    vertices = np.array(
        [
            -1.0,
            -1.0,
            3.0,
            -1.0,
            -1.0,
            3.0,
        ],
        dtype="f4",
    )
    vbo = ctx.buffer(vertices.tobytes())
    vao = ctx.simple_vertex_array(program, vbo, "in_pos")

    texture = ctx.texture(OUTPUT_SIZE, 3, input_arr.tobytes())
    texture.use(location=0)
    program["u_input"] = 0

    freq = float(params.get("frequency", 3.0))
    blend = float(params.get("blend", 0.3))
    time_scale = float(params.get("time_scale", 0.05))

    program["u_time"] = float(iteration) * time_scale
    program["u_freq"] = freq
    program["u_blend"] = blend

    fbo.clear(0.0, 0.0, 0.0, 1.0)
    vao.render(mode=moderngl.TRIANGLES)

    data = fbo.read(components=3)
    render_img = Image.frombytes("RGB", OUTPUT_SIZE, data).transpose(Image.FLIP_TOP_BOTTOM)

    render_path = output_dir / f"iter_{iteration + 1:02d}.png"
    render_img.save(render_path)

    shader_code = (
        "// GLSL fragment shader (template)\n"
        f"// Params: frequency={freq:.3f}, blend={blend:.3f}, time_scale={time_scale:.3f}\n"
        + FRAGMENT_SHADER
    )

    return render_path, shader_code, render_img, input_img
