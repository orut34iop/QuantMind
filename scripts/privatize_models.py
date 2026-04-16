import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Force DATABASE_URL to avoid env loading issues if needed
# os.environ["DATABASE_URL"] = "postgresql://quantmind:quantmind@quantmind-postgresql:5432/quantmind"

from backend.shared.database_manager_v2 import get_session
from sqlalchemy import text

PRODUCTION_ROOT = Path("/app/models/production")
TARGET_USER = "79311845"
TARGET_TENANT = "default"

BRANDING = {
    "alpha158": "Alpha158_Deep_Signal",
    "model_qlib": "Qlib_Base_Signal"
}

async def privatize():
    if not PRODUCTION_ROOT.exists():
        print(f"Error: {PRODUCTION_ROOT} not found")
        return

    async with get_session() as session:
        for subdir in PRODUCTION_ROOT.iterdir():
            if not subdir.is_dir():
                continue
            
            meta_file = subdir / "metadata.json"
            if not meta_file.exists():
                print(f"Skipping {subdir.name}: metadata.json missing")
                continue
                
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Skipping {subdir.name}: Error reading JSON: {e}")
                continue
                
            model_id = subdir.name
            display_name = BRANDING.get(model_id, meta.get("display_name") or model_id)
            
            # Prepare metadata
            metadata_json = {
                **meta,
                "display_name": display_name,
                "privatized_at": datetime.now(timezone.utc).isoformat(),
                "readonly": False, # Now private
                "system_default": False
            }
            
            # Check if model file exists
            model_file = "model.lgb" # Default
            if "files" in meta and isinstance(meta["files"], dict):
                model_file = meta["files"].get("model_checkpoint") or meta["files"].get("model_file") or "model.lgb"

            print(f"Privatizing {model_id} as '{display_name}' for user {TARGET_USER}...")
            
            await session.execute(
                text("""
                    INSERT INTO qm_user_models (
                        tenant_id, user_id, model_id, status, storage_path, model_file,
                        metadata_json, metrics_json, is_default, created_at, updated_at
                    ) VALUES (
                        :tenant_id, :user_id, :model_id, 'active', :storage_path, :model_file,
                        CAST(:metadata_json AS JSONB), CAST(:metrics_json AS JSONB), :is_default, NOW(), NOW()
                    )
                    ON CONFLICT (tenant_id, user_id, model_id) 
                    DO UPDATE SET 
                        metadata_json = EXCLUDED.metadata_json,
                        storage_path = EXCLUDED.storage_path,
                        updated_at = NOW();
                """),
                {
                    "tenant_id": TARGET_TENANT,
                    "user_id": TARGET_USER,
                    "model_id": model_id,
                    "storage_path": str(subdir),
                    "model_file": model_file,
                    "metadata_json": json.dumps(metadata_json, ensure_ascii=False),
                    "metrics_json": json.dumps(meta.get("metrics", {}), ensure_ascii=False),
                    "is_default": (model_id == "model_qlib")
                }
            )
        
        await session.commit()
        print("Success: Privatization complete.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(privatize())
