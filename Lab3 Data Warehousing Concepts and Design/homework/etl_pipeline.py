import pandas as pd
import sqlite3

# ==========================================
# Phase 1: EXTRACT (อ่านข้อมูลดิบ)
# ==========================================
print("1. [EXTRACT] ดึงข้อมูลดิบจาก retail_logs.csv...")
raw_df = pd.read_csv('retail_logs.csv')

# ล้างช่องว่างและปรับตัวพิมพ์ให้เป็นมาตรฐาน เพื่อไม่ให้ dim table ซ้ำซ้อนกันโดยไม่จำเป็น
raw_df['Store_Code'] = raw_df['Store_Code'].str.strip()
title_case_columns = ['Branch', 'Province', 'Region', 'Product_Name', 'Category']
for col in title_case_columns:
    raw_df[col] = raw_df[col].str.strip().str.title()

# ==========================================
# Phase 2: TRANSFORM (สร้าง Star Schema)
# ==========================================
print("2. [TRANSFORM] ปรับแต่งโครงสร้างข้อมูลแบบ Star Schema...")

# 2.1 สร้าง dim_location
dim_location = raw_df[['Store_Code', 'Branch', 'Province', 'Region']].drop_duplicates().reset_index(drop=True)
dim_location['location_id'] = dim_location.index + 1
dim_location = dim_location[['location_id', 'Store_Code', 'Branch', 'Province', 'Region']]

# 2.2 สร้าง dim_product
dim_product = raw_df[['Product_Name', 'Category']].drop_duplicates().reset_index(drop=True)
dim_product['product_id'] = dim_product.index + 1
dim_product = dim_product[['product_id', 'Product_Name', 'Category']]

# 2.3 สร้าง dim_date
raw_df['Date_Parsed'] = pd.to_datetime(raw_df['Sale_Date'], dayfirst=True, format='mixed')
dim_date = raw_df[['Date_Parsed']].drop_duplicates().reset_index(drop=True)
dim_date['date_id'] = dim_date.index + 1
dim_date['Date'] = dim_date['Date_Parsed'].dt.strftime('%Y-%m-%d')
dim_date['Year'] = dim_date['Date_Parsed'].dt.year
dim_date['Month'] = dim_date['Date_Parsed'].dt.month
dim_date['Day'] = dim_date['Date_Parsed'].dt.day
dim_date = dim_date[['date_id', 'Date', 'Year', 'Month', 'Day']]

# 2.4 สร้าง fact_sales (Map เอา Surrogate Keys เข้าตาราง Fact)
fact_sales = pd.merge(raw_df, dim_location, on=['Store_Code', 'Branch', 'Province', 'Region'], how='left')
fact_sales = pd.merge(fact_sales, dim_product, on=['Product_Name', 'Category'], how='left')

fact_sales['Date_Format'] = fact_sales['Date_Parsed'].dt.strftime('%Y-%m-%d')
fact_sales = pd.merge(fact_sales, dim_date, left_on='Date_Format', right_on='Date', how='left')

# คำนวณยอดขายสุทธิ (Total_Amount)
fact_sales['Total_Amount'] = fact_sales['Quantity'] * fact_sales['Unit_Price'] * (1 - fact_sales['Discount_Percent'] / 100.0)

# คัดเลือกเฉพาะ Keys และ Metrics
fact_sales['sale_db_id'] = fact_sales.index + 1
fact_sales = fact_sales[[
    'sale_db_id', 'Sale_ID', 'location_id', 'product_id', 'date_id',
    'Quantity', 'Unit_Price', 'Discount_Percent', 'Total_Amount'
]]

# ==========================================
# Phase 3: LOAD (สร้าง DB และนำข้อมูลลง SQLite)
# ==========================================
print("3. [LOAD] สร้างฐานข้อมูลและบันทึกลง retail_warehouse.db...")
conn = sqlite3.connect('retail_warehouse.db')
cursor = conn.cursor()

# เปิดใช้งาน Foreign Key Constraints
cursor.execute("PRAGMA foreign_keys = ON;")

# ลบตารางเก่าก่อน (กรณีที่เคยรันสคริปต์ไปแล้ว)
cursor.execute("DROP TABLE IF EXISTS fact_sales;")
cursor.execute("DROP TABLE IF EXISTS dim_location;")
cursor.execute("DROP TABLE IF EXISTS dim_product;")
cursor.execute("DROP TABLE IF EXISTS dim_date;")

# สร้างตาราง Dimension Tables ใน SQLite
cursor.execute('''
CREATE TABLE dim_location (
    location_id INTEGER PRIMARY KEY,
    Store_Code TEXT,
    Branch TEXT,
    Province TEXT,
    Region TEXT
)
''')

cursor.execute('''
CREATE TABLE dim_product (
    product_id INTEGER PRIMARY KEY,
    Product_Name TEXT,
    Category TEXT
)
''')

cursor.execute('''
CREATE TABLE dim_date (
    date_id INTEGER PRIMARY KEY,
    Date TEXT,
    Year INTEGER,
    Month INTEGER,
    Day INTEGER
)
''')

# สร้าง Fact Table ใน SQLite พร้อมผูก Foreign Keys
cursor.execute('''
CREATE TABLE fact_sales (
    sale_db_id INTEGER PRIMARY KEY,
    Sale_ID TEXT,
    location_id INTEGER,
    product_id INTEGER,
    date_id INTEGER,
    Quantity INTEGER,
    Unit_Price REAL,
    Discount_Percent REAL,
    Total_Amount REAL,
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
)
''')
conn.commit()

# โหลดข้อมูลลงตารางที่มีอยู่แล้วด้วย if_exists='append' (เพื่อรักษา FK Constraints)
dim_location.to_sql('dim_location', conn, if_exists='append', index=False)
dim_product.to_sql('dim_product', conn, if_exists='append', index=False)
dim_date.to_sql('dim_date', conn, if_exists='append', index=False)
fact_sales.to_sql('fact_sales', conn, if_exists='append', index=False)

print("ETL Pipeline Completed Successfully!")

# ==========================================
# Verification: ทดสอบคิวรีข้อมูลใน Warehouse
# ==========================================
print("\n--- [VERIFICATION] สรุปยอดขายแยกตามสาขา (Top 5) ---")
test_query = '''
SELECT 
    l.Branch, 
    l.Province,
    SUM(f.Total_Amount) AS Total_Sales
FROM fact_sales f
JOIN dim_location l ON f.location_id = l.location_id
GROUP BY l.location_id
ORDER BY Total_Sales DESC
LIMIT 5;
'''
print(pd.read_sql_query(test_query, conn))

conn.close()