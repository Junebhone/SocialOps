"""Preparing an uploaded image for the vision model.

One job, called once per asset by the media node. It is a separate module from
the agent because the agent must stay cheap (`BaseAgent.images` runs inside the
window `llm.complete` times) and because this is the part with edge cases worth
testing on their own.

Three things happen here, and each one is a bug that reached a model before it
was fixed somewhere:

* **Downscale to 1024px.** A 4000px phone photo is tiled into hundreds of image
  tokens by a vision model. On qwen3.5:9b that is the difference between a
  ~4s call and one that exhausts the context window and returns nothing. 1024
  is what step 6 specifies and it is comfortably enough to read a label.
* **Apply EXIF orientation.** Phones store a portrait photo as landscape plus a
  rotation flag. Strip the flag without applying it and the model describes a
  sideways bottle, then the brand check fails on "product visible".
* **Re-encode deliberately.** JPEG for photographs, PNG only when the image has
  real transparency, because re-encoding a photo as PNG multiplies the base64
  payload roughly tenfold for no gain in what the model can see.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from worker.llm import PromptImage

# Step 6's number. The long edge; the short edge follows from the aspect ratio.
MAX_EDGE = 1024

# JPEG quality. 85 is the usual point where artefacts stop being visible; the
# model is reading shapes and label text, not judging compression.
JPEG_QUALITY = 85

# A guard against decompression bombs — a 100 KB PNG can declare a 50000x50000
# canvas and allocate ten gigabytes on decode. Pillow's own default limit is
# larger than anything this product accepts, and the upload endpoint caps bytes
# on the wire, which is a different thing from pixels after decode.
MAX_PIXELS = 50_000_000


class ImageError(ValueError):
    """The bytes are not an image we can send to a model."""


def downscale(data: bytes, max_edge: int = MAX_EDGE) -> PromptImage:
    """Decode, orient, shrink, and re-encode one image.

    Raises `ImageError` for anything undecodable, which the media node lets
    propagate: a corrupt upload is a permanent failure, so it should reach
    `failed_jobs` rather than be retried three times against a vision model.
    """
    try:
        with Image.open(io.BytesIO(data)) as source:
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise ImageError(f"Image is {width}x{height}, over the {MAX_PIXELS} pixel limit")

            # Rotate to how a human would see it, then discard the EXIF block —
            # it can carry a location the brand never meant to publish.
            image = ImageOps.exif_transpose(source) or source

            # `thumbnail` preserves the aspect ratio and never enlarges, so a
            # 400px image passes through untouched instead of being blown up
            # into a blurry 1024px one.
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

            # A palette image ("P") can carry transparency without an alpha
            # band, so ask the source, not the mode.
            transparent = image.mode in ("RGBA", "LA") or "transparency" in image.info

            buffer = io.BytesIO()
            if transparent:
                image.convert("RGBA").save(buffer, format="PNG", optimize=True)
                return PromptImage(data=buffer.getvalue(), media_type="image/png")

            image.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return PromptImage(data=buffer.getvalue(), media_type="image/jpeg")
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError(f"Could not decode the uploaded image: {exc}") from exc
