"""Build the multi-resolution Windows icon from the high-resolution PNG asset."""

from __future__ import annotations

import os
import struct
from io import BytesIO

from PIL import Image


ICON_SIZES = (256, 128, 96, 64, 48, 40, 32, 24, 20, 16)


def write_ico_descending(frames_with_sizes, output_path: str) -> None:
    """Write PNG-compressed RGBA frames largest-first in a Windows ICO file."""
    header = struct.pack("<HHH", 0, 1, len(frames_with_sizes))
    entries = []
    blobs = []
    offset = 6 + len(frames_with_sizes) * 16

    for (width, height), image in frames_with_sizes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        blob = buffer.getvalue()
        blobs.append(blob)

        width_byte = 0 if width >= 256 else width
        height_byte = 0 if height >= 256 else height
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width_byte,
                height_byte,
                0,
                0,
                1,
                32,
                len(blob),
                offset,
            )
        )
        offset += len(blob)

    with open(output_path, "wb") as icon_file:
        icon_file.write(header)
        for entry in entries:
            icon_file.write(entry)
        for blob in blobs:
            icon_file.write(blob)


def generate_black_hole_icon(output_dir: str = "assets") -> None:
    """Create all Windows icon sizes from assets/black_hole_icon.png."""
    png_path = os.path.join(output_dir, "black_hole_icon.png")
    ico_path = os.path.join(output_dir, "black_hole_icon.ico")

    if not os.path.isfile(png_path):
        raise FileNotFoundError(f"High-resolution icon source not found: {png_path}")

    with Image.open(png_path) as source_image:
        source = source_image.convert("RGBA")
        if min(source.size) < 512:
            raise ValueError(
                f"Icon source must be at least 512 px per side; got {source.size}."
            )

        # Keep non-square artwork centered without cropping or distorting it.
        side = max(source.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.alpha_composite(
            source,
            ((side - source.width) // 2, (side - source.height) // 2),
        )
        base_icon = square.resize((256, 256), Image.Resampling.LANCZOS)

    frames = [
        ((size, size), base_icon.resize((size, size), Image.Resampling.LANCZOS))
        for size in ICON_SIZES
    ]
    write_ico_descending(frames, ico_path)
    print(f"Generated {ico_path} from {png_path} ({source.size[0]}x{source.size[1]} PNG).")


if __name__ == "__main__":
    generate_black_hole_icon()
