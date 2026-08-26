from __future__ import annotations

from typing import Tuple

from .record import ShippingLabel

# ^ starts a ZPL format command and ~ starts a ZPL control command, so
# either one appearing literally inside field data breaks the label. ZPL's
# fix is "field hex escape" mode (^FH), where those bytes get written as
# _XX. The escape marker defaults to "_", which means a literal underscore
# in the data has to be escaped too once ^FH is active, or it gets read as
# the start of another escape sequence instead of a real character.
HEX_ESCAPE_CHARS = ("^", "~", "_")


def escape_field(text: str) -> Tuple[str, bool]:
    """Return (field_data, needs_fh) for use inside an ^FD...^FS block."""
    if not any(ch in text for ch in HEX_ESCAPE_CHARS):
        return text, False
    out = []
    for ch in text:
        if ch in HEX_ESCAPE_CHARS:
            out.append("_%02X" % ord(ch))
        else:
            out.append(ch)
    return "".join(out), True


def _text_field(x: int, y: int, height: int, width: int, text: str) -> str:
    escaped, needs_hex = escape_field(text)
    hex_flag = "^FH" if needs_hex else ""
    return f"^FO{x},{y}^A0N,{height},{width}{hex_flag}^FD{escaped}^FS"


def _barcode_field(x: int, y: int, height: int, text: str) -> str:
    escaped, needs_hex = escape_field(text)
    hex_flag = "^FH" if needs_hex else ""
    return f"^FO{x},{y}^BY2^BCN,{height},Y,N,N{hex_flag}^FD{escaped}^FS"


def build_zpl(label: ShippingLabel) -> str:
    lines = [
        "^XA",
        "^CI28",  # UTF-8 so accented names/addresses render instead of mojibake
    ]

    y = 30
    lines.append(_text_field(30, y, 40, 40, label.recipient_name))
    y += 45

    lines.append(_text_field(30, y, 30, 30, label.address1))
    y += 35

    if label.address2:
        lines.append(_text_field(30, y, 30, 30, label.address2))
        y += 35

    city_line = f"{label.city}, {label.state} {label.postal_code}"
    lines.append(_text_field(30, y, 30, 30, city_line))
    y += 35

    lines.append(_text_field(30, y, 30, 30, label.country))
    y += 45

    weight_line = f"{label.weight_oz:g} oz"
    lines.append(_text_field(30, y, 25, 25, weight_line))
    y += 50

    lines.append(_barcode_field(30, y, 80, label.tracking_number))
    y += 110

    if label.order_number:
        lines.append(_text_field(30, y, 20, 20, f"Order: {label.order_number}"))
        y += 30

    lines.append("^XZ")
    return "\n".join(lines)
