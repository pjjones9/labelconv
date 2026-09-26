from __future__ import annotations

import re

from .zpl import DEFAULT_CONFIG, LabelConfig, unescape_field

# Renders build_zpl's output as an ASCII grid so a test (or a human reading
# a failure) can see where a field actually landed on the label, instead of
# reverse-engineering ^FO x,y pairs by hand. This is a layout simulation,
# not a pixel-accurate renderer -- there's no real font metrics or barcode
# symbology, just one grid cell per field character.
_ROW_DOTS = 40
_COL_DOTS = 20

_PREVIEW_FIELD_RE = re.compile(
    r"\^FO(?P<x>\d+),(?P<y>\d+)\^"
    r"(?:A0N,\d+,\d+|(?P<barcode>BY2\^BCN,\d+,Y,N,N))"
    r"(?P<hexflag>\^FH)?\^FD(?P<data>.*?)\^FS"
)


def render_preview(
    zpl_text: str,
    config: LabelConfig = DEFAULT_CONFIG,
    row_dots: int = _ROW_DOTS,
    col_dots: int = _COL_DOTS,
) -> str:
    """Render ^XA...^XZ ZPL (as produced by build_zpl) into an ASCII grid.

    row_dots/col_dots set how many printer dots each preview cell covers --
    smaller values give a bigger, more precise grid at the cost of a wider
    string. Barcode fields are wrapped in "|...|" since there's no real
    Code 128 rendering here, just a marker that something was printed there.
    """
    cols = max(1, config.width_dots // col_dots)
    rows = max(1, config.height_dots // row_dots)
    grid = [[" "] * cols for _ in range(rows)]

    for match in _PREVIEW_FIELD_RE.finditer(zpl_text):
        text = unescape_field(match.group("data"), match.group("hexflag") is not None)
        if not text:
            continue
        if match.group("barcode") is not None:
            text = f"|{text}|"

        row = min(rows - 1, int(match.group("y")) // row_dots)
        col = min(cols - 1, int(match.group("x")) // col_dots)
        for offset, ch in enumerate(text):
            c = col + offset
            if c >= cols:
                break
            grid[row][c] = ch

    return "\n".join("".join(row).rstrip() for row in grid)
