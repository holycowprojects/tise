"""Generate Tise's icons. Placeholders, produced by a script rather than drawn once.

**Why a generator and not four PNGs.** Four binaries nobody can regenerate are four
binaries nobody can change: the day the accent colour moves or a fifth size is needed,
the only options are to redraw by hand or to live with the drift. The same argument as
everywhere else here — the artefact is derived, and the thing under version control is
the derivation.

**No new dependency.** Neither toolchain has an image library and this is not a good
reason to add one, so the PNGs are written with `zlib` and `struct` from the standard
library. That is enough for flat shapes, which is all this mark is.

**The palette is not invented.** `#1f6feb` is `--accent` from `ui/popup/popup.html`, and
white is `--bg`. An icon in colours nothing else uses is a second brand.

**The mark.** Three ascending bars, the third at reduced opacity. It is a chart, which is
what Tise is, and the faded bar is the part Tise does not claim to know yet — which is
the honest description of where this project stands: it counts what you did and shows the
denominator, and the one target that earned adoption is not switched on. If that changes,
the icon can stop being a placeholder and the last bar can fill in.

**These are placeholders and should be replaced.** Tise is a showcase for Holy Cow
Studios, and what represents the company in the Chrome Web Store is a branding decision,
not a rendering one. Replacing them changes no code: the manifest names the files.

    uv run python extension/icons/generate.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: `--accent` and `--bg` from `ui/popup/popup.html`. Kept as one source of truth by
#: `manifest.test.ts`, which fails if the manifest and this directory disagree.
ACCENT = (0x1F, 0x6F, 0xEB)
MARK = (0xFF, 0xFF, 0xFF)

#: Manifest sizes. 16 is the page favicon, 32 Windows, 48 the extensions card, 128 the
#: install dialog and the store listing.
SIZES = (16, 32, 48, 128)

#: Sub-samples per axis. Antialiasing matters far more at 16px than at 128: the mark is
#: nine pixels wide there, and a hard edge on a diagonal-free shape still beats a blur.
SUPERSAMPLE = 6

#: Fractions of the icon's side. Held as ratios so every size is the same drawing.
CORNER_RADIUS = 0.22
PADDING = 0.21
BAR_GAP = 0.16
#: Heights of the three bars, and how solid each is. The third is the point of the mark.
BAR_HEIGHTS = (0.42, 0.70, 1.00)
BAR_ALPHAS = (1.0, 1.0, 0.42)


def _inside_rounded_square(x: float, y: float, side: float, radius: float) -> bool:
    """Is this point inside a square with rounded corners?"""
    left, top, right, bottom = radius, radius, side - radius, side - radius
    if left <= x <= right or top <= y <= bottom:
        # The cross through the middle covers everything but the four corner boxes.
        return 0.0 <= x <= side and 0.0 <= y <= side
    corner_x = left if x < left else right
    corner_y = top if y < top else bottom
    return (x - corner_x) ** 2 + (y - corner_y) ** 2 <= radius**2


def _bars(side: float) -> list[tuple[float, float, float, float, float]]:
    """`(x0, y0, x1, y1, alpha)` for each bar, in pixel coordinates."""
    padding = side * PADDING
    content = side - 2 * padding
    gap = content * BAR_GAP
    width = (content - 2 * gap) / 3
    baseline = padding + content

    out: list[tuple[float, float, float, float, float]] = []
    for index, (height, alpha) in enumerate(zip(BAR_HEIGHTS, BAR_ALPHAS, strict=True)):
        x0 = padding + index * (width + gap)
        out.append((x0, baseline - content * height, x0 + width, baseline, alpha))
    return out


def _pixels(size: int) -> bytearray:
    """RGBA rows, top to bottom. Coverage is sampled rather than computed analytically:
    the shapes are axis-aligned apart from four arcs, and sampling keeps one code path."""
    side = float(size)
    radius = side * CORNER_RADIUS
    bars = _bars(side)
    step = 1.0 / SUPERSAMPLE
    samples = SUPERSAMPLE * SUPERSAMPLE

    rows = bytearray()
    for row in range(size):
        rows.append(0)  # PNG filter byte: none
        for column in range(size):
            background = 0
            covered = [0] * len(bars)
            for sub_y in range(SUPERSAMPLE):
                y = row + (sub_y + 0.5) * step
                for sub_x in range(SUPERSAMPLE):
                    x = column + (sub_x + 0.5) * step
                    if not _inside_rounded_square(x, y, side, radius):
                        continue
                    background += 1
                    for index, (x0, y0, x1, y1, _) in enumerate(bars):
                        if x0 <= x <= x1 and y0 <= y <= y1:
                            covered[index] += 1

            alpha = background / samples
            if alpha == 0.0:
                rows.extend((0, 0, 0, 0))
                continue

            # Premultiplied accumulation, then unpremultiply once at the end. Compositing
            # each bar in place would round three times and shift the colour.
            red, green, blue = (channel * alpha for channel in ACCENT)
            for index, (*_, bar_alpha) in enumerate(bars):
                mark_alpha = (covered[index] / samples) * bar_alpha
                if mark_alpha <= 0.0:
                    continue
                red = MARK[0] * mark_alpha + red * (1 - mark_alpha)
                green = MARK[1] * mark_alpha + green * (1 - mark_alpha)
                blue = MARK[2] * mark_alpha + blue * (1 - mark_alpha)

            rows.extend(
                (
                    round(min(255.0, red / alpha)),
                    round(min(255.0, green / alpha)),
                    round(min(255.0, blue / alpha)),
                    round(alpha * 255),
                )
            )
    return rows


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def png(size: int) -> bytes:
    """A complete PNG. 8-bit RGBA, no interlacing, maximum compression — these are tiny
    and they ship, and a deterministic level keeps the bytes stable across runs."""
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(_pixels(size)), 9))
        + _chunk(b"IEND", b"")
    )


def main() -> None:
    here = Path(__file__).resolve().parent
    for size in SIZES:
        path = here / f"icon{size}.png"
        path.write_bytes(png(size))
        print(f"wrote {path.name}  ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
