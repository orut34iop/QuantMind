import duckdb
import json

db_path = r"E:\code\quantmind\db\stock_new.duckdb"
output_path = r"E:\code\quantmind\backend\scripts\duckdb_schema.json"


def export_schema():
    conn = duckdb.connect(db_path, read_only=True)
    tables = conn.execute("SHOW TABLES").fetchall()

    metadata = {}
    for table_tuple in tables:
        table_name = table_tuple[0]
        schema = conn.execute(f"DESCRIBE {table_name}").fetchall()
        cols = [{"name": c[0], "type": str(c[1])} for c in schema]
        metadata[table_name] = cols

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    conn.close()
    print(f"Schema exported to {output_path}")


if __name__ == "__main__":
    export_schema()
