#!/usr/bin/env python3
"""
Generate a mock screenshot PNG file for testing ScreenshotOne API.
This script creates a simple image that can be used in place of a real screenshot.
"""

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont

    # Create a mock screenshot image
    width, height = 800, 600
    image = Image.new("RGB", (width, height), color=(255, 255, 255))

    # Add some text to the image
    draw = ImageDraw.Draw(image)

    # Draw a header bar
    draw.rectangle([(0, 0), (width, 60)], fill=(53, 106, 195))

    # Draw website content placeholder
    draw.rectangle([(50, 100), (width-50, 300)], outline=(200, 200, 200))
    draw.rectangle([(50, 320), (width-50, 500)], outline=(200, 200, 200))

    # Add text
    try:
        font = ImageFont.truetype("Arial", 24)
    except OSError:
        font = ImageFont.load_default()

    draw.text((20, 15), "Mock Website - ScreenshotOne API Test", fill=(255, 255, 255), font=font)
    draw.text((width // 2 - 180, height // 2), "This is a mock screenshot for testing", fill=(0, 0, 0), font=font)

    # Save the image
    output_path = Path(__file__).parent / "mock_screenshot.png"
    image.save(output_path)


except ImportError:
    # If PIL is not available, create a 1x1 transparent PNG
    with open(Path(__file__).parent / "mock_screenshot.png", "wb") as f:
        # Minimal valid PNG file (1x1 transparent pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\r"      # IHDR chunk length
            b"IHDR"                # IHDR chunk type
            b"\x00\x00\x00\x01"    # Width: 1
            b"\x00\x00\x00\x01"    # Height: 1
            b"\x08"                # Bit depth: 8
            b"\x06"                # Color type: RGBA
            b"\x00\x00\x00"        # Compression, filter, interlace
            b"\x1f\x15\xc4\x89"    # CRC
            b"\x00\x00\x00\x0a"    # IDAT chunk length
            b"IDAT"                # IDAT chunk type
            b"\x78\x9c\x63\x00\x01\x00\x00\x05\x00\x01"  # Compressed data
            b"\x0d\x0a\x2d\xb4"    # CRC
            b"\x00\x00\x00\x00"    # IEND chunk length
            b"IEND"                # IEND chunk type
            b"\xae\x42\x60\x82"    # CRC
        )
        f.write(png_data)


if __name__ == "__main__":
    pass
