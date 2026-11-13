"""Image preparation: orientation, cropping, rotation and on-screen overlays."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:  # iPhone HEIC photos, if pillow-heif is installed
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

# Native panel resolution of the 13.3" Spectra 6 (landscape).
PANEL_SIZE = (1600, 1200)


def portrait_size(panel_size: tuple[int, int] = PANEL_SIZE) -> tuple[int, int]:
    w, h = panel_size
    return (min(w, h), max(w, h))


def open_image(path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respect phone camera rotation
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def prepare(img: Image.Image, size: tuple[int, int], fit: str = "fill",
            background: str = "#ffffff") -> Image.Image:
    """Return an RGB image of exactly `size` (portrait)."""
    if fit == "fit":
        contained = ImageOps.contain(img, size, Image.LANCZOS)
        canvas = Image.new("RGB", size, background)
        canvas.paste(contained, ((size[0] - contained.width) // 2,
                                 (size[1] - contained.height) // 2))
        return canvas
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))


def to_panel(img: Image.Image, rotation: int) -> Image.Image:
    """Rotate a portrait image into the panel's landscape orientation."""
    if img.width < img.height:
        return img.rotate(rotation, expand=True)
    return img


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def add_low_battery(img: Image.Image, percent: float) -> Image.Image:
    img = img.copy()
    draw = ImageDraw.Draw(img)
    text = f"Battery {percent:.0f}% - please charge"
    font = _font(28)
    pad = 12
    box = draw.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = img.width - w - 3 * pad, img.height - h - 3 * pad
    draw.rectangle((x - pad, y - pad, x + w + pad, y + h + pad), fill="white", outline="red", width=3)
    draw.text((x - box[0], y - box[1]), text, fill="red", font=font)
    return img


def welcome_screen(size: tuple[int, int], address: str) -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    lines = [
        ("InkFrame", 90, "black"),
        ("", 40, "black"),
        ("On your phone (same Wi-Fi), open:", 42, "black"),
        (address, 54, "blue"),
        ("", 40, "black"),
        ("Upload some pictures to get started.", 42, "black"),
    ]
    y = size[1] // 3
    for text, px, colour in lines:
        font = _font(px)
        box = draw.textbbox((0, 0), text or " ", font=font)
        draw.text(((size[0] - (box[2] - box[0])) // 2, y), text, fill=colour, font=font)
        y += (box[3] - box[1]) + 30
    return img
