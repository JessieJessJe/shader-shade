from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Optional

import weave
from openai import OpenAI
from PIL import Image


def _image_to_data_url(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


@weave.op()
def critique_images(
    *,
    target_img: Image.Image,
    output_img: Image.Image,
    prompt_override: Optional[str] = None,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or os.getenv("VISION_DISABLED") in {"1", "true", "TRUE"}:
        return "VLM critique unavailable; using stub critique."

    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    prompt = prompt_override or (
        "Compare these two images:\n"
        "- IMAGE 1: TARGET (the goal)\n"
        "- IMAGE 2: CURRENT OUTPUT (shader render)\n\n"
        "PRIORITY RULE: Color and palette matching is ALWAYS the #1 priority. "
        "The output must match the target's colors, tones, and contrast before anything else. "
        "Always start your analysis with color, and always include color correction guidance "
        "even if other aspects also need work.\n\n"
        "Analyze in this fixed priority order:\n"
        "1. COLOR/CONTRAST: palette, hue, saturation, brightness, contrast. Must match the TARGET image.\n"
        "2. STRUCTURE: shape/form, composition, spatial layout\n"
        "3. TEXTURE: grain, smoothness, density, pattern detail\n"
        "4. EDGES: silhouettes, edge brightness, sharpness\n\n"
        "Provide your analysis as:\n"
        "SIMILARITY SCORE: <1-10, where 1 = completely different, 10 = nearly identical>\n"
        "COLOR DELTA: <brief description of the exact color/palette shift needed>\n"
        "WHAT'S WORKING:\n"
        "- ...\n"
        "WHAT NEEDS TO CHANGE (structure, texture, edges only — do NOT repeat color here, it is already covered in COLOR DELTA):\n"
        "- ...\n"
    )

    target_url = _image_to_data_url(target_img)
    output_url = _image_to_data_url(output_img)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": target_url}},
                    {"type": "image_url", "image_url": {"url": output_url}},
                ],
            }
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or "No critique returned."
