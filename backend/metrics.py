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

    loss_fn = lpips.LPIPS(net="alex")
    with torch.no_grad():
        input_tensor = _load_image_tensor(input_img)
        render_tensor = _load_image_tensor(render_img)
        score = loss_fn(input_tensor, render_tensor)
    return float(score.item())


__all__ = ["compute_lpips"]
