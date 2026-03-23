"""SVG to PNG conversion utilities using cairosvg and Pillow."""

import io
import os


def convert_svg_to_png(svg_path: str, tempdir: str) -> str:
    """Convert an SVG file to a PNG file (max side 1024px, aspect ratio preserved).

    Save the PNG in tempdir and return the PNG path.
    Raises RuntimeError if conversion fails or dependencies are missing.
    """
    try:
        import cairosvg
    except ImportError as err:
        raise RuntimeError(
            "cairosvg is required for SVG to PNG conversion. Please install it."
        ) from err
    try:
        from PIL import Image as PILImage
    except ImportError as err:
        raise RuntimeError(
            "Pillow is required for SVG to PNG conversion. Please install it."
        ) from err

    with open(svg_path, "rb") as f:
        svg_data = f.read()
    png_bytes = cairosvg.svg2png(
        bytestring=svg_data, output_width=1024, output_height=1024, scale=1.0
    )
    img = PILImage.open(io.BytesIO(png_bytes))
    w, h = img.size
    if w > h:
        new_w = 1024
        new_h = int(h * (1024 / w))
    else:
        new_h = 1024
        new_w = int(w * (1024 / h))
    img = img.resize((new_w, new_h), PILImage.LANCZOS)
    png_path = os.path.join(tempdir, "rendered.png")
    img.save(png_path)
    return png_path
