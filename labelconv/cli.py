from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Sequence, TextIO, Tuple

from .record import LabelRecordError, parse_row
from .zpl import DEFAULT_DPI, LabelConfig, build_zpl


def _read_rows(input_path: str) -> List[dict]:
    if input_path == "-":
        return list(csv.DictReader(sys.stdin))
    with Path(input_path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _convert_rows(rows: List[dict], config: LabelConfig, err: TextIO) -> Tuple[List[str], bool]:
    """Convert each row to ZPL, reporting bad rows to err instead of aborting.

    A single malformed row (bad weight, missing address) in a batch export
    shouldn't stop every other label in the file from converting.
    """
    labels = []
    had_error = False
    for line_number, row in enumerate(rows, start=2):  # header occupies line 1
        try:
            label = parse_row(row)
        except LabelRecordError as exc:
            print(f"line {line_number}: {exc}", file=err)
            had_error = True
            continue
        labels.append(build_zpl(label, config=config))
    return labels, had_error


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="labelconv",
        description="Convert a CSV of shipping label rows into ZPL.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="CSV file to read (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="file to write ZPL to (default: stdout)",
    )
    default_config = LabelConfig()
    parser.add_argument(
        "--width-in", type=float, default=default_config.width_in,
        help=f"label stock width in inches (default: {default_config.width_in})",
    )
    parser.add_argument(
        "--height-in", type=float, default=default_config.height_in,
        help=f"label stock height in inches (default: {default_config.height_in})",
    )
    parser.add_argument(
        "--dpi", type=int, default=DEFAULT_DPI,
        help=f"printer resolution in dots per inch (default: {DEFAULT_DPI})",
    )
    return parser


def main(argv: Sequence[str] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = LabelConfig(width_in=args.width_in, height_in=args.height_in, dpi=args.dpi)

    try:
        rows = _read_rows(args.input)
    except OSError as exc:
        print(f"labelconv: {exc}", file=sys.stderr)
        return 1

    labels, had_error = _convert_rows(rows, config, sys.stderr)

    if not labels:
        print("labelconv: no labels converted", file=sys.stderr)
        return 1

    # Each label is a complete ^XA...^XZ block, so concatenating them is
    # itself valid ZPL a printer can spool as one batch send.
    output_text = "\n".join(labels) + "\n"
    if args.output == "-":
        sys.stdout.write(output_text)
    else:
        Path(args.output).write_text(output_text, encoding="utf-8")

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
