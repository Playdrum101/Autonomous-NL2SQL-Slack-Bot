import sqlite3
import os
from pathlib import Path

# Dynamically find the project root (one folder up from /scripts)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ecommerce.db"

# Update your connection line to use DB_PATH
# conn = sqlite3.connect(DB_PATH)
DB_NAME = "ecommerce.db"

def setup_database():
    # Remove existing db if it exists to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Connect to SQLite (this creates the file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    
    # Enforce foreign key constraints in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    
    cursor = conn.cursor()

    # 1. Create Users Table
    cursor.execute('''
    CREATE TABLE Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        signup_date DATE NOT NULL
    )
    ''')

    # 2. Create Products Table
    cursor.execute('''
    CREATE TABLE Products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL
    )
    ''')

    # 3. Create Coupons Table
    cursor.execute('''
    CREATE TABLE Coupons (
        coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_percent REAL NOT NULL,
        valid_until DATE NOT NULL
    )
    ''')

    # 4. Create Orders Table
    cursor.execute('''
    CREATE TABLE Orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        coupon_id INTEGER,
        quantity INTEGER NOT NULL,
        order_date DATE NOT NULL,
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        FOREIGN KEY (product_id) REFERENCES Products(product_id),
        FOREIGN KEY (coupon_id) REFERENCES Coupons(coupon_id)
    )
    ''')

    # Insert Mock Data
    users_data = [
        ("Alice Smith", "alice@example.com", "2024-01-15"),
        ("Bob Johnson", "bob@example.com", "2024-02-20"),
        ("Charlie Brown", "charlie@example.com", "2024-03-10")
    ]
    cursor.executemany("INSERT INTO Users (name, email, signup_date) VALUES (?, ?, ?)", users_data)

    products_data = [
        ("Laptop Pro", "Electronics", 1200.00, 50),
        ("Wireless Mouse", "Electronics", 25.50, 200),
        ("Coffee Maker", "Home Appliances", 89.99, 30),
        ("Desk Chair", "Furniture", 150.00, 45)
    ]
    cursor.executemany("INSERT INTO Products (name, category, price, stock_quantity) VALUES (?, ?, ?, ?)", products_data)

    coupons_data = [
        ("SAVE10", 10.0, "2026-12-31"),
        ("WINTER20", 20.0, "2026-03-01")
    ]
    cursor.executemany("INSERT INTO Coupons (code, discount_percent, valid_until) VALUES (?, ?, ?)", coupons_data)

    orders_data = [
        (1, 1, 1, 1, "2024-01-16"), 
        (2, 2, None, 2, "2024-02-21"), 
        (3, 4, 2, 1, "2024-03-11")  
    ]
    cursor.executemany("INSERT INTO Orders (user_id, product_id, coupon_id, quantity, order_date) VALUES (?, ?, ?, ?, ?)", orders_data)

    # Save and close
    conn.commit()
    conn.close()
    
    print(f"Success: '{DB_PATH.name}' created with mock data!")

if __name__ == "__main__":
    setup_database()