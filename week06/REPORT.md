# ETL Lab Report

Student ID: 67160378
Name: สุรชัช ศาลาน้อย

## 1. Data Quality Problems Found

- `customers.csv`: มี `customer_id` ซ้ำ (C004, C009 ซ้ำท้ายไฟล์) จำนวน 2 แถว
- `customers.csv`: ค่า `province` เขียนไม่เป็นมาตรฐาน (ตัวพิมพ์เล็ก/ใหญ่ปนกัน เช่น `BKK`, `bangkok`, `CHONBURI`, `chon buri`, และภาษาไทย เช่น `ชลบุรี`, `กรุงเทพฯ`, `จันทบุรี`, `ระยอง`)
- `customers.csv`: มีค่า `province` และ `email` ว่างเปล่าในบางแถว (เช่น C006 ไม่มี email, C013 ไม่มี province)
- `orders.csv`: มี `order_id` ซ้ำ 3 คู่ (O0011, O0041, O0101)
- `orders.csv`: `order_date` มีรูปแบบวันที่ไม่เหมือนกันในไฟล์เดียว (`2026-08-01`, `2026/08/02`, `01/08/2026`, `03-Aug-2026`) และมีค่าที่ไม่ใช่วันที่เลย (`not-a-date`)
- `orders.csv`: `status` ตัวพิมพ์ไม่สม่ำเสมอ (`PAID` ปนกับ `paid`)
- `orders.csv`: มีค่าที่ผิดกฎธุรกิจ เช่น `qty` ติดลบ, `unit_price` ติดลบ, `discount_pct` เกิน 100%
- `products.json`: เป็น nested JSON (`category.name`, `pricing.price`) ต้อง flatten ก่อนใช้งาน
- `products.json`: มีราคาที่เก็บเป็น string พร้อม comma คั่นหลักพัน (`"1,299.00"`) แทนที่จะเป็นตัวเลข
- `products.json`: มี `category.name` เป็น `null` ในบางสินค้า (P009)

## 2. Cleaning / Transformation Rules

- Customers: `drop_duplicates(subset="customer_id", keep="first")` เพื่อลบ id ซ้ำ; ทำ `province` ให้เป็นมาตรฐานด้วย dictionary mapping (`PROVINCE_MAP` ใน `config.py`) โดย lower + strip ค่าก่อนเทียบ ค่าที่หาไม่เจอ map จะ title-case ไว้แทน; เติมค่า `email`/`province` ที่ว่างเป็น `"Unknown"`
- Products: ใช้ `pd.json_normalize()` ตอน extract เพื่อ flatten `category.name` → `category`, `pricing.price` → `price`; แปลง `price` เป็นตัวเลขด้วยการลบ comma ออกก่อนแล้วค่อย `pd.to_numeric(errors="coerce")`; เติม `category` ที่หายไปเป็น `"Unknown"`
- Orders: `drop_duplicates(subset="order_id", keep="first")` เพื่อลบ order ซ้ำ; parse `order_date` ด้วยการลองหลาย format ตามลำดับ (`%Y-%m-%d`, `%Y/%m/%d`, `%d/%m/%Y`, `%d-%b-%Y`) ค่าที่ parse ไม่ได้ = `NaT`; ทำ `status` เป็น lowercase ด้วย `.str.lower()`
- Reject rule: แถวที่ `qty <= 0` หรือ `unit_price <= 0` หรือ `discount_pct` นอกช่วง [0,100] หรือ `order_date` เป็น `NaT` จะถูกแยกไปที่ `rejects` พร้อมเหตุผล ไม่ถูกลบทิ้งเงียบ ๆ
- Merge: กรองเฉพาะ order ที่ `status` เป็น `paid`/`completed`, join กับ `customers`/`products` ผ่าน key; แถวที่ `customer_id`/`product_id` ไม่พบใน master จะถูกย้ายไป `rejects` เช่นกัน
- คำนวณ `gross_amount = qty * unit_price`, `discount_amount = gross_amount * discount_pct / 100`, `sales_amount = gross_amount - discount_amount`

## 3. Rejected Records

จำนวน: 4 รายการ (ดูรายละเอียดใน `output/rejects.csv`)

เหตุผลหลัก:
- O0007: `qty = -2` (ติดลบ)
- O0021: `discount_pct = 150` (เกิน 100%)
- O0034: `order_date` เป็น `not-a-date`
- O0091: `unit_price = -100.0` (ติดลบ)

(ไม่มีรายการที่ถูก reject จากปัญหา customer/product ไม่พบใน master — ทุก order ที่เหลืออ้างอิง customer_id/product_id ที่มีอยู่จริง)

## 4. ETL Validation

- Valid transformed rows: 100
- Warehouse rows: 100
- Duplicate order_id: 0
- Source total sales: 192074.66
- Warehouse total sales: 192074.66
- Validation status: PASS

## 5. Idempotency Test

จำนวน fact_sales หลัง run ครั้งที่ 1: 100

จำนวน fact_sales หลัง run ครั้งที่ 2: 100

อธิบายผล: จำนวนแถวใน `fact_sales` ไม่เพิ่มขึ้นเมื่อรัน pipeline ซ้ำ เพราะตาราง `fact_sales` กำหนดให้ `order_id` เป็น `PRIMARY KEY` (UNIQUE) และ `load_data()` ใช้คำสั่ง `INSERT OR IGNORE` ซึ่งจะข้ามแถวที่ `order_id` มีอยู่แล้วในตารางแทนที่จะ insert ซ้ำ ทำให้ pipeline สามารถ rerun ได้อย่างปลอดภัย (idempotent) โดยไม่เกิดข้อมูลซ้ำ
