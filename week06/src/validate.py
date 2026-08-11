import sqlite3
from .config import WAREHOUSE_DB

def validate_data(source_sales):
    """
    Compare transformed (source) sales against what actually landed in the
    warehouse and report PASS/FAIL.
    """
    conn = sqlite3.connect(WAREHOUSE_DB)
    warehouse_rows = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    duplicate_order_ids = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT order_id FROM fact_sales GROUP BY order_id HAVING COUNT(*) > 1"
        ")"
    ).fetchone()[0]
    warehouse_total_sales = conn.execute(
        "SELECT COALESCE(SUM(sales_amount), 0) FROM fact_sales"
    ).fetchone()[0]
    conn.close()

    source_valid_rows = len(source_sales)
    source_total_sales = round(float(source_sales["sales_amount"].sum()), 2)
    warehouse_total_sales = round(float(warehouse_total_sales), 2)

    status = (
        "PASS"
        if source_valid_rows == warehouse_rows
        and duplicate_order_ids == 0
        and abs(source_total_sales - warehouse_total_sales) < 0.01
        else "FAIL"
    )

    return {
        "source_valid_rows": source_valid_rows,
        "warehouse_rows": warehouse_rows,
        "duplicate_order_ids": duplicate_order_ids,
        "source_total_sales": source_total_sales,
        "warehouse_total_sales": warehouse_total_sales,
        "status": status,
    }
