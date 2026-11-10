
from PIL import Image
from pathlib import Path

source = Path("assets/icons/fileorganizer.png")
destination = Path("assets/icons/fileorganizer.ico")

image = Image.open(source).convert("RGBA")

image.save(
    destination,
    format="ICO",
    sizes=[
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    ],
)

print(f"Icono generado: {destination}")
