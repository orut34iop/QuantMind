import pandas as pd
import numpy as np
import os
import duckdb
import lightgbm as lgb
import json
from pathlib import Path
from datetime import datetime

# Reuse our elite logic
from scripts.train_final_sprint import _sql, FEATURE_COLS_64, _neutralize_strict, _load_split_df

def generate_master_predictions():
    db_path = 'db/csmar_data.duckdb'
    model_dir = Path('models/production/model_qlib')
    
    if not model_dir.exists():
        print(f"Error: Model directory {model_dir} not found.")
        return

    # 1. Load all 10 seed models
    print("[1/3] Loading 10-Seed Ensemble Models...")
    seed_files = sorted(list(model_dir.glob("seed_*.txt")))
    if not seed_files:
        # Fallback to single model.txt if seeds not found
        seed_files = [model_dir / "model.txt"]
        print("Warning: Only single model.txt found, generating single-seed predictions.")
    
    boosters = [lgb.Booster(model_file=str(f)) for f in seed_files]
    
    # 2. Extract and Neutralize Data (2023-2025)
    conn = duckdb.connect(db_path, read_only=True)
    print("[2/3] Extracting and Neutralizing Data (2023-2025)...")
    # We process in chunks to avoid memory pressure
    all_preds = []
    
    for year in [2023, 2024, 2025]:
        print(f" >> Processing Year {year}...")
        df_year = _load_split_df(conn, f"{year}-01-01", f"{year}-12-31")
        
        X = df_year[FEATURE_COLS_64].fillna(0.0).astype('float32').to_numpy()
        
        # Ensemble Prediction
        year_preds = []
        for b in boosters:
            year_preds.append(b.predict(X))
        
        avg_score = np.mean(year_preds, axis=0)
        
        # Create Qlib-standard DataFrame
        res_df = pd.DataFrame({
            'score': avg_score
        }, index=pd.MultiIndex.from_arrays([df_year['date'], df_year['stkcd']], names=['datetime', 'instrument']))
        
        all_preds.append(res_df)
    
    conn.close()
    
    # 3. Save Final Master Pickle
    print("[3/3] Saving Master Predictions...")
    final_df = pd.concat(all_preds).sort_index()
    output_path = model_dir / "predictions.pkl"
    final_df.to_pickle(output_path)
    
    print(f"--- SUCCESS ---")
    print(f"Master predictions saved to: {output_path}")
    print(f"Total rows: {len(final_df)}")
    print(f"Date range: {final_df.index.get_level_values(0).min()} to {final_df.index.get_level_values(0).max()}")

if __name__ == "__main__":
    generate_master_predictions()
