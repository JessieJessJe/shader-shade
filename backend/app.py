from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

# Load .env file BEFORE importing modules that use environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from backend.agent import (
    DEFAULT_FRAGMENT_SHADER,
    edit_shader,
    fix_compile_errors,
    generate_initial_shader,
    run_discovery,
)
from backend.metrics import compute_lpips_multi
from backend.render import render_iteration_frames
from backend.vision import critique_images
import weave

ASSETS_DIR = BASE_DIR / "assets"
UPLOADS_DIR = ASSETS_DIR / "uploads"
RENDERS_DIR = ASSETS_DIR / "renders"
FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_IMAGE_PATH = UPLOADS_DIR / "test1.png"

for p in (UPLOADS_DIR, RENDERS_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="La Shader is Shading")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/api/health")
def health() -> JSONResponse:
    try:
        import torch  # noqa: F401
        import lpips  # noqa: F401
        lpips_available = True
    except Exception as exc:
        lpips_available = False
        lpips_error = str(exc)
    else:
        lpips_error = ""

    return JSONResponse(
        {
            "status": "ok",
            "lpips_available": lpips_available,
            "lpips_error": lpips_error,
        }
    )


class RunRequest(BaseModel):
    image_id: str | None = Field(None, description="Upload id returned by /api/upload")
    iterations: int = Field(12, ge=1, le=20)
    num_frames: int = Field(1, ge=1, le=30, description="Frames to render per iteration")
    reference_text: str | None = Field(
        None, description="Optional reference text overriding the default summary"
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


def _sse(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/run")
async def run_loop(payload: RunRequest):
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

    ref_text = payload.reference_text
    num_iterations = payload.iterations
    num_frames = payload.num_frames

    def event_stream():
        nonlocal input_img

        # --- emit input image ---
        yield _sse("input_image", {"input_image": input_image_ref})

        # --- Phase A: Discovery ---
        discovery = run_discovery(reference_text=ref_text, target_img=input_img)
        discovery_initial = discovery.get("initial_prompt", "")
        discovery_edit = discovery.get("edit_prompt", "")

        yield _sse("discovery", {
            "gap_analysis": discovery.get("gap_analysis", ""),
            "notes": discovery.get("notes", ""),
        })

        # --- Phase B: Iteration loop ---
        best = {"score": None, "render_path": "", "shader_code": "", "metric": ""}
        prev_shader = None
        prev_critique = None
        last_good_shader = DEFAULT_FRAGMENT_SHADER

        for i in range(num_iterations):
            if i == 0:
                agent_out = generate_initial_shader(
                    target_description=None,
                    reference_text=ref_text,
                    discovery_context=discovery_initial,
                )
            else:
                agent_out = edit_shader(
                    current_shader=prev_shader or last_good_shader,
                    critique_text=prev_critique or "No critique available.",
                    target_description=None,
                    reference_text=ref_text,
                    discovery_context=discovery_edit,
                    iteration=i,
                    total_iterations=num_iterations,
                )
            fragment_shader = agent_out.get("fragment_shader", DEFAULT_FRAGMENT_SHADER)
            compile_error = ""
            try:
                render_paths, shader_code, render_imgs, input_img = render_iteration_frames(
                    input_img=input_img,
                    iteration=i,
                    total_iterations=num_iterations,
                    fragment_shader=fragment_shader,
                    output_dir=RENDERS_DIR,
                    num_frames=num_frames,
                )
                last_good_shader = fragment_shader
            except Exception as exc:
                compile_error = str(exc)
                repaired = fix_compile_errors(shader=fragment_shader, compile_error=compile_error)
                repaired_shader = repaired.get("fragment_shader", last_good_shader)
                try:
                    render_paths, shader_code, render_imgs, input_img = render_iteration_frames(
                        input_img=input_img,
                        iteration=i,
                        total_iterations=num_iterations,
                        fragment_shader=repaired_shader,
                        output_dir=RENDERS_DIR,
                        num_frames=num_frames,
                    )
                    last_good_shader = repaired_shader
                except Exception:
                    render_paths, shader_code, render_imgs, input_img = render_iteration_frames(
                        input_img=input_img,
                        iteration=i,
                        total_iterations=num_iterations,
                        fragment_shader=last_good_shader,
                        output_dir=RENDERS_DIR,
                        num_frames=num_frames,
                    )

            best_lpips, best_frame_idx, all_lpips = compute_lpips_multi(input_img, render_imgs)
            best_render_img = render_imgs[best_frame_idx]
            critique_text = critique_images(target_img=input_img, output_img=best_render_img)

            try:
                weave.log(
                    {
                        "iteration": i + 1,
                        "lpips_score": best_lpips,
                        "lpips_scores": all_lpips,
                        "best_frame_index": best_frame_idx,
                        "num_frames": num_frames,
                        "compile_error": compile_error,
                        "render_paths": [str(p) for p in render_paths],
                    }
                )
            except Exception:
                pass

            iter_data = {
                "iteration": i + 1,
                "lpips_score": best_lpips,
                "lpips_scores": all_lpips,
                "best_frame_index": best_frame_idx,
                "render_paths": [f"/assets/renders/{p.name}" for p in render_paths],
                "render_path": f"/assets/renders/{render_paths[best_frame_idx].name}",
                "shader_code": shader_code,
                "compile_error": compile_error,
                "critique": critique_text,
                "agent_notes": agent_out.get("notes", ""),
            }
            yield _sse("iteration", iter_data)

            rank_value = best_lpips
            rank_metric = "lpips"
            rank_is_lower = True

            if rank_value is None:
                should_replace = False
            elif best["score"] is None:
                should_replace = True
            elif rank_is_lower and rank_value < best["score"]:
                should_replace = True
            elif not rank_is_lower and rank_value > best["score"]:
                should_replace = True
            else:
                should_replace = False

            if should_replace:
                best = {
                    "score": rank_value,
                    "render_path": f"/assets/renders/{render_paths[best_frame_idx].name}",
                    "shader_code": shader_code,
                    "metric": rank_metric,
                }
            prev_shader = fragment_shader
            prev_critique = critique_text

        yield _sse("best", best)
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
