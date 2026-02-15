#!/usr/bin/env python3
"""Simple script to convert PNG to ICO while maintaining transparency."""

import sys
from pathlib import Path
from PIL import Image


def png_to_ico(png_path, ico_path=None, sizes=None):
    """
    Convert PNG to ICO format.

    Args:
        png_path: Path to input PNG file
        ico_path: Path to output ICO file (optional, defaults to same name with .ico extension)
        sizes: List of icon sizes to include (default: [16, 32, 48, 256])
    """
    if sizes is None:
        sizes = [16, 32, 48, 256]

    png_path = Path(png_path)

    if not png_path.exists():
        raise FileNotFoundError(f"PNG file not found: {png_path}")

    if ico_path is None:
        ico_path = png_path.with_suffix('.ico')
    else:
        ico_path = Path(ico_path)

    # Open the PNG image
    img = Image.open(png_path)

    # Convert to RGBA if not already (to ensure transparency support)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Create resized versions for different icon sizes
    icon_sizes = []
    for size in sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        icon_sizes.append(resized)

    # Save as ICO with multiple sizes
    icon_sizes[0].save(
        ico_path,
        format='ICO',
        sizes=[(size, size) for size in sizes],
        append_images=icon_sizes[1:]
    )

    print(f"✓ Converted: {png_path.name} → {ico_path.name}")
    print(f"  Icon sizes: {', '.join(f'{s}x{s}' for s in sizes)}")
    print(f"  Output: {ico_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python png_to_ico.py <input.png> [output.ico]")
        sys.exit(1)

    input_png = sys.argv[1]
    output_ico = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        png_to_ico(input_png, output_ico)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
