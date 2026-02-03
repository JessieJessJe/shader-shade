# shader-widget

An anywidget for rendering GLSL fragment shaders in marimo notebooks.

## Install

```bash
pip install shader-widget
```

## Usage

```python
import marimo as mo
from shader_widget import ShaderWidget

widget = mo.ui.anywidget(ShaderWidget(
    glsl="""#version 330
uniform vec2 u_resolution;
uniform float u_time;
in vec2 v_uv;
out vec4 f_color;

void main() {
    vec3 color = 0.5 + 0.5 * cos(u_time + v_uv.xyx + vec3(0, 2, 4));
    f_color = vec4(color, 1.0);
}""",
    width=512,
    height=512,
))
widget
```

## GLSL Contract

The widget accepts shaders written for desktop OpenGL 3.3:

```glsl
#version 330
uniform sampler2D u_input;   // placeholder texture (1x1 black)
uniform vec2 u_resolution;   // canvas size in pixels
uniform float u_time;        // elapsed seconds
in vec2 v_uv;                // UV coordinates [0,1]
out vec4 f_color;            // output color
```

The `#version 330` header is automatically converted to WebGL2 (`#version 300 es`).
