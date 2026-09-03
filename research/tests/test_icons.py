"""The icons are derived, and this is what keeps them derived.

`manifest.test.ts` checks that every icon the manifest names exists, is a PNG, and is the
size it claims. That is the shipping check. This is the different one: **the committed
bytes are still what the generator produces.**

Without it, `generate.py` becomes a comment. Someone opens a PNG in an editor, nudges it,
and the file on disk and the script that supposedly makes it quietly describe different
marks — the same failure as a parity oracle regenerated to make a test green
(`test_parity_fixture.py`), and the same fix: regenerating becomes a deliberate act with a
commit behind it rather than a side effect of running the script.

It also pins the colour to `ui/popup/popup.html`. The claim in the generator's docstring is
that the palette is not invented — that `#1f6feb` is the product's own `--accent`. A claim
about a value in another file is exactly the kind that stops being true silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from extension.icons.generate import ACCENT, MARK, SIZES, png

ICON_DIR = Path(__file__).resolve().parents[2] / "extension" / "icons"
POPUP = Path(__file__).resolve().parents[2] / "extension" / "ui" / "popup" / "popup.html"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _css_variable(name: str) -> str:
    """The first definition of a custom property in the popup's stylesheet — the light
    theme, which is the one an icon has to sit against on a store listing."""
    found = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{3,8}})", POPUP.read_text(encoding="utf-8"))
    assert found is not None, f"--{name} is not defined in popup.html any more"
    return found.group(1).lower()


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


class TestThePaletteIsTheProducts:
    def test_the_accent_is_the_popups_accent(self) -> None:
        assert _hex(ACCENT) == _css_variable("accent")

    def test_the_mark_is_the_popups_background(self) -> None:
        assert _hex(MARK) == _css_variable("bg")


class TestTheCommittedIconsAreStillGenerated:
    @pytest.mark.parametrize("size", SIZES)
    def test_regenerating_reproduces_the_committed_file(self, size: int) -> None:
        """If this fails, either the generator changed or a PNG was edited by hand.

        Decide which, then regenerate deliberately —
        `uv run python extension/icons/generate.py` — never as a reflex to go green.
        """
        path = ICON_DIR / f"icon{size}.png"
        assert path.exists(), "run uv run python extension/icons/generate.py"
        assert path.read_bytes() == png(size)

    @pytest.mark.parametrize("size", SIZES)
    def test_each_is_a_png_of_the_size_it_is_named_for(self, size: int) -> None:
        raw = (ICON_DIR / f"icon{size}.png").read_bytes()
        assert raw[:8] == PNG_MAGIC
        assert int.from_bytes(raw[16:20], "big") == size
        assert int.from_bytes(raw[20:24], "big") == size

    def test_no_committed_png_is_missing_from_the_generator(self) -> None:
        on_disk = sorted(int(p.stem.removeprefix("icon")) for p in ICON_DIR.glob("icon*.png"))
        assert on_disk == sorted(SIZES)


class TestTheMarkSurvivesTheSmallestSize:
    def test_sixteen_pixels_is_neither_blank_nor_solid(self) -> None:
        """A mark that vanishes or fills at 16px is not a mark, and 16px is the size the
        favicon and the tab strip use. Checked through the file's compressed size, which
        needs no decoder: a blank or solid tile compresses to almost nothing."""
        smallest = (ICON_DIR / "icon16.png").stat().st_size
        blank = len(png(1)) * 2
        assert smallest > blank

    def test_the_sizes_are_the_ones_chrome_and_the_store_ask_for(self) -> None:
        assert SIZES == (16, 32, 48, 128)
