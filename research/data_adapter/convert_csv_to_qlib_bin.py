import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert CSV data to Qlib bin format using Qlib dump_bin.py."
    )
    parser.add_argument("--data-path", default="research/data_adapter/raw/1d")
    parser.add_argument(
        "--qlib-dir", default="research/data_adapter/qlib_data")
    parser.add_argument("--freq", default="day")
    parser.add_argument("--date-field", default="date")
    parser.add_argument("--symbol-field", default="symbol")
    parser.add_argument("--exclude-fields", default="symbol")
    parser.add_argument("--file-suffix", default=".csv")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    dump_script = repo_root / "qlib" / "qlib-main" / "scripts" / "dump_bin.py"

    if not dump_script.exists():
        raise FileNotFoundError(f"dump_bin.py not found at {dump_script}")

    env = os.environ.copy()
    qlib_root = repo_root / "qlib" / "qlib-main"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(qlib_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    env.setdefault("SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYQLIB", "0.0.0")

    cmd = [
        sys.executable,
        str(dump_script),
        "dump_all",
        "--data_path",
        args.data_path,
        "--qlib_dir",
        args.qlib_dir,
        "--freq",
        args.freq,
        "--date_field_name",
        args.date_field,
        "--symbol_field_name",
        args.symbol_field,
        "--exclude_fields",
        args.exclude_fields,
        "--file_suffix",
        args.file_suffix,
    ]

    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    main()
