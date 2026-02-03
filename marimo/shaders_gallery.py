# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "anywidget",
#     "traitlets",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full", app_title="Shader Gallery")


@app.cell
def _(mo):
    mo.md("""
    # Shader Gallery

    AI-generated GLSL fragment shaders, created by an agentic loop that generates, critiques, and refines shaders using VLM feedback.

    **How to use:** drag the slider to browse shaders. Each shader renders live via WebGL. The GLSL source and agent notes are shown alongside.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import json
    import urllib.request

    import anywidget
    import traitlets

    class ShaderWidget(anywidget.AnyWidget):
        glsl = traitlets.Unicode("").tag(sync=True)
        width = traitlets.Int(512).tag(sync=True)
        height = traitlets.Int(512).tag(sync=True)

        _esm = r"""
        const VERT = `#version 300 es
        in vec2 in_pos;
        out vec2 v_uv;
        void main() {
            v_uv = in_pos * 0.5 + 0.5;
            gl_Position = vec4(in_pos, 0.0, 1.0);
        }`;

        function adaptGLSL(src) {
            let s = src.replace(/^\s*#version\s+330\s*/m, "");
            return "#version 300 es\nprecision highp float;\n" + s;
        }

        function compile(gl, type, src) {
            const sh = gl.createShader(type);
            gl.shaderSource(sh, src);
            gl.compileShader(sh);
            if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
                const log = gl.getShaderInfoLog(sh);
                gl.deleteShader(sh);
                return { shader: null, error: log };
            }
            return { shader: sh, error: null };
        }

        function link(gl, vert, frag) {
            const prog = gl.createProgram();
            gl.attachShader(prog, vert);
            gl.attachShader(prog, frag);
            gl.linkProgram(prog);
            if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
                const log = gl.getProgramInfoLog(prog);
                gl.deleteProgram(prog);
                return { program: null, error: log };
            }
            return { program: prog, error: null };
        }

        function render({ model, el }) {
            const container = document.createElement("div");
            container.style.position = "relative";
            container.style.display = "inline-block";

            const canvas = document.createElement("canvas");
            const errorDiv = document.createElement("div");
            errorDiv.style.cssText =
                "color:#f44;font-family:monospace;font-size:12px;padding:8px;" +
                "max-height:80px;overflow:auto;display:none;background:#1a1a1a;" +
                "border-radius:0 0 8px 8px;";

            container.appendChild(canvas);
            container.appendChild(errorDiv);
            el.appendChild(container);

            const gl = canvas.getContext("webgl2");
            if (!gl) {
                errorDiv.textContent = "WebGL2 not supported";
                errorDiv.style.display = "block";
                return;
            }

            const vao = gl.createVertexArray();
            gl.bindVertexArray(vao);
            const buf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buf);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
                -1, -1,  1, -1,  -1, 1,
                -1,  1,  1, -1,   1, 1,
            ]), gl.STATIC_DRAW);
            gl.enableVertexAttribArray(0);
            gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

            const { shader: vertShader, error: vertErr } = compile(gl, gl.VERTEX_SHADER, VERT);
            if (vertErr) {
                errorDiv.textContent = "Vertex shader error: " + vertErr;
                errorDiv.style.display = "block";
                return;
            }

            const placeholderTex = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, placeholderTex);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
                          new Uint8Array([0, 0, 0, 255]));

            let program = null;
            let startTime = performance.now();
            let animId = null;

            function resize() {
                const w = model.get("width");
                const h = model.get("height");
                const dpr = window.devicePixelRatio || 1;
                canvas.width = w * dpr;
                canvas.height = h * dpr;
                canvas.style.width = w + "px";
                canvas.style.height = h + "px";
                canvas.style.borderRadius = "8px";
                canvas.style.display = "block";
            }

            function buildProgram() {
                const src = model.get("glsl");
                if (!src) return;
                const fragSrc = adaptGLSL(src);
                const { shader: fragShader, error: fragErr } = compile(gl, gl.FRAGMENT_SHADER, fragSrc);
                if (fragErr) {
                    errorDiv.textContent = fragErr;
                    errorDiv.style.display = "block";
                    return;
                }
                const { program: newProg, error: linkErr } = link(gl, vertShader, fragShader);
                gl.deleteShader(fragShader);
                if (linkErr) {
                    errorDiv.textContent = linkErr;
                    errorDiv.style.display = "block";
                    return;
                }
                if (program) gl.deleteProgram(program);
                program = newProg;
                errorDiv.style.display = "none";
                startTime = performance.now();
            }

            function draw(now) {
                animId = requestAnimationFrame(draw);
                if (!program) return;
                const elapsed = (now - startTime) / 1000.0;
                gl.viewport(0, 0, canvas.width, canvas.height);
                gl.clearColor(0, 0, 0, 1);
                gl.clear(gl.COLOR_BUFFER_BIT);
                gl.useProgram(program);
                const uRes = gl.getUniformLocation(program, "u_resolution");
                if (uRes) gl.uniform2f(uRes, canvas.width, canvas.height);
                const uTime = gl.getUniformLocation(program, "u_time");
                if (uTime) gl.uniform1f(uTime, elapsed);
                const uInput = gl.getUniformLocation(program, "u_input");
                if (uInput) {
                    gl.activeTexture(gl.TEXTURE0);
                    gl.bindTexture(gl.TEXTURE_2D, placeholderTex);
                    gl.uniform1i(uInput, 0);
                }
                gl.bindVertexArray(vao);
                gl.drawArrays(gl.TRIANGLES, 0, 6);
            }

            resize();
            buildProgram();
            animId = requestAnimationFrame(draw);

            model.on("change:glsl", buildProgram);
            model.on("change:width", () => { resize(); });
            model.on("change:height", () => { resize(); });

            return () => {
                if (animId) cancelAnimationFrame(animId);
                if (program) gl.deleteProgram(program);
                gl.deleteShader(vertShader);
                gl.deleteTexture(placeholderTex);
                gl.deleteBuffer(buf);
                gl.deleteVertexArray(vao);
            };
        }

        export default { render };
        """

    DATA_URL = "https://raw.githubusercontent.com/JessieJessJe/shader-shade/refs/heads/main/marimo/data/shader_traces.json"
    return DATA_URL, ShaderWidget, json, mo, urllib


@app.cell
def _(DATA_URL, json, mo, urllib):
    try:
        with urllib.request.urlopen(DATA_URL) as _resp:
            _all_shaders = json.loads(_resp.read().decode("utf-8"))
    except Exception as _e:
        mo.stop(True, mo.callout(mo.md(f"Failed to load data: {_e}"), kind="warn"))

    shaders = [s for s in _all_shaders if s.get("glsl")]
    return (shaders,)


@app.cell
def _(mo, shaders):
    slider = mo.ui.slider(
        start=0,
        stop=max(len(shaders) - 1, 0),
        value=42,
        show_value=True,
        full_width=True,
        label=f"Shader (1 to {len(shaders)})",
    )

    slider
    return (slider,)


@app.cell
def _(ShaderWidget, mo, shaders, slider):
    _s = shaders[slider.value]

    _widget = mo.ui.anywidget(ShaderWidget(
        glsl=_s["glsl"],
        width=512,
        height=512,
    ))

    _notes = _s.get("notes") or "_No notes_"
    _glsl = _s.get("glsl", "")

    # Scrollable right panel
    _right_content = mo.vstack([
        mo.md(f"**Shader {slider.value}** · `{_s['op']}`"),
        mo.md(f"### Notes\n{_notes}"),
        mo.md(f"### GLSL\n```glsl\n{_glsl}\n```"),
    ])

    _scrollable_right = mo.Html(f"""
    <div style="max-height: 520px; overflow-y: auto; padding-right: 8px;">
        {_right_content.text}
    </div>
    """)

    mo.hstack(
        [_widget, _scrollable_right],
        widths=[0, 1],
        gap=1,
        align="start",
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
