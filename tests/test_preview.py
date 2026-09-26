import unittest

from labelconv.preview import render_preview
from labelconv.record import ShippingLabel
from labelconv.zpl import LabelConfig, build_zpl


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


class TestRenderPreview(unittest.TestCase):
    def test_recipient_name_appears_on_its_own_row(self):
        preview = render_preview(build_zpl(make_label()))
        lines = preview.split("\n")
        self.assertTrue(any("Jane Doe" in line for line in lines))

    def test_fields_land_on_different_rows_in_label_order(self):
        preview = render_preview(build_zpl(make_label(address2="Apt 4B")))
        lines = preview.split("\n")
        name_row = next(i for i, line in enumerate(lines) if "Jane Doe" in line)
        address1_row = next(i for i, line in enumerate(lines) if "123 Main St" in line)
        address2_row = next(i for i, line in enumerate(lines) if "Apt 4B" in line)
        city_row = next(i for i, line in enumerate(lines) if "Springfield" in line)
        self.assertLess(name_row, address1_row)
        self.assertLess(address1_row, address2_row)
        self.assertLess(address2_row, city_row)

    def test_barcode_field_is_wrapped_in_pipes(self):
        preview = render_preview(build_zpl(make_label()))
        self.assertIn("|1Z999AA10123456784|", preview)

    def test_hex_escaped_field_is_unescaped_for_display(self):
        preview = render_preview(build_zpl(make_label(recipient_name="A^B Corp")))
        self.assertIn("A^B Corp", preview)
        self.assertNotIn("_5E", preview)

    def test_blank_optional_fields_produce_no_stray_marks(self):
        preview = render_preview(build_zpl(make_label(address2="")))
        self.assertNotIn("^FD", preview)

    def test_grid_dimensions_follow_label_config(self):
        config = LabelConfig(width_in=2.0, height_in=1.0, dpi=203)
        preview = render_preview(build_zpl(make_label(), config=config), config=config)
        lines = preview.split("\n")
        self.assertEqual(len(lines), config.height_dots // 40)

    def test_field_past_right_edge_is_clipped_not_wrapped(self):
        config = LabelConfig(width_in=1.0, height_in=1.0, dpi=203)
        preview = render_preview(
            build_zpl(make_label(recipient_name="A" * 40), config=config), config=config
        )
        for line in preview.split("\n"):
            self.assertLessEqual(len(line), config.width_dots // 20)

    def test_unrelated_zpl_renders_blank_grid(self):
        preview = render_preview("^XA^XZ")
        self.assertEqual(preview.strip("\n "), "")


if __name__ == "__main__":
    unittest.main()
