import json
import networkx as nx
from sqlalchemy import create_engine, inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ecommerce.db"
OUTPUT_FILE = PROJECT_ROOT / "data" / "relationship_graph.json"

# Update your SQLAlchemy engine line to use the new DB_PATH:
# DB_URL = f"sqlite:///{DB_PATH}"
# engine = create_engine(DB_URL)
# ...
# with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
DB_NAME = "ecommerce.db"
DB_URL = f"sqlite:///{DB_PATH}"
OUTPUT_FILE = "relationship_graph.json"

def build_relationship_graph():
    print("Building Relationship Graph (NetworkX)...")
    
    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    
    # Initialize a Directed Graph
    G = nx.DiGraph()
    
    # 1. Add all tables as nodes
    for table_name in inspector.get_table_names():
        G.add_node(table_name)
        
    # 2. Extract Foreign Keys and create edges
    edge_count = 0
    for table_name in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            referred_table = fk["referred_table"]
            local_cols = fk["constrained_columns"]
            referred_cols = fk["referred_columns"]
            
            # Draw an edge mapping the exact JOIN path
            relationship_label = f"{table_name}.{local_cols[0]} -> {referred_table}.{referred_cols[0]}"
            G.add_edge(
                table_name, 
                referred_table, 
                relationship=relationship_label
            )
            edge_count += 1
            print(f"Mapped Edge: {relationship_label}")
            
    # 3. Export the graph topology to JSON for the LLM context
    graph_data = nx.node_link_data(G)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=4)
        
    print(f"\nSuccess! Graph with {G.number_of_nodes()} tables and {edge_count} join paths saved to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    build_relationship_graph()