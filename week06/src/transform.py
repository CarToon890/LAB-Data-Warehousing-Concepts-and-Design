import pandas as pd
from .config import PROVINCE_MAP

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%b-%Y"]


def _parse_date(value):
    """Try each known raw date format in turn; NaT if none match."""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(text, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def _standardize_province(value):
    if pd.isna(value) or str(value).strip() == "":
        return "Unknown"
    key = str(value).strip().lower()
    return PROVINCE_MAP.get(key, str(value).strip().title())


def transform_data(raw):
    """
    Customers, Products, Orders cleaning + merge into fact sales.
    Returns: clean_customers, clean_products, sales, rejects
    """

    # ---------------- Customers ----------------
    customers = (
        raw["customers"].drop_duplicates(subset="customer_id", keep="first").copy()
    )
    customers["province"] = customers["province"].apply(_standardize_province)
    customers["email"] = customers["email"].fillna("Unknown")
    customers.loc[customers["email"].astype(str).str.strip() == "", "email"] = "Unknown"

    # ---------------- Products ----------------
    products = raw["products"].rename(
        columns={"category.name": "category", "pricing.price": "price"}
    ).copy()
    products["price"] = (
        products["price"].astype(str).str.replace(",", "", regex=False)
    )
    products["price"] = pd.to_numeric(products["price"], errors="coerce")
    products["category"] = products["category"].fillna("Unknown")
    products.loc[products["category"].astype(str).str.strip() == "", "category"] = "Unknown"
    clean_products = products[["product_id", "product_name", "category", "price"]].copy()

    # ---------------- Orders ----------------
    orders = raw["orders"].drop_duplicates(subset="order_id", keep="first").copy()
    orders["order_date"] = orders["order_date"].apply(_parse_date)
    orders["status"] = orders["status"].astype(str).str.strip().str.lower()

    invalid_mask = (
        (orders["qty"] <= 0)
        | (orders["unit_price"] <= 0)
        | (orders["discount_pct"] < 0)
        | (orders["discount_pct"] > 100)
        | (orders["order_date"].isna())
    )
    rejects = orders[invalid_mask].copy()
    rejects["reject_reason"] = "invalid qty/unit_price/discount_pct/order_date"
    valid_orders = orders[~invalid_mask].copy()

    # keep only paid/completed
    kept_orders = valid_orders[valid_orders["status"].isin(["paid", "completed"])].copy()

    # reject unknown customer_id / product_id
    known_customers = set(customers["customer_id"])
    known_products = set(clean_products["product_id"])
    unknown_mask = (
        ~kept_orders["customer_id"].isin(known_customers)
        | ~kept_orders["product_id"].isin(known_products)
    )
    unknown_rejects = kept_orders[unknown_mask].copy()
    unknown_rejects["reject_reason"] = "unknown customer_id or product_id"
    rejects = pd.concat([rejects, unknown_rejects], ignore_index=True)

    matched_orders = kept_orders[~unknown_mask].copy()

    # ---------------- Calculate + assemble fact rows ----------------
    matched_orders["gross_amount"] = matched_orders["qty"] * matched_orders["unit_price"]
    matched_orders["discount_amount"] = (
        matched_orders["gross_amount"] * matched_orders["discount_pct"] / 100
    )
    matched_orders["sales_amount"] = (
        matched_orders["gross_amount"] - matched_orders["discount_amount"]
    )
    matched_orders["order_date"] = matched_orders["order_date"].dt.strftime("%Y-%m-%d")

    sales = matched_orders[
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
    ].copy()

    if "order_date" in rejects.columns:
        rejects["order_date"] = rejects["order_date"].astype(str)

    return customers, clean_products, sales, rejects
