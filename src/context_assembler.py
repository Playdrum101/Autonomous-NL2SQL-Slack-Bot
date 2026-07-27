import json
import chromadb
from pathlib import Path

# Define exact paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema_stats.json"
GRAPH_PATH = PROJECT_ROOT / "data" / "relationship_graph.json"

def assemble_context(user_query):
    print(f"Assembling Context Brain for query: '{user_query}'\n")
    print("-" * 50)
    
    # 1. Semantic Search via Vector Store
    client =  chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(name="schema_embeddings")
    
    # Lower n_results to 2 so we don't force irrelevant tables
    results = collection.query(query_texts=[user_query], n_results=2)
    matched_tables = [meta["table"] for meta in results["metadatas"][0]]
    
    # 2. Hybrid Search: Exact-Match via Schema Store
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        full_schema = json.load(f)
        
    # Scan top_frequent_values for lexical matches (e.g., catching "Laptop Pro")
    for table, data in full_schema.items():
        for col in data["columns"]:
            for val in col["top_frequent_values"]:
                # If a known database value is mentioned in the query, pull that table!
                if str(val).lower() in user_query.lower() and table not in matched_tables:
                    matched_tables.append(table)
                    
    print(f"[OK] Hybrid Search retrieved relevant tables: {matched_tables}")
    
    # Filter the schema
    filtered_schema = {t: full_schema[t] for t in matched_tables if t in full_schema}
    print("[OK] Schema Store injected data types and sample values.")
    
    # 3. Robust Join Paths Extraction
    with open(GRAPH_PATH, "r", encoding="utf-8") as f:
        graph_data = json.load(f)
        
    # Safely extract edges regardless of networkx minor version differences
    edges = graph_data.get("links", []) or graph_data.get("edges", [])
    join_paths = []
    
    for edge in edges:
        if "relationship" in edge:
            # Token Optimization: Only include join paths connected to our matched tables
            if edge.get("source") in matched_tables or edge.get("target") in matched_tables:
                join_paths.append(edge["relationship"])
                
    print("[OK] Relationship Graph injected exact Foreign Key mappings.")
    
    # 4. Construct the Final LLM Context Prompt
    context_prompt = f"""You are an expert SQL Generator. Write a highly accurate SQLite query to answer the User Query based strictly on the Database Context provided below. 

=== DATABASE CONTEXT ===

[RELEVANT TABLES & STATS]
{json.dumps(filtered_schema, indent=2)}

[GUARANTEED JOIN PATHS]
{chr(10).join(join_paths)}

========================
USER QUERY: {user_query}
"""
    
    print("-" * 50)
    print("FINAL LLM PAYLOAD GENERATED:\n")
    print(context_prompt)
    
    return context_prompt

if __name__ == "__main__":
    dummy_query = "Who purchased a Laptop Pro and used the SAVE10 coupon?"
    assemble_context(dummy_query)