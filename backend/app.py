from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

# Load .env file BEFORE importing modules that use environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from backend.agent import DEFAULT_FRAGMENT_SHADER, generate_shader
from backend.render import render_iteration
from backend.scoring import score_pair

ASSETS_DIR = BASE_DIR / "assets"
UPLOADS_DIR = ASSETS_DIR / "uploads"
RENDERS_DIR = ASSETS_DIR / "renders"
FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_IMAGE_PATH = UPLOADS_DIR / "test1.png"

for p in (UPLOADS_DIR, RENDERS_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shader Agent MVP")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class RunRequest(BaseModel):
    image_id: str | None = Field(None, description="Upload id returned by /api/upload")
    iterations: int = Field(5, ge=1, le=8)
    weights: dict = Field(
        default_factory=lambda: {"fft": 0.4, "edge": 0.3, "gram": 0.3}
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)) -> JSONResponse:
    contents = await file.read()
    app.state.latest_upload = contents
    app.state.latest_upload_mime = file.content_type or "image/png"

    return JSONResponse({"image_id": "latest"})


@app.post("/api/run")
async def run_loop(payload: RunRequest) -> JSONResponse:
    input_img = None
    input_image_ref = None

    if payload.image_id == "latest" and getattr(app.state, "latest_upload", None):
        try:
            input_img = Image.open(BytesIO(app.state.latest_upload))
            mime = getattr(app.state, "latest_upload_mime", "image/png")
            b64 = base64.b64encode(app.state.latest_upload).decode("ascii")
            input_image_ref = f"data:{mime};base64,{b64}"
        except Exception:
            input_img = None

    if input_img is None:
        if not DEFAULT_IMAGE_PATH.exists():
            return JSONResponse({"error": "default image not found"}, status_code=404)
        input_img = Image.open(DEFAULT_IMAGE_PATH)
        input_image_ref = "/assets/uploads/test1.png"

    iterations = []
    best = {"score": -1.0, "render_path": "", "shader_code": ""}
    prev_scores = None
    prev_shader = None
    last_good_shader = DEFAULT_FRAGMENT_SHADER

    for i in range(payload.iterations):
        agent_out = generate_shader(
            iteration=i,
            total_iterations=payload.iterations,
            weights=payload.weights,
            prev_scores=prev_scores,
            prev_shader=prev_shader,
        )
        fragment_shader = agent_out.get("fragment_shader", DEFAULT_FRAGMENT_SHADER)
        compile_error = ""
        try:
            render_path, shader_code, render_img, input_img = render_iteration(
                input_img=input_img,
                iteration=i,
                total_iterations=payload.iterations,
                fragment_shader=fragment_shader,
                output_dir=RENDERS_DIR,
            )
            last_good_shader = fragment_shader
        except Exception as exc:
            compile_error = str(exc)
            render_path, shader_code, render_img, input_img = render_iteration(
                input_img=input_img,
                iteration=i,
                total_iterations=payload.iterations,
                fragment_shader=last_good_shader,
                output_dir=RENDERS_DIR,
            )

        scores = score_pair(input_img, render_img, payload.weights)
        score = scores["composite"]

        iterations.append(
            {
                "iteration": i + 1,
                "score": score,
                "scores": scores,
                "render_path": f"/assets/renders/{render_path.name}",
                "shader_code": shader_code,
                "compile_error": compile_error,
                "agent_notes": agent_out.get("notes", ""),
            }
        )

        if score > best["score"]:
            best = {
                "score": score,
                "render_path": f"/assets/renders/{render_path.name}",
                "shader_code": shader_code,
            }
        prev_scores = scores
        prev_shader = fragment_shader

    return JSONResponse({"iterations": iterations, "best": best, "input_image": input_image_ref})
