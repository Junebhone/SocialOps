"""Draw the five sample product images.

Generated rather than downloaded so there is no licensing question and no
network dependency in a demo (`data/sample_images/` is committed). They are
deliberately simple: flat shapes, a product silhouette, a legible wordmark. That
is enough for the media agent to have something real to describe and to check
against `brand_rules_json` — a photo would prove nothing extra and would need a
provenance trail.

    docker compose exec api python /app/data/generate_images.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "sample_images"
SIZE = (1024, 1024)

# name, background, product body, accent, wordmark, whether a logo is drawn
SAMPLES = [
    ("ridgeline_bag_front", (231, 226, 216), (58, 46, 38), (176, 106, 58), "RIDGELINE", True),
    ("ridgeline_cup_table", (240, 236, 228), (92, 74, 60), (176, 106, 58), "RIDGELINE", True),
    # No wordmark: the media agent's brand_check should fail "logo visible".
    ("ridgeline_beans_flatlay", (222, 214, 200), (70, 52, 40), (140, 92, 52), "", False),
    ("fieldnote_serum_bottle", (236, 240, 238), (48, 72, 66), (150, 176, 166), "FIELDNOTE", True),
    ("fieldnote_refill_pouch", (244, 241, 235), (60, 84, 78), (150, 176, 166), "FIELDNOTE", True),
]


def _draw(name: str, bg: tuple[int, int, int], body: tuple[int, int, int],
          accent: tuple[int, int, int], wordmark: str, logo: bool) -> Path:
    image = Image.new("RGB", SIZE, bg)
    draw = ImageDraw.Draw(image)

    # A soft ground line, so the product reads as sitting on a surface.
    draw.rectangle([0, 720, SIZE[0], SIZE[1]], fill=tuple(max(0, c - 14) for c in bg))

    if "bag" in name or "pouch" in name:
        draw.rectangle([330, 250, 694, 760], fill=body)
        draw.rectangle([330, 250, 694, 320], fill=accent)          # the top seal
        draw.rectangle([392, 430, 632, 470], fill=bg)              # label band
    elif "cup" in name:
        draw.ellipse([330, 300, 694, 420], fill=accent)            # crema
        draw.polygon([(340, 360), (684, 360), (620, 760), (404, 760)], fill=body)
    elif "beans" in name:
        for row in range(5):
            for column in range(5):
                x, y = 300 + column * 90, 320 + row * 84
                draw.ellipse([x, y, x + 62, y + 46], fill=body if (row + column) % 2 else accent)
    else:  # bottle
        draw.rectangle([430, 300, 594, 760], fill=body)
        draw.rectangle([470, 235, 554, 300], fill=accent)          # dropper cap
        draw.rectangle([452, 470, 572, 560], fill=bg)              # ingredient panel

    if logo:
        draw.ellipse([60, 60, 140, 140], fill=accent)
        draw.text((160, 88), wordmark, fill=body)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    image.save(path, optimize=True)
    return path


def main() -> None:
    for sample in SAMPLES:
        path = _draw(*sample)
        print(f"{path.name:<32} {path.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
