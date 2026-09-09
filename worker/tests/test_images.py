"""Preparing an image for the vision model.

Each of these is a real failure mode of sending an upload straight to a model:
a photo that blows the context window, a portrait picture the model describes
sideways, and a payload ten times larger than it needs to be.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from worker import images
from worker.images import MAX_EDGE, ImageError, downscale


def _png(width: int, height: int, mode: str = "RGB", color: object = (200, 120, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color).save(buffer, format="PNG")  # type: ignore[arg-type]
    return buffer.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_a_large_photo_is_shrunk_to_the_long_edge() -> None:
    """A 4000px phone photo is tiled into hundreds of image tokens. On
    qwen3.5:9b that is the difference between a ~4s call and one that exhausts
    the context window and returns nothing."""
    prepared = downscale(_png(4000, 3000))

    assert max(_open(prepared.data).size) == MAX_EDGE


def test_the_aspect_ratio_survives() -> None:
    """Squashing a product shot changes what the model reports seeing."""
    prepared = downscale(_png(4000, 2000))

    assert _open(prepared.data).size == (1024, 512)


def test_a_small_image_is_not_enlarged() -> None:
    """`thumbnail` only shrinks. Upscaling a 400px image to 1024 would hand the
    model a blurry picture and four times the tokens for no extra detail."""
    prepared = downscale(_png(400, 300))

    assert _open(prepared.data).size == (400, 300)


def test_a_photograph_comes_back_as_jpeg() -> None:
    """Re-encoding a photo as PNG multiplies the base64 payload roughly tenfold
    for nothing the model can see."""
    prepared = downscale(_png(1200, 900))

    assert prepared.media_type == "image/jpeg"
    assert _open(prepared.data).format == "JPEG"


def test_transparency_is_preserved_as_png() -> None:
    """A packshot on a transparent background flattened onto black stops looking
    like a product on a background at all."""
    prepared = downscale(_png(1200, 900, mode="RGBA", color=(200, 120, 60, 0)))

    assert prepared.media_type == "image/png"
    assert _open(prepared.data).mode == "RGBA"


def test_exif_rotation_is_applied_not_stripped() -> None:
    """Phones store a portrait photo as landscape plus a rotation flag. Drop the
    flag without applying it and the model describes a sideways bottle — and
    then the brand check fails on 'product visible'.
    """
    portrait = Image.new("RGB", (200, 100), (10, 20, 30))
    exif = portrait.getexif()
    exif[274] = 6  # Orientation: rotate 90° clockwise on display.
    buffer = io.BytesIO()
    portrait.save(buffer, format="JPEG", exif=exif)

    prepared = downscale(buffer.getvalue())

    # 200x100 displayed with orientation 6 is 100x200.
    assert _open(prepared.data).size == (100, 200)


def test_undecodable_bytes_raise_rather_than_reaching_a_model() -> None:
    """A corrupt upload is a permanent failure. Raising here sends it to
    `failed_jobs` instead of retrying it three times against a vision model."""
    with pytest.raises(ImageError):
        downscale(b"this is not an image")


def test_a_decompression_bomb_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The upload endpoint caps bytes on the wire, which is a different thing
    from pixels after decode: a small PNG can declare an enormous canvas.

    The limit is lowered rather than the image made huge — allocating a real
    50-megapixel bitmap to prove a comparison works would cost 150 MB in the
    test suite and prove nothing extra.
    """
    monkeypatch.setattr(images, "MAX_PIXELS", 1000)

    with pytest.raises(ImageError, match="pixel limit"):
        downscale(_png(100, 100))


def test_the_real_pixel_limit_is_above_any_plausible_upload() -> None:
    """The guard must not reject a normal camera. 50 MP is well past a phone."""
    assert images.MAX_PIXELS >= 50_000_000


def test_the_result_is_smaller_than_the_original() -> None:
    """The whole point. A 4000px source must not come back bigger than it went
    in, which is what happens if the re-encode picks PNG for a photograph."""
    original = _png(4000, 3000)

    assert len(downscale(original).data) < len(original)
