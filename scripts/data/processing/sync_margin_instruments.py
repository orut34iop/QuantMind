#!/usr/bin/env python3
"""将融资融券 Excel 清单固化为 Qlib instruments 股票池文件。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_margin_symbols(excel_path: Path) -> set[str]:
    df = pd.read_excel(excel_path, dtype=str)
    code_col = next((col for col in df.columns if "股票代码" in str(col)), None)
    if code_col is None:
        raise ValueError(f"未找到股票代码列: {excel_path}")

    symbols: set[str] = set()
    for value in df[code_col].tolist():
        code = str(value or "").strip()
        if not code:
            continue
        if code.endswith(".0") and code[:-2].isdigit():
            code = code[:-2]
        if code.isdigit() and len(code) < 6:
            code = code.zfill(6)
        if len(code) != 6 or not code.isdigit():
            continue
        if code.startswith(("6", "9")):
            symbols.add(f"SH{code}")
        elif code.startswith(("0", "2", "3")):
            symbols.add(f"SZ{code}")
        elif code.startswith(("4", "8")):
            symbols.add(f"BJ{code}")
    return symbols


def _load_all_instruments(all_txt: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in all_txt.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split("\t")
        if len(parts) < 3:
            continue
        mapping[parts[0].strip().upper()] = text
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="同步融资融券股票池到 db/qlib_data/instruments")
    parser.add_argument(
        "--excel-path",
        default=str(PROJECT_ROOT / "data" / "融资融券.xlsx"),
    )
    parser.add_argument(
        "--all-instruments",
        default=str(PROJECT_ROOT / "db" / "qlib_data" / "instruments" / "all.txt"),
    )
    parser.add_argument(
        "--output-path",
        default=str(PROJECT_ROOT / "db" / "qlib_data" / "instruments" / "margin.txt"),
    )
    args = parser.parse_args()

    excel_path = Path(args.excel_path)
    all_txt = Path(args.all_instruments)
    output_path = Path(args.output_path)

    margin_symbols = _load_margin_symbols(excel_path)
    all_mapping = _load_all_instruments(all_txt)

    matched_lines = [all_mapping[symbol] for symbol in sorted(margin_symbols) if symbol in all_mapping]
    missing_symbols = sorted(symbol for symbol in margin_symbols if symbol not in all_mapping)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(matched_lines) + ("\n" if matched_lines else ""), encoding="utf-8")

    print(f"excel_symbols={len(margin_symbols)}")
    print(f"matched_instruments={len(matched_lines)}")
    print(f"missing_in_all={len(missing_symbols)}")
    print(f"output={output_path}")
    if missing_symbols:
        preview = ", ".join(missing_symbols[:20])
        print(f"missing_preview={preview}")


if __name__ == "__main__":
    main()
