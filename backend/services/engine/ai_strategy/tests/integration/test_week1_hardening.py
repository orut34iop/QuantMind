import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.services.engine.ai_strategy.app_factory import create_app
from backend.services.engine.ai_strategy.services.cos_uploader import InvalidUserIdError

# 添加项目路径（兼容直接执行 pytest）
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


def test_query_pool_auth_status_contract():
    client = TestClient(create_app())

    no_ctx = client.post(
        "/api/v1/strategy/query-pool",
        json={"dsl": "SELECT symbol WHERE pe <= 20"},
    )
    assert no_ctx.status_code == 401
    assert "未认证" in no_ctx.json().get("detail", "")

    user_only = client.post(
        "/api/v1/strategy/query-pool",
        headers={"X-User-Id": "1"},
        json={"dsl": "SELECT symbol WHERE pe <= 20"},
    )
    assert user_only.status_code == 403
    assert "未授权" in user_only.json().get("detail", "")


def test_legacy_routes_disabled_by_default():
    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/legacy/strategy/save-pool-file",
        json={"user_id": "1", "pool_name": "p", "pool": [{"symbol": "000001.SZ"}]},
    )

    assert resp.status_code == 200
    body = resp.json()
    # shared.response.error 返回业务错误码
    assert body.get("code") == 2001
    assert "legacy 路由已关闭" in body.get("message", "")


def test_save_to_cloud_invalid_user_id_returns_422(monkeypatch):
    class _DummyStorage:
        async def save_strategy(self, user_id, strategy_name, code, metadata):
            raise InvalidUserIdError(f"user_id 必须为整数类型字符串，当前值: {user_id}")

    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.api.v1.wizard.get_strategy_storage_service",
        lambda: _DummyStorage(),
    )

    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/strategy/save-to-cloud",
        json={
            "user_id": "abc",
            "strategy_name": "s1",
            "code": "print(1)",
            "metadata": {},
        },
    )
    assert resp.status_code == 422
    assert "user_id 必须为整数类型字符串" in resp.json().get("detail", "")
