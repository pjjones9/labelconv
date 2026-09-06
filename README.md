# labelconv

Converts shipping label data from a plain CSV export into ZPL, the command
language most Zebra thermal label printers speak.

The usual situation: your store platform (or your own order database) exports
orders as CSV, one row per shipment. To actually print a 4x6 label you need
ZPL, and generating ZPL by hand is where things get awkward. `^FD...^FS` is
how you write a field's text, but `^` and `~` are ZPL's own command prefixes,
so a recipient name like `A^B Corp` or an address with a tilde in it will
corrupt the label unless you switch that field into hex-escape mode with
`^FH` and hex-encode the offending bytes. And once you're in hex-escape mode,
a literal underscore in the data collides with the escape marker itself and
also needs encoding. Getting this wrong doesn't throw an error — it just
prints a broken or truncated label at 2am when you're not looking.

## Usage

```python
from labelconv import load_csv, build_zpl

labels = load_csv("orders.csv")
for label in labels:
    print(build_zpl(label))
```

Expected CSV columns:

```
recipient_name,address1,address2,city,state,postal_code,country,weight_oz,tracking_number,order_number,service_level
```

`address2`, `order_number`, and `service_level` are optional and may be left
blank. Everything else is required.

You can also build a label from data you already have in memory:

```python
from labelconv import ShippingLabel, build_zpl

label = ShippingLabel(
    recipient_name="Jane Doe",
    address1="123 Main St",
    city="Springfield",
    state="IL",
    postal_code="62704",
    country="US",
    weight_oz=16.0,
    tracking_number="1Z999AA10123456784",
)
print(build_zpl(label))
```

`build_zpl` defaults to a 4x6 label at 203 dpi. For other stock sizes or
printer resolutions, pass a `LabelConfig`:

```python
from labelconv import LabelConfig, build_zpl

config = LabelConfig(width_in=2.0, height_in=1.0, dpi=300)
print(build_zpl(label, config=config))
```

`width_in`/`height_in` become the label's `^PW`/`^LL` commands. `dpi` also
scales the field positions, which are tuned in dots at 203 dpi -- printing
those same dot values at a different resolution would move the text to the
wrong physical spot on the label.

Send the resulting string to a Zebra printer over raw TCP/9100, a USB queue,
or whatever transport you're already using — this project only produces the
ZPL text, it doesn't talk to printers.

You can go the other way too, recovering a `ShippingLabel` from ZPL that
`build_zpl` produced (useful for tests, or for re-reading a label you saved
to disk):

```python
from labelconv import parse_zpl

label = parse_zpl(zpl_text)
```

`parse_zpl` is a reverse of `build_zpl`'s specific layout, not a general ZPL
reader — it expects the field order and line formats `build_zpl` uses.
`service_level` isn't written to the label, so it always comes back empty.

## Status

Handles the CSV -> ZPL direction for a shipping label (name, address, weight,
Code 128 tracking barcode, order number), plus a ZPL -> CSV reverse parse for
labels this project generated. Defaults to 4x6 stock at 203 dpi but supports
other sizes and resolutions via `LabelConfig`. No dependencies beyond the
Python standard library.

## License

MIT, see LICENSE.
