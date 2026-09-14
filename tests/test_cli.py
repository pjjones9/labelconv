import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labelconv.cli import main

HEADER = (
    "recipient_name,address1,address2,city,state,postal_code,country,"
    "weight_oz,weight_unit,tracking_number,order_number,service_level"
)

GOOD_ROW = 'Jane Doe,123 Main St,,Springfield,IL,62704,US,16,,1Z999AA10123456784,,'
BAD_ROW = ',123 Main St,,Springfield,IL,62704,US,16,,1Z999AA10123456784,,'  # blank name


def run_cli(argv, stdin_text=""):
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin_text)):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class TestCliStdinStdout(unittest.TestCase):
    def test_converts_one_row_from_stdin_to_stdout(self):
        csv_text = "\n".join([HEADER, GOOD_ROW])
        exit_code, stdout, stderr = run_cli([], stdin_text=csv_text)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("^XA", stdout)
        self.assertIn("^XZ", stdout)
        self.assertIn("Jane Doe", stdout)

    def test_multiple_rows_produce_multiple_labels(self):
        csv_text = "\n".join([HEADER, GOOD_ROW, GOOD_ROW])
        _, stdout, _ = run_cli([], stdin_text=csv_text)
        self.assertEqual(stdout.count("^XA"), 2)
        self.assertEqual(stdout.count("^XZ"), 2)

    def test_bad_row_is_reported_but_good_rows_still_convert(self):
        csv_text = "\n".join([HEADER, BAD_ROW, GOOD_ROW])
        exit_code, stdout, stderr = run_cli([], stdin_text=csv_text)
        self.assertEqual(exit_code, 1)
        self.assertIn("line 2", stderr)
        self.assertEqual(stdout.count("^XA"), 1)
        self.assertIn("Jane Doe", stdout)

    def test_all_rows_bad_reports_no_labels_converted(self):
        csv_text = "\n".join([HEADER, BAD_ROW])
        exit_code, stdout, stderr = run_cli([], stdin_text=csv_text)
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("no labels converted", stderr)


class TestCliFiles(unittest.TestCase):
    def test_reads_input_file_and_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "orders.csv"
            out_path = Path(tmp) / "labels.zpl"
            in_path.write_text("\n".join([HEADER, GOOD_ROW]), encoding="utf-8")

            exit_code, stdout, stderr = run_cli([str(in_path), "-o", str(out_path)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "")
            output_text = out_path.read_text(encoding="utf-8")
            self.assertIn("^XA", output_text)
            self.assertIn("Jane Doe", output_text)

    def test_missing_input_file_reports_error(self):
        exit_code, stdout, stderr = run_cli(["/no/such/file.csv"])
        self.assertEqual(exit_code, 1)
        self.assertIn("labelconv:", stderr)


class TestCliStockOptions(unittest.TestCase):
    def test_width_height_dpi_flags_change_label_config(self):
        csv_text = "\n".join([HEADER, GOOD_ROW])
        exit_code, stdout, _ = run_cli(
            ["--width-in", "2.0", "--height-in", "1.0", "--dpi", "203"],
            stdin_text=csv_text,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("^PW406", stdout)
        self.assertIn("^LL203", stdout)


if __name__ == "__main__":
    unittest.main()
