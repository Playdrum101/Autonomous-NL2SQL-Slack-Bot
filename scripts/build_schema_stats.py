import sqlite3
import json
from sqlalchemy import create_engine, inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ecommerce.db"
OUTPUT_FILE = PROJECT_ROOT / "data" / "schema_stats.json"

# Update your connection and file saving lines to use these new variables:
# conn = sqlite3.connect(DB_PATH)
# ...
# with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
DB_NAME = "ecommerce.db"
DB_URL = f"sqlite:///{DB_PATH}"


def get_top_frequent_values(cursor, table, column, limit=3):
    """Fetches the top N most frequent non-null values for a column."""
    try:
        query = f"""
            SELECT {column}, COUNT(*) as freq 
            FROM {table} 
            WHERE {column} IS NOT NULL 
            GROUP BY {column} 
            ORDER BY freq DESC 
            LIMIT {limit};
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return [row[0] for row in results]
    except Exception as e:
        return []

def extract_schema_and_stats():
    print(f"Extracting Schema & Stats from database...")
    
    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    schema_stats = {}

    for table_name in inspector.get_table_names():
        columns_info = []
        
        # Fetch columns
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_cols = pk_constraint.get("constrained_columns", [])
        
        for col in columns:
            col_name = col["name"]
            col_type = str(col["type"])
            is_pk = col_name in pk_cols
            
            # Fetch top 3 frequent values
            sample_values = get_top_frequent_values(cursor, table_name, col_name, limit=3)
            
            columns_info.append({
                "column_name": col_name,
                "data_type": col_type,
                "is_primary_key": is_pk,
                "top_frequent_values": sample_values
            })
            
        schema_stats[table_name] = {
            "columns": columns_info,
            "row_count": cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        }

    conn.close()

    # Save locally to schema_stats.json
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schema_stats, f, indent=4)
        
    print(f"Success! Schema and stats saved to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    extract_schema_and_stats()