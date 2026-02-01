from __future__ import annotations

from typing import Optional

from PIL import Image

try:
    import torch
    import torchvision.transforms as transforms
    import lpips
    _LPIPS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - optional dependency
    torch = None
    transforms = None
    lpips = None
    _LPIPS_IMPORT_ERROR = str(exc)

_lpips_model = None


def _get_lpips_model():
    global _lpips_model
    if _lpips_model is None:
        if lpips is None:
            return None
        _lpips_model = lpips.LPIPS(net="alex")
    return _lpips_model


def _load_image_tensor(img: Image.Image) -> "torch.Tensor":
    if torch is None or transforms is None:
        raise RuntimeError("LPIPS dependencies not available")

    transform = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    return transform(img.convert("RGB")).unsqueeze(0)


def compute_lpips(input_img: Image.Image, render_img: Image.Image) -> Optional[float]:
    if torch is None or lpips is None:
        if _LPIPS_IMPORT_ERROR:
            print(f"[lpips] unavailable: {_LPIPS_IMPORT_ERROR}")
        return None

    loss_fn = _get_lpips_model()
    if loss_fn is None:
        return None
    with torch.no_grad():
        input_tensor = _load_image_tensor(input_img)
        render_tensor = _load_image_tensor(render_img)
        score = loss_fn(input_tensor, render_tensor)
    return float(score.item())


def compute_lpips_multi(
    input_img: Image.Image,
    render_imgs: list[Image.Image],
) -> tuple[Optional[float], int, list[Optional[float]]]:
    """Score each render against the target, return (best_score, best_index, all_scores)."""
    if torch is None or lpips is None:
        if _LPIPS_IMPORT_ERROR:
            print(f"[lpips] unavailable: {_LPIPS_IMPORT_ERROR}")
        return None, 0, [None] * len(render_imgs)

    loss_fn = _get_lpips_model()
    if loss_fn is None:
        return None, 0, [None] * len(render_imgs)

    input_tensor = _load_image_tensor(input_img)
    scores: list[float] = []

    with torch.no_grad():
        for img in render_imgs:
            render_tensor = _load_image_tensor(img)
            score = float(loss_fn(input_tensor, render_tensor).item())
            scores.append(score)

    best_idx = min(range(len(scores)), key=lambda i: scores[i])
    return scores[best_idx], best_idx, scores


__all__ = ["compute_lpips", "compute_lpips_multi"]
