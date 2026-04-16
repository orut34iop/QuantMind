#!/usr/bin/env python3
"""
凌晨定时任务：将训练完成的模型产物批量上传至 COS
扫描 models/users 目录下所有 cos_upload_pending.json（uploaded=false），逐一上传后标记完成。

用法：
    python scripts/cos_upload_models.py
    python scripts/cos_upload_models.py --models-root /home/quantmind/models/users --dry-run

Cron（服务器 /etc/cron.d/quantmind-cos-upload）：
    0 3 * * * quantmind cd /home/quantmind && .venv/bin/python scripts/cos_upload_models.py >> logs/cos_upload.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

_DEFAULT_MODELS_ROOT = Path(
    os.getenv("HOST_PROJECT_PATH", "/home/quantmind")
) / "models" / "users"


def _cos_client():
    from qcloud_cos import CosConfig, CosS3Client
    return CosS3Client(CosConfig(
        Region=os.getenv("TENCENT_REGION", "ap-guangzhou"),
        SecretId=os.getenv("TENCENT_SECRET_ID", ""),
        SecretKey=os.getenv("TENCENT_SECRET_KEY", ""),
    ))


def upload_one(manifest_path: Path, dry_run: bool = False) -> bool:
    """上传单个模型目录，成功后将 manifest 标记为 uploaded=true。"""
    workspace = manifest_path.parent
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as e:
        logger.error("Failed to read manifest %s: %s", manifest_path, e)
        return False

    if manifest.get("uploaded"):
        logger.info("Already uploaded: %s", workspace.name)
        return True

    cos_prefix = manifest["cos_prefix"]
    bucket = manifest.get("bucket", os.getenv("TENCENT_BUCKET", "quantmind-1255718505"))
    files = manifest.get("files", [])

    logger.info("=== Uploading %s -> cos://%s/%s ===", workspace.name, bucket, cos_prefix)

    if dry_run:
        for f in files:
            local = workspace / f["local"]
            size_mb = local.stat().st_size / 1024 / 1024 if local.exists() else 0
            logger.info("  [DRY-RUN] %s -> %s  (%.1f MB)", f["local"], f["key"], size_mb)
        return True

    cos = _cos_client()
    failed = []
    for f in files:
        local = workspace / f["local"]
        if not local.exists():
            logger.warning("  SKIP (not found): %s", local)
            continue
        size_mb = local.stat().st_size / 1024 / 1024
        logger.info("  Uploading %s  (%.1f MB) -> %s", f["local"], size_mb, f["key"])
        try:
            with open(local, "rb") as fh:
                cos.put_object(
                    Bucket=bucket,
                    Key=f["key"],
                    Body=fh,
                    ContentType=f.get("content_type", "application/octet-stream"),
                )
            logger.info("  ✓ %s", f["key"])
        except Exception as e:
            logger.error("  ✗ Failed to upload %s: %s", f["local"], e)
            failed.append(f["local"])

    if failed:
        logger.error("Upload incomplete for %s, failed: %s", workspace.name, failed)
        return False

    # 标记完成
    manifest["uploaded"] = True
    manifest["uploaded_at"] = datetime.utcnow().isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    logger.info("  Marked as uploaded: %s", manifest_path.name)
    return True


def main():
    parser = argparse.ArgumentParser(description="批量上传模型产物到 COS")
    parser.add_argument("--models-root", default=str(_DEFAULT_MODELS_ROOT),
                        help="模型根目录（默认 models/users）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不实际上传")
    args = parser.parse_args()

    models_root = Path(args.models_root)
    if not models_root.exists():
        logger.error("models-root not found: %s", models_root)
        sys.exit(1)

    # 扫描所有 cos_upload_pending.json
    manifests = sorted(models_root.rglob("cos_upload_pending.json"))
    pending = [m for m in manifests if not json.loads(m.read_text()).get("uploaded")]

    logger.info("Found %d pending manifest(s) in %s", len(pending), models_root)
    if not pending:
        logger.info("Nothing to upload. Exiting.")
        return

    success, failure = 0, 0
    for manifest_path in pending:
        ok = upload_one(manifest_path, dry_run=args.dry_run)
        if ok:
            success += 1
        else:
            failure += 1

    logger.info("Done: %d succeeded, %d failed", success, failure)
    if failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
