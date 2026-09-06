from __future__ import annotations

import dataclasses
import re
import string
from typing import Tuple

from .record import ShippingLabel

# dpi build_zpl's field positions (the 30, 40, 45... constants below) were
# measured against. Any other dpi scales those dot values so the label keeps
# the same physical layout instead of shrinking or spilling off the stock.
DEFAULT_DPI = 203


@dataclasses.dataclass(frozen=True)
class LabelConfig:
    """Physical label stock size and printer resolution.

    width_in/height_in become ZPL's ^PW (print width) and ^LL (label length)
    commands, in dots. dpi also scales build_zpl's field positions, which
    are all tuned in dots at DEFAULT_DPI -- printing those same dot values
    at a different resolution would move the text to the wrong physical
    spot on the label.
    """

    width_in: float = 4.0
    height_in: float = 6.0
    dpi: int = DEFAULT_DPI

    @property
    def width_dots(self) -> int:
        return round(self.width_in * self.dpi)

    @property
    def height_dots(self) -> int:
        return round(self.height_in * self.dpi)

    @property
    def scale(self) -> float:
        return self.dpi / DEFAULT_DPI


DEFAULT_CONFIG = LabelConfig()

# ^ starts a ZPL format command and ~ starts a ZPL control command, so
# either one appearing literally inside field data breaks the label. ZPL's
# fix is "field hex escape" mode (^FH), where those bytes get written as
# _XX. The escape marker defaults to "_", which means a literal underscore
# in the data has to be escaped too once ^FH is active, or it gets read as
# the start of another escape sequence instead of a real character.
HEX_ESCAPE_CHARS = ("^", "~", "_")

# Prefix build_zpl writes in front of the order number line. There's no
# other marker in the label distinguishing that field from address2, so
# parse_zpl leans on this literal string to tell them apart.
ORDER_PREFIX = "Order: "

_HEX_DIGITS = frozenset(string.hexdigits)

# Matches one ^FO...^FD...^FS field, text or barcode, and captures whether
# ^FH (hex-escape mode) was turned on and the raw (possibly escaped) field
# data. Field data never contains a literal "^FS" -- any caret would have
# forced ^FH and been hex-escaped -- so the non-greedy match is safe.
_FIELD_RE = re.compile(
    r"\^FO\d+,\d+\^(?:A0N,\d+,\d+|BY2\^BCN,\d+,Y,N,N)(\^FH)?\^FD(.*?)\^FS"
)


class ZplParseError(ValueError):
    """A ZPL document could not be parsed back into a ShippingLabel."""


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


def unescape_field(field_data: str, needs_hex: bool) -> str:
    """Inverse of escape_field: recover the original text from ^FD data.

    needs_hex mirrors escape_field's return value -- pass False for field
    data that was never hex-escaped and it's returned unchanged.
    """
    if not needs_hex:
        return field_data
    out = []
    i = 0
    n = len(field_data)
    while i < n:
        ch = field_data[i]
        if ch == "_" and i + 3 <= n and field_data[i + 1] in _HEX_DIGITS and field_data[i + 2] in _HEX_DIGITS:
            out.append(chr(int(field_data[i + 1 : i + 3], 16)))
            i += 3
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _text_field(x: int, y: int, height: int, width: int, text: str) -> str:
    escaped, needs_hex = escape_field(text)
    hex_flag = "^FH" if needs_hex else ""
    return f"^FO{x},{y}^A0N,{height},{width}{hex_flag}^FD{escaped}^FS"


def _barcode_field(x: int, y: int, height: int, text: str) -> str:
    escaped, needs_hex = escape_field(text)
    hex_flag = "^FH" if needs_hex else ""
    return f"^FO{x},{y}^BY2^BCN,{height},Y,N,N{hex_flag}^FD{escaped}^FS"


def build_zpl(label: ShippingLabel, config: LabelConfig = DEFAULT_CONFIG) -> str:
    s = config.scale

    def d(dots: float) -> int:
        return round(dots * s)

    x = d(30)
    lines = [
        "^XA",
        f"^PW{config.width_dots}",
        f"^LL{config.height_dots}",
        "^CI28",  # UTF-8 so accented names/addresses render instead of mojibake
    ]

    y = d(30)
    lines.append(_text_field(x, y, d(40), d(40), label.recipient_name))
    y += d(45)

    lines.append(_text_field(x, y, d(30), d(30), label.address1))
    y += d(35)

    if label.address2:
        lines.append(_text_field(x, y, d(30), d(30), label.address2))
        y += d(35)

    city_line = f"{label.city}, {label.state} {label.postal_code}"
    lines.append(_text_field(x, y, d(30), d(30), city_line))
    y += d(35)

    lines.append(_text_field(x, y, d(30), d(30), label.country))
    y += d(45)

    weight_line = f"{label.weight_oz:g} oz"
    lines.append(_text_field(x, y, d(25), d(25), weight_line))
    y += d(50)

    lines.append(_barcode_field(x, y, d(80), label.tracking_number))
    y += d(110)

    if label.order_number:
        lines.append(_text_field(x, y, d(20), d(20), f"Order: {label.order_number}"))
        y += d(30)

    lines.append("^XZ")
    return "\n".join(lines)


def parse_zpl(text: str) -> ShippingLabel:
    """Recover a ShippingLabel from ZPL produced by build_zpl.

    This is a reverse of build_zpl's fixed layout, not a general ZPL
    reader -- it assumes the field order and line formats build_zpl uses
    (city line as "City, ST ZIP", weight line as "N oz", and so on).
    service_level isn't written to the label, so it always comes back "".
    """
    matches = _FIELD_RE.findall(text)
    fields = [unescape_field(data, bool(hex_flag)) for hex_flag, data in matches]

    order_number = ""
    if fields and fields[-1].startswith(ORDER_PREFIX):
        order_number = fields.pop()[len(ORDER_PREFIX):]

    if len(fields) == 7:
        name, address1, address2, city_line, country, weight_line, tracking_number = fields
    elif len(fields) == 6:
        name, address1, city_line, country, weight_line, tracking_number = fields
        address2 = ""
    else:
        raise ZplParseError(f"expected 6 or 7 label fields, found {len(fields)}")

    try:
        city, rest = city_line.split(", ", 1)
        state, postal_code = rest.rsplit(" ", 1)
    except ValueError as exc:
        raise ZplParseError(f"could not parse city/state/postal line: {city_line!r}") from exc

    weight_str, sep, unit = weight_line.rpartition(" ")
    if not sep or unit != "oz":
        raise ZplParseError(f"could not parse weight line: {weight_line!r}")
    try:
        weight_oz = float(weight_str)
    except ValueError as exc:
        raise ZplParseError(f"weight is not a number: {weight_str!r}") from exc

    return ShippingLabel(
        recipient_name=name,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
        weight_oz=weight_oz,
        tracking_number=tracking_number,
        order_number=order_number,
    )
