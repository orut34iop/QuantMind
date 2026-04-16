#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import text

from backend.shared.database_manager_v2 import init_database, get_session
from backend.shared.model_registry import model_registry_service


async def _backfill_system_default() -> int:
    now = datetime.now(timezone.utc)
    metadata_json = json.dumps({"system_default": True, "readonly": True}, ensure_ascii=False)
    async with get_session() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT COALESCE(tenant_id, 'default') AS tenant_id, user_id
                    FROM admin_training_jobs
                    WHERE COALESCE(user_id, '') <> ''
                    """
                )
            )
        ).mappings().all()

        inserted = 0
        for row in rows:
            tenant_id = str(row.get("tenant_id") or "default")
            user_id = str(row.get("user_id") or "").strip()
            if not user_id:
                continue
            current_default = (
                await session.execute(
                    text(
                        """
                        SELECT model_id
                        FROM qm_user_models
                        WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_default = TRUE
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "user_id": user_id},
                )
            ).mappings().first()
            exists = (
                await session.execute(
                    text(
                        """
                        SELECT 1
                        FROM qm_user_models
                        WHERE tenant_id = :tenant_id AND user_id = :user_id AND model_id = 'model_qlib'
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "user_id": user_id},
                )
            ).first()
            if exists:
                continue
            await session.execute(
                text(
                    """
                    INSERT INTO qm_user_models (
                        tenant_id, user_id, model_id, source_run_id, status, storage_path, model_file,
                        metadata_json, metrics_json, is_default, created_at, updated_at, activated_at
                    ) VALUES (
                        :tenant_id, :user_id, 'model_qlib', NULL, 'active',
                        :storage_path, 'model.lgb',
                        CAST(:metadata_json AS JSONB), CAST('{}' AS JSONB), :is_default,
                        :created_at, :updated_at, :activated_at
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "storage_path": "/app/models/production/model_qlib",
                    "metadata_json": metadata_json,
                    "is_default": False if current_default else True,
                    "created_at": now,
                    "updated_at": now,
                    "activated_at": None if current_default else now,
                },
            )
            inserted += 1
    return inserted


async def main() -> None:
    await init_database()
    await model_registry_service.ensure_tables()
    inserted = await _backfill_system_default()
    print(f"[migration] qm_user_models/qm_strategy_model_bindings ready, backfilled={inserted}")


if __name__ == "__main__":
    asyncio.run(main())
