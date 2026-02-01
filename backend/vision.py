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
        "- IMAGE 2: CURRENT OUTPUT (shader render)\n"
        "Analyze these aspects and describe what needs to change:\n"
        "STRUCTURE: shape/form issues\n"
        "EDGES: silhouettes/edge brightness\n"
        "TEXTURE: grain/smoothness/density\n"
        "COLOR/CONTRAST: palette and contrast\n"
        "Provide your analysis as:\n"
        "WHAT'S WORKING:\n"
        "- ...\n"
        "WHAT NEEDS TO CHANGE:\n"
        "- ...\n"
        "SUGGESTED GLSL FIXES:\n"
        "- 2 to 3 concrete code-level suggestions\n"
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
