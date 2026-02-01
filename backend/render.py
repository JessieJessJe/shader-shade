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


def render_iteration_frames(
    *,
    input_img: Image.Image,
    iteration: int,
    total_iterations: int,
    fragment_shader: str,
    output_dir: Path,
    num_frames: int = 1,
) -> tuple[list[Path], str, list[Image.Image], Image.Image]:
    input_img = input_img.convert("RGB").resize(OUTPUT_SIZE)
    input_arr = np.asarray(input_img, dtype=np.uint8)

    ctx = moderngl.create_standalone_context()
    fbo = ctx.simple_framebuffer(OUTPUT_SIZE)
    fbo.use()

    program = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=fragment_shader)

    vertices = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype="f4")
    vbo = ctx.buffer(vertices.tobytes())
    vao = ctx.simple_vertex_array(program, vbo, "in_pos")

    texture = ctx.texture(OUTPUT_SIZE, 3, input_arr.tobytes())
    texture.use(location=0)
    if "u_input" in program:
        program["u_input"] = 0
    if "u_resolution" in program:
        program["u_resolution"] = OUTPUT_SIZE

    render_paths = []
    render_imgs = []

    for f in range(num_frames):
        t = f / max(num_frames, 1)
        if "u_time" in program:
            program["u_time"] = float(t)

        fbo.clear(0.0, 0.0, 0.0, 1.0)
        vao.render(mode=moderngl.TRIANGLES)

        data = fbo.read(components=3)
        render_img = Image.frombytes("RGB", OUTPUT_SIZE, data)

        if num_frames == 1:
            render_path = output_dir / f"iter_{iteration + 1:02d}.png"
        else:
            render_path = output_dir / f"iter_{iteration + 1:02d}_f{f + 1:02d}.png"
        render_img.save(render_path)

        render_paths.append(render_path)
        render_imgs.append(render_img)

    vao.release()
    vbo.release()
    texture.release()
    fbo.release()
    ctx.release()

    return render_paths, fragment_shader, render_imgs, input_img


def render_iteration(
    *,
    input_img: Image.Image,
    iteration: int,
    total_iterations: int,
    fragment_shader: str,
    output_dir: Path,
) -> tuple[Path, str, Image.Image, Image.Image]:
    paths, code, imgs, inp = render_iteration_frames(
        input_img=input_img,
        iteration=iteration,
        total_iterations=total_iterations,
        fragment_shader=fragment_shader,
        output_dir=output_dir,
        num_frames=1,
    )
    return paths[0], code, imgs[0], inp
