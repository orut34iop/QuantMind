#!/usr/bin/env python3
"""
将模型训练特征字典（JSON）同步到 qm_feature_set_* 注册表。

默认行为：
1. upsert qm_feature_category / qm_feature_definition
2. 覆盖写入指定 version_id 的 qm_feature_set_item
3. 将该版本置为 active，并将其他 active 版本置为 inactive
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session


@dataclass
class SyncStats:
    version_id: str
    version_name: str
    category_count: int
    feature_count: int
    item_count: int
    before_active: dict[str, Any] | None
    after_active: dict[str, Any] | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync feature catalog JSON to qm_feature_set_* tables")
    parser.add_argument(
        "--catalog",
        default="config/features/model_training_feature_catalog_v1.json",
        help="Feature catalog JSON path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only parse and print summary, do not write database",
    )
    parser.add_argument(
        "--keep-other-active",
        action="store_true",
        help="Do not inactivate other active versions",
    )
    return parser.parse_args()


def load_catalog(path: Path) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    version_id = str(obj.get("version_id") or "").strip()
    version_name = str(obj.get("name") or obj.get("version_name") or version_id).strip()
    categories_raw = obj.get("categories")
    if not version_id:
        raise ValueError("catalog missing version_id")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise ValueError("catalog missing categories")

    categories: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    seen_feature_keys: set[str] = set()

    for idx, category in enumerate(categories_raw, start=1):
        if not isinstance(category, dict):
            continue
        cid = str(category.get("id") or "").strip()
        if not cid:
            continue
        categories.append(
            {
                "category_id": cid,
                "category_name": str(category.get("name") or cid).strip(),
                "sort_order": int(category.get("order") or idx),
            }
        )

        features = category.get("features") if isinstance(category.get("features"), list) else []
        for order_idx, feature in enumerate(features, start=1):
            if not isinstance(feature, dict):
                continue
            key = str(feature.get("key") or "").strip()
            if not key:
                continue
            feature_id = str(feature.get("feature_id") or "").strip() or f"feat_auto_{len(seen_feature_keys) + 1:03d}"
            feature_name = str(feature.get("feature_name") or feature.get("description") or key).strip()
            formula = str(feature.get("formula") or "")
            source_table_fields = str(feature.get("source_table_fields") or feature.get("source") or "")
            if key not in seen_feature_keys:
                definitions.append(
                    {
                        "feature_id": feature_id,
                        "feature_key": key,
                        "feature_name": feature_name,
                        "category_id": cid,
                        "formula": formula,
                        "source_table_fields": source_table_fields,
                    }
                )
                seen_feature_keys.add(key)

            items.append(
                {
                    "version_id": version_id,
                    "category_id": cid,
                    "feature_key": key,
                    "order_no": int(feature.get("order_no") or order_idx),
                    "enabled": bool(feature.get("enabled", True)),
                }
            )

    if not items:
        raise ValueError("catalog has no valid features")

    return version_id, version_name, categories, definitions, items


async def sync_catalog(
    version_id: str,
    version_name: str,
    categories: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    items: list[dict[str, Any]],
    dry_run: bool,
    keep_other_active: bool,
) -> SyncStats:
    async with get_session(read_only=not dry_run) as session:
        before_active = (
            await session.execute(
                text(
                    """
                    SELECT version_id, version_name, feature_count, status, effective_at, created_at
                    FROM qm_feature_set_version
                    WHERE status='active'
                    ORDER BY effective_at DESC, created_at DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()

        if not dry_run:
            for row in categories:
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_feature_category (category_id, category_name, sort_order)
                        VALUES (:category_id, :category_name, :sort_order)
                        ON CONFLICT (category_id)
                        DO UPDATE SET
                            category_name=EXCLUDED.category_name,
                            sort_order=EXCLUDED.sort_order
                        """
                    ),
                    row,
                )

            for row in definitions:
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_feature_definition (
                            feature_id, feature_key, feature_name, category_id, formula, source_table_fields
                        )
                        VALUES (
                            :feature_id, :feature_key, :feature_name, :category_id, :formula, :source_table_fields
                        )
                        ON CONFLICT (feature_key)
                        DO UPDATE SET
                            feature_id=EXCLUDED.feature_id,
                            feature_name=EXCLUDED.feature_name,
                            category_id=EXCLUDED.category_id,
                            formula=EXCLUDED.formula,
                            source_table_fields=EXCLUDED.source_table_fields
                        """
                    ),
                    row,
                )

            await session.execute(
                text("DELETE FROM qm_feature_set_item WHERE version_id=:version_id"),
                {"version_id": version_id},
            )
            for row in items:
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_feature_set_item (
                            version_id, category_id, feature_key, order_no, enabled
                        ) VALUES (
                            :version_id, :category_id, :feature_key, :order_no, :enabled
                        )
                        """
                    ),
                    row,
                )

            await session.execute(
                text(
                    """
                    INSERT INTO qm_feature_set_version (
                        version_id, version_name, feature_count, status, effective_at
                    ) VALUES (
                        :version_id, :version_name, :feature_count, 'active', :effective_at
                    )
                    ON CONFLICT (version_id)
                    DO UPDATE SET
                        version_name=EXCLUDED.version_name,
                        feature_count=EXCLUDED.feature_count,
                        status='active',
                        effective_at=EXCLUDED.effective_at
                    """
                ),
                {
                    "version_id": version_id,
                    "version_name": version_name,
                    "feature_count": len(items),
                    "effective_at": datetime.now(timezone.utc),
                },
            )

            if not keep_other_active:
                await session.execute(
                    text(
                        """
                        UPDATE qm_feature_set_version
                        SET status='inactive'
                        WHERE version_id <> :version_id
                          AND status='active'
                        """
                    ),
                    {"version_id": version_id},
                )

        after_active = (
            await session.execute(
                text(
                    """
                    SELECT version_id, version_name, feature_count, status, effective_at, created_at
                    FROM qm_feature_set_version
                    WHERE status='active'
                    ORDER BY effective_at DESC, created_at DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()

    return SyncStats(
        version_id=version_id,
        version_name=version_name,
        category_count=len(categories),
        feature_count=len(definitions),
        item_count=len(items),
        before_active=dict(before_active) if before_active else None,
        after_active=dict(after_active) if after_active else None,
    )


async def async_main() -> int:
    args = parse_args()
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")

    version_id, version_name, categories, definitions, items = load_catalog(catalog_path)
    stats = await sync_catalog(
        version_id=version_id,
        version_name=version_name,
        categories=categories,
        definitions=definitions,
        items=items,
        dry_run=bool(args.dry_run),
        keep_other_active=bool(args.keep_other_active),
    )

    print("SYNC_FEATURE_CATALOG_RESULT")
    print(f"dry_run={args.dry_run}")
    print(f"version_id={stats.version_id}")
    print(f"version_name={stats.version_name}")
    print(f"category_count={stats.category_count}")
    print(f"feature_count={stats.feature_count}")
    print(f"item_count={stats.item_count}")
    print(f"before_active={stats.before_active}")
    print(f"after_active={stats.after_active}")
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
