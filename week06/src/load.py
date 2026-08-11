import sqlite3
from .config import WAREHOUSE_DB

def load_data(customers, products, sales):
    """
    Load dim_customer, dim_product, fact_sales into the SQLite warehouse.
    UNIQUE primary keys + INSERT OR IGNORE make repeated runs idempotent.
    """
    WAREHOUSE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WAREHOUSE_DB)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_id TEXT PRIMARY KEY,
            name TEXT,
            province TEXT,
            email TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_product (
            product_id TEXT PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            price REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_sales (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            product_id TEXT,
            order_date TEXT,
            qty INTEGER,
            unit_price REAL,
            discount_pct REAL,
            sales_amount REAL
        )
        """
    )

    cur.executemany(
        "INSERT OR IGNORE INTO dim_customer (customer_id, name, province, email) VALUES (?, ?, ?, ?)",
        customers[["customer_id", "name", "province", "email"]].itertuples(index=False, name=None),
    )
    cur.executemany(
        "INSERT OR IGNORE INTO dim_product (product_id, product_name, category, price) VALUES (?, ?, ?, ?)",
        products[["product_id", "product_name", "category", "price"]].itertuples(index=False, name=None),
    )
    cur.executemany(
        """
        INSERT OR IGNORE INTO fact_sales
            (order_id, customer_id, product_id, order_date, qty, unit_price, discount_pct, sales_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sales[
            [
                "order_id",
                "customer_id",
                "product_id",
                "order_date",
                "qty",
                "unit_price",
                "discount_pct",
                "sales_amount",
            ]
        ].itertuples(index=False, name=None),
    )

    conn.commit()
    conn.close()
