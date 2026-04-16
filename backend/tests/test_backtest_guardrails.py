import os
import sys
import types

import pytest

project_root = os.path.join(os.path.dirname(__file__), "../../")
sys.path.append(project_root)

from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService
from backend.services.engine.qlib_app.services.risk_analyzer import RiskAnalyzer


def test_normalize_signal_config_rejects_module_path_only_dict():
    service = QlibBacktestService()
    signal = {"module_path": "backend.services.engine.qlib_app.utils.simple_signal"}
    assert service._normalize_signal_config(signal) == "$close"


def test_build_signal_data_rejects_module_path_only_signal_dict():
    service = QlibBacktestService()
    request = types.SimpleNamespace(
        strategy_params=types.SimpleNamespace(
            signal={"module_path": "backend.services.engine.qlib_app.utils.simple_signal"}
        ),
        universe="all",
        start_date="2025-01-01",
        end_date="2025-01-02",
    )
    signal_data, signal_meta = service._build_signal_data(request)
    assert signal_data == "$close"
    assert signal_meta.get("source") == "close_fallback"


def test_normalize_trades_for_display_backfills_factor_and_price(monkeypatch):
    monkeypatch.setattr(
        RiskAnalyzer,
        "_load_factor_map",
        classmethod(lambda cls, pairs: {("SZ002822", "2025-01-02"): 0.14105364680290222}),
    )
    trades = [
        {
            "date": "2025-01-02",
            "symbol": "SZ002822",
            "price": 0.5444670915603638,
            "quantity": 34738.55593997433,
            "totalAmount": 18914.00051764482,
            "adj_price": None,
            "adj_quantity": None,
            "factor": None,
        }
    ]
    normalized = RiskAnalyzer.normalize_trades_for_display(trades)
    row = normalized[0]
    assert row["factor"] == pytest.approx(0.14105364680290222)
    assert row["price"] == pytest.approx(3.86, rel=1e-3)
    assert row["quantity"] == pytest.approx(4900.0, rel=1e-6)


def test_recording_strategy_drops_pool_file_local_before_super(monkeypatch):
    qlib = pytest.importorskip("qlib")
    assert qlib is not None

    from backend.services.engine.qlib_app.utils import recording_strategy as rs

    captured = {}

    def fake_init_redis(self, kwargs):
        return None

    def fake_init_dynamic_risk(self, kwargs):
        return None

    def fake_super_init(self, *args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(rs.RedisRecordingStrategy, "init_redis", fake_init_redis)
    monkeypatch.setattr(rs.RedisRecordingStrategy, "init_dynamic_risk", fake_init_dynamic_risk)
    monkeypatch.setattr(rs.TopkDropoutStrategy, "__init__", fake_super_init)

    rs.RedisRecordingStrategy(
        signal="$close",
        topk=10,
        n_drop=2,
        pool_file_local="/tmp/custom_pool.txt",
        rebalance_days=1,
    )

    assert "pool_file_local" not in captured
