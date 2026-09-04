import dataclasses
import unittest

from labelconv.record import LabelRecordError, ShippingLabel, parse_row
from labelconv.zpl import ZplParseError, build_zpl, escape_field, parse_zpl, unescape_field

BASE_ROW = {
    "recipient_name": "Jane Doe",
    "address1": "123 Main St",
    "address2": "",
    "city": "Springfield",
    "state": "IL",
    "postal_code": "62704",
    "country": "US",
    "weight_oz": "16",
    "tracking_number": "1Z999AA10123456784",
    "order_number": "",
    "service_level": "",
}


def row_with(**overrides):
    row = dict(BASE_ROW)
    row.update(overrides)
    return row


# Each case: (description, escaped field data, whether ^FH is required).
# The awkward ones are the ZPL control characters themselves, and the
# underscore, which collides with the hex-escape marker used to write them.
ESCAPE_CASES = [
    ("plain ascii", "plain text", "plain text", False),
    ("caret is a ZPL format-command prefix", "A^B Corp", "A_5EB Corp", True),
    ("tilde is a ZPL control-command prefix", "Home~Away", "Home_7EAway", True),
    ("underscore collides with the hex escape marker", "first_last", "first_5Flast", True),
    ("accented text needs no escaping under ^CI28", "Ünïcödé Straße", "Ünïcödé Straße", False),
    ("empty string", "", "", False),
    ("run of escape markers", "___", "_5F_5F_5F", True),
    ("all three special chars together", "^~_", "_5E_7E_5F", True),
]


class TestEscapeField(unittest.TestCase):
    def test_table(self):
        for description, text, expected, expected_needs_hex in ESCAPE_CASES:
            with self.subTest(case=description):
                escaped, needs_hex = escape_field(text)
                self.assertEqual(escaped, expected)
                self.assertEqual(needs_hex, expected_needs_hex)


class TestUnescapeField(unittest.TestCase):
    def test_table_round_trips_escape_field(self):
        for description, text, escaped, needs_hex in ESCAPE_CASES:
            with self.subTest(case=description):
                self.assertEqual(unescape_field(escaped, needs_hex), text)

    def test_plain_text_with_needs_hex_false_is_unchanged(self):
        self.assertEqual(unescape_field("plain text", False), "plain text")

    def test_trailing_underscore_without_hex_digits_is_kept_literal(self):
        # Not a shape escape_field ever produces, but a parser reading
        # arbitrary ^FH data shouldn't choke on it either.
        self.assertEqual(unescape_field("trailing_", True), "trailing_")


# Each case: (description, row overrides, expected exception or None).
PARSE_CASES = [
    ("all fields present", {}, None),
    ("missing tracking number", {"tracking_number": ""}, LabelRecordError),
    ("whitespace-only field counts as missing", {"city": "   "}, LabelRecordError),
    ("non-numeric weight", {"weight_oz": "sixteen"}, LabelRecordError),
    ("weight with stray whitespace is still valid", {"weight_oz": " 16 "}, None),
    ("optional address2 left blank", {"address2": ""}, None),
]


class TestParseRow(unittest.TestCase):
    def test_table(self):
        for description, overrides, expected_exc in PARSE_CASES:
            with self.subTest(case=description):
                row = row_with(**overrides)
                if expected_exc is None:
                    label = parse_row(row)
                    self.assertIsInstance(label, ShippingLabel)
                else:
                    with self.assertRaises(expected_exc):
                        parse_row(row)


def make_label(**overrides):
    base = dict(
        recipient_name="Jane Doe",
        address1="123 Main St",
        city="Springfield",
        state="IL",
        postal_code="62704",
        country="US",
        weight_oz=16.0,
        tracking_number="1Z999AA10123456784",
    )
    base.update(overrides)
    return ShippingLabel(**base)


class TestBuildZpl(unittest.TestCase):
    def test_omits_blank_address2_line(self):
        zpl = build_zpl(make_label(address2=""))
        self.assertNotIn("^FD^FS", zpl)

    def test_includes_address2_when_present(self):
        zpl = build_zpl(make_label(address2="Apt 4B"))
        self.assertIn("Apt 4B", zpl)

    def test_escapes_caret_in_recipient_name(self):
        zpl = build_zpl(make_label(recipient_name="A^B Corp"))
        self.assertIn("A_5EB Corp", zpl)
        self.assertNotIn("^FDA^B Corp^FS", zpl)

    def test_integer_weight_drops_trailing_zero(self):
        zpl = build_zpl(make_label(weight_oz=16.0))
        self.assertIn("16 oz", zpl)

    def test_fractional_weight_keeps_precision(self):
        zpl = build_zpl(make_label(weight_oz=16.25))
        self.assertIn("16.25 oz", zpl)

    def test_unicode_recipient_name_is_not_hex_escaped(self):
        zpl = build_zpl(make_label(recipient_name="Ünïcödé Straße"))
        self.assertIn("Ünïcödé Straße", zpl)

    def test_starts_and_ends_with_label_delimiters(self):
        zpl = build_zpl(make_label())
        self.assertTrue(zpl.startswith("^XA"))
        self.assertTrue(zpl.endswith("^XZ"))


class TestParseZpl(unittest.TestCase):
    def assert_round_trips(self, label):
        parsed = parse_zpl(build_zpl(label))
        for field in dataclasses.fields(ShippingLabel):
            if field.name == "service_level":
                continue  # never written to the label, so not recoverable
            self.assertEqual(
                getattr(parsed, field.name), getattr(label, field.name), field.name
            )

    def test_round_trips_minimal_label(self):
        self.assert_round_trips(make_label())

    def test_round_trips_with_address2_and_order_number(self):
        self.assert_round_trips(
            make_label(address2="Apt 4B", order_number="PO-4471")
        )

    def test_round_trips_with_address2_only(self):
        self.assert_round_trips(make_label(address2="Suite 200"))

    def test_round_trips_with_order_number_only(self):
        self.assert_round_trips(make_label(order_number="PO-4471"))

    def test_round_trips_escaped_fields(self):
        self.assert_round_trips(
            make_label(recipient_name="A^B Corp", address1="Home~Away, first_last")
        )

    def test_round_trips_fractional_weight(self):
        self.assert_round_trips(make_label(weight_oz=16.25))

    def test_raises_on_unrelated_zpl(self):
        with self.assertRaises(ZplParseError):
            parse_zpl("^XA^FO0,0^A0N,10,10^FDjust one field^FS^XZ")

    def test_raises_on_unparseable_weight_line(self):
        label = make_label()
        zpl = build_zpl(label).replace("16 oz", "sixteen ounces")
        with self.assertRaises(ZplParseError):
            parse_zpl(zpl)


if __name__ == "__main__":
    unittest.main()
