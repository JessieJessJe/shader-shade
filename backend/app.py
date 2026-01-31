from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load .env file BEFORE importing modules that use environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agent import generate_params
from backend.render import render_iteration
from backend.scoring import score_pair

ASSETS_DIR = BASE_DIR / "assets"
UPLOADS_DIR = ASSETS_DIR / "uploads"
RENDERS_DIR = ASSETS_DIR / "renders"
FRONTEND_DIR = BASE_DIR / "frontend"

for p in (UPLOADS_DIR, RENDERS_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shader Agent MVP")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class RunRequest(BaseModel):
    image_id: str = Field(..., description="Upload id returned by /api/upload")
    iterations: int = Field(4, ge=1, le=8)
    weights: dict = Field(
        default_factory=lambda: {"fft": 0.4, "edge": 0.3, "gram": 0.3}
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)) -> JSONResponse:
    upload_id = uuid.uuid4().hex
    suffix = Path(file.filename or "image").suffix or ".png"
    path = UPLOADS_DIR / f"{upload_id}{suffix}"

    contents = await file.read()
    path.write_bytes(contents)

    return JSONResponse({"image_id": upload_id, "path": f"/assets/uploads/{path.name}"})


@app.post("/api/run")
async def run_loop(payload: RunRequest) -> JSONResponse:
    # Load the uploaded image by id (match any suffix).
    candidates = list(UPLOADS_DIR.glob(f"{payload.image_id}.*"))
    if not candidates:
        return JSONResponse({"error": "image_id not found"}, status_code=404)

    image_path = candidates[0]

    iterations = []
    best = {"score": -1.0, "render_path": "", "shader_code": ""}
    prev_scores = None
    prev_params = None

    for i in range(payload.iterations):
        agent_out = generate_params(
            iteration=i,
            total_iterations=payload.iterations,
            weights=payload.weights,
            prev_scores=prev_scores,
            prev_params=prev_params,
        )
        params = agent_out["params"]
        render_path, shader_code, render_img, input_img = render_iteration(
            image_path=image_path,
            iteration=i,
            total_iterations=payload.iterations,
            params=params,
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
                "params": params,
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
        prev_params = params

    return JSONResponse({"iterations": iterations, "best": best})
