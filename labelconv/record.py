from __future__ import annotations

import csv
import dataclasses
from pathlib import Path
from typing import Iterable, Iterator, List

# Columns a row must have non-blank values for. Everything else on
# ShippingLabel is optional and defaults to "".
REQUIRED_FIELDS = (
    "recipient_name",
    "address1",
    "city",
    "state",
    "postal_code",
    "country",
    "weight_oz",
    "tracking_number",
)


class LabelRecordError(ValueError):
    """A CSV row could not be turned into a ShippingLabel."""


# ShippingLabel.weight_oz is always ounces -- these let a CSV source that
# ships weights in pounds or kilograms (a lot of freight/scale exports do)
# say so via an optional weight_unit column instead of pre-converting.
OUNCES_PER_POUND = 16.0
OUNCES_PER_KILOGRAM = 35.27396195

_WEIGHT_UNITS_TO_OUNCES = {
    "oz": 1.0,
    "lb": OUNCES_PER_POUND,
    "kg": OUNCES_PER_KILOGRAM,
}


def convert_to_oz(value: float, unit: str) -> float:
    """Convert a weight of the given unit ("oz", "lb", or "kg") to ounces."""
    try:
        factor = _WEIGHT_UNITS_TO_OUNCES[unit.strip().lower()]
    except KeyError:
        raise LabelRecordError(f"unsupported weight_unit: {unit!r}") from None
    return value * factor


@dataclasses.dataclass
class ShippingLabel:
    recipient_name: str
    address1: str
    city: str
    state: str
    postal_code: str
    country: str
    weight_oz: float
    tracking_number: str
    address2: str = ""
    order_number: str = ""
    service_level: str = ""


def parse_row(row: dict) -> ShippingLabel:
    # A field present but containing only spaces is still "missing" for our
    # purposes -- CSV exports from spreadsheets do this constantly.
    missing = [f for f in REQUIRED_FIELDS if not (row.get(f) or "").strip()]
    if missing:
        raise LabelRecordError(f"missing required field(s): {', '.join(missing)}")

    raw_weight = row["weight_oz"].strip()
    try:
        weight_value = float(raw_weight)
    except ValueError as exc:
        raise LabelRecordError(f"weight_oz is not a number: {raw_weight!r}") from exc

    weight_unit = (row.get("weight_unit") or "oz").strip()
    weight_oz = convert_to_oz(weight_value, weight_unit)

    return ShippingLabel(
        recipient_name=row["recipient_name"].strip(),
        address1=row["address1"].strip(),
        address2=(row.get("address2") or "").strip(),
        city=row["city"].strip(),
        state=row["state"].strip(),
        postal_code=row["postal_code"].strip(),
        country=row["country"].strip(),
        weight_oz=weight_oz,
        tracking_number=row["tracking_number"].strip(),
        order_number=(row.get("order_number") or "").strip(),
        service_level=(row.get("service_level") or "").strip(),
    )


def parse_csv(rows: Iterable[dict]) -> Iterator[ShippingLabel]:
    for row in rows:
        yield parse_row(row)


def load_csv(path) -> List[ShippingLabel]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(parse_csv(reader))
