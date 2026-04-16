from pathlib import Path

from backend.services.engine.qlib_app.utils.simple_signal import SimpleSignal


def test_simple_signal_loads_first_column_from_qlib_instrument_file(tmp_path: Path):
    instrument_file = tmp_path / "margin.txt"
    instrument_file.write_text(
        "SH600000\t2005-01-01\t2099-12-31\nSZ000001\t2005-01-01\t2099-12-31\n",
        encoding="utf-8",
    )

    signal = SimpleSignal(universe=str(instrument_file))

    assert signal._load_instruments_from_file(instrument_file) == ["SH600000", "SZ000001"]
