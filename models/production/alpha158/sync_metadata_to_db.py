#!/usr/bin/env python3
import json
import os
import psycopg2
from pathlib import Path

def sync():
    # Load metadata.json
    meta_path = Path("/app/models/production/alpha158/metadata.json")
    if not meta_path.exists():
        print(f"Error: {meta_path} not found")
        return
        
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
        
    # Prepare the records
    # We want to sync to both 'system' user and all other users who have this model
    # Note: For production, we usually only update 'system' and let users re-materialize,
    # but since this is a specific stability task, we'll update all instances of 'alpha158'.
    
    perf = meta.get("performance_metrics", {})
    metadata_json = {
        "display_name": meta.get("model_info", {}).get("name") or "Alpha158_Base",
        "model_type": meta.get("model_type") or "LGBModel",
        "feature_count": meta.get("feature_count"),
        "features": meta.get("feature_columns", []),
        "performance_metrics": perf,
        "train_start": meta.get("train_start"),
        "train_end": meta.get("train_end"),
        "val_start": meta.get("valid_start"),
        "val_end": meta.get("valid_end"),
        "test_start": meta.get("test_start"),
        "test_end": meta.get("test_end"),
        "system_default": True,
        "readonly": True
    }
    metrics_json = perf
    
    # DB Connection Info inside container
    # DATABASE_URL: postgresql+asyncpg://quantmind:9d4e1f8a2c7b6035e8f1a9c2d4b7e6f0@quantmind-postgresql:5432/quantmind
    conn_str = "dbname='quantmind' user='quantmind' host='quantmind-postgresql' password='9d4e1f8a2c7b6035e8f1a9c2d4b7e6f0' port='5432'"
    
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        sql = """
            UPDATE qm_user_models
            SET metadata_json = %s,
                metrics_json = %s,
                updated_at = NOW()
            WHERE model_id = 'alpha158'
        """
        
        print("Executing DB update...")
        cur.execute(sql, (json.dumps(metadata_json, ensure_ascii=False), json.dumps(metrics_json, ensure_ascii=False)))
        print(f"Update complete. Rows affected: {cur.rowcount}")
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    sync()
