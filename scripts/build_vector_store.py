import chromadb
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = PROJECT_ROOT / "chroma_db"


def build_vector_store():
    print("Initializing Local Vector Store (ChromaDB)...")
    
    # 1. Plain-English descriptions bridging natural language to SQL tables
    schema_descriptions = [
        {
            "id": "table_users",
            "table": "Users",
            "description": "Contains customer information, including their full name, email address, and the date they signed up for an account."
        },
        {
            "id": "table_products",
            "table": "Products",
            "description": "A catalog of items available for sale, including product name, category (like Electronics, Home Appliances, or Furniture), price, and current stock quantity (inventory or availability)."
        },
        {
            "id": "table_coupons",
            "table": "Coupons",
            "description": "Stores promotional discount codes applied to orders. Includes the text code (e.g. SAVE10), the discount percentage, and the expiration date (valid_until)."
        },
        {
            "id": "table_orders",
            "table": "Orders",
            "description": "Records all purchase transactions. Links a user to a specific product, includes the quantity purchased, the date of the order, and any applied coupon code."
        }
    ]

    # 2. Setup ChromaDB client (saves locally to a folder named 'chroma_db')
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    
    # 3. Create a collection (similar to a table in SQL, but for vectors)
    collection = client.get_or_create_collection(name="schema_embeddings")

    # 4. Extract data for insertion
    ids = [item["id"] for item in schema_descriptions]
    documents = [item["description"] for item in schema_descriptions]
    metadatas = [{"table": item["table"]} for item in schema_descriptions]

    # 5. Embed and store the documents
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print(f"Success! Embedded {len(documents)} table descriptions into the ChromaDB vector store at './chroma_db'.")

if __name__ == "__main__":
    build_vector_store()