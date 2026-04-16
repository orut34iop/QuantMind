import os
import json
import shutil
from datetime import datetime
from pathlib import Path

def promote():
    source_dir = Path("models/candidates/custom_lgbm_duckdb_64f_20260228_135031")
    prod_dir = Path("models/production/model_qlib")
    archive_dir = Path("models/archive")
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Backup existing production
    if prod_dir.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = archive_dir / f"model_qlib_backup_{timestamp}"
        shutil.copytree(prod_dir, backup_path)
        print(f"Backed up current production to {backup_path}")
    else:
        prod_dir.mkdir(parents=True, exist_ok=True)
        
    # 2. Copy new model files
    for file_name in ["model.txt", "feature_importance.csv", "grid_search_results.csv"]:
        src_file = source_dir / file_name
        if src_file.exists():
            shutil.copy2(src_file, prod_dir / file_name)
            
    # 3. Update metadata
    with open(source_dir / "metadata.json", "r") as f:
        src_meta = json.load(f)
        
    # Read existing prod metadata if exists to keep structure
    prod_meta = {}
    prod_meta_file = prod_dir / "metadata.json"
    if prod_meta_file.exists():
        with open(prod_meta_file, "r") as f:
            try:
                prod_meta = json.load(f)
            except:
                pass
                
    prod_meta.update({
        "model_name": "model_qlib_custom64_prod",
        "model_file": "model.txt",
        "model_format": "lightgbm_txt",
        "resolved_class": "lightgbm.Booster",
        "feature_set": "64",
        "feature_count": 64,
        "metrics": src_meta.get("metrics", {}), # Contains the 0.0503 rank IC
        "description": f"Promoted from candidate {source_dir.name} (ASOF JOIN Optimized)",
        "promoted_at": datetime.now().isoformat(),
        "source_candidate": str(source_dir)
    })
    
    with open(prod_meta_file, "w") as f:
        json.dump(prod_meta, f, indent=2)
        
    print(f"Successfully promoted model to {prod_dir}")
    print("New Production Metrics:")
    print(json.dumps(prod_meta["metrics"], indent=2))

if __name__ == "__main__":
    promote()
