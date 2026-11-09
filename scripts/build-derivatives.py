#!/usr/bin/env python3
"""Generate responsive WebP derivatives for the photo archive.

Reads  photos/cat-NNN.jpg   (originals, source of truth - never modified)
Writes photos/400/cat-NNN.webp   grid thumbnail, 1x
       photos/800/cat-NNN.webp   grid thumbnail, 2x / hero
       index.html                intrinsic sizes, inlined between the
                                 PHOTO_DIMS markers so reserving space costs
                                 no extra request before first paint

Re-runnable: skips derivatives newer than their source. After adding or
removing photos, just run this again - index.html needs no edits.

    python3 scripts/build-derivatives.py          # incremental
    python3 scripts/build-derivatives.py --force  # rebuild everything
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"
WIDTHS = (400, 800)
QUALITY = 78
FORCE = "--force" in sys.argv


def resize(image, width):
    if image.width <= width:
        return image
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.LANCZOS)


def build(source):
    targets = {w: PHOTOS / str(w) / f"{source.stem}.webp" for w in WIDTHS}
    fresh = all(
        t.exists() and t.stat().st_mtime >= source.stat().st_mtime
        for t in targets.values()
    )
    if fresh and not FORCE:
        with Image.open(targets[WIDTHS[0]]) as thumb:
            return source.name, thumb.size, 0
    with Image.open(source) as original:
        original = original.convert("RGB")
        size = None
        for width, target in targets.items():
            scaled = resize(original, width)
            scaled.save(target, "webp", quality=QUALITY, method=5)
            if width == WIDTHS[0]:
                size = scaled.size
    return source.name, size, 1


def main():
    for width in WIDTHS:
        (PHOTOS / str(width)).mkdir(parents=True, exist_ok=True)
    sources = sorted(PHOTOS.glob("cat-*.jpg"))
    if not sources:
        sys.exit(f"no photos found in {PHOTOS}")

    with ProcessPoolExecutor() as pool:
        results = list(pool.map(build, sources, chunksize=8))

    dims = [list(size) for _, size, _ in results]
    written = sum(count for _, _, count in results)

    index = ROOT / "index.html"
    html = index.read_text()
    start, end = "/*PHOTO_DIMS:start*/", "/*PHOTO_DIMS:end*/"
    before, _, rest = html.partition(start)
    _, _, after = rest.partition(end)
    if not rest or not after:
        sys.exit(f"PHOTO_DIMS markers not found in {index}")
    payload = "window.PHOTO_DIMS=" + json.dumps(dims, separators=(",", ":")) + ";"
    index.write_text(before + start + payload + end + after)

    print(f"{len(sources)} photos, {written} rebuilt, {len(dims)} dims inlined")


if __name__ == "__main__":
    main()
