# สรุปวิธีทำ Lab: Mini ETL Pipeline with Python (week06)

โน้ตนี้สรุปแนวคิดและขั้นตอนการทำ Lab ไว้อ่านทบทวนก่อนสอบ ไม่ใช่ตัวส่งงาน (ไฟล์ที่ต้องส่งคือ `REPORT.md` + โค้ดใน `src/`)

## ภาพรวมโจทย์

ต้องสร้าง ETL pipeline ครบ 4 ขั้นตอน: **Extract → Transform → Load → Validate**
โครงสร้างไฟล์หลัก:

```
week06/
├── src/
│   ├── config.py     # path ต่าง ๆ + PROVINCE_MAP
│   ├── extract.py     # PART 1
│   ├── transform.py   # PART 2 (คะแนนเยอะสุด 40)
│   ├── load.py         # PART 3
│   ├── validate.py     # PART 4
│   └── main.py          # เรียกทั้ง pipeline ตามลำดับ
├── data/
│   ├── raw/              # customers.csv, orders.csv, products.json
│   ├── source_db/        # store.db (SQLite ต้นทาง)
│   └── warehouse/        # warehouse.db (ผลลัพธ์ปลายทาง)
├── output/               # rejects.csv, validation.json
└── logs/                 # etl.log
```

รันด้วยคำสั่ง: `python -m src.main` (ต้องรันจากโฟลเดอร์ `week06/` เพราะใช้ relative import `from .config import ...`)

---

## PART 1 — Extract (20 คะแนน)

**หลักการ**: อ่านข้อมูลจากแหล่งที่ต่างชนิดกัน (CSV, JSON ซ้อน, SQLite) มารวมในโครงสร้างเดียว

- CSV ธรรมดา → `pd.read_csv(path)`
- JSON ที่มีโครงสร้างซ้อน (nested) เช่น `{"category": {"name": "Food"}}` → ห้ามอ่านตรง ๆ ด้วย `pd.read_json` เพราะจะได้ column เป็น dict ต้องใช้ **`pd.json_normalize(data)`** ซึ่งจะ "แตก" key ซ้อนออกมาเป็น column แบบ `category.name`, `pricing.price` โดยอัตโนมัติ (ใช้ `.` คั่นระดับ)
- ตารางใน SQLite → เปิด connection ด้วย `sqlite3.connect(path)` แล้ว `pd.read_sql_query("SELECT * FROM stores", conn)`

**คีย์สำคัญ**: return เป็น dict ของ DataFrame `{"customers":..., "orders":..., "products":..., "stores":...}` เพื่อให้ step ถัดไปเรียกใช้ง่าย และควร print shape/columns ออกมาดูก่อนเสมอ (checkpoint) — เป็นนิสัยที่ดีเวลาทำ data pipeline จริง เพราะช่วยจับปัญหาตั้งแต่ต้นทาง

---

## PART 2 — Transform (40 คะแนน, เยอะสุด)

นี่คือหัวใจของ Lab เพราะข้อมูลจริงมักไม่สะอาด ต้องจัดการปัญหาหลายแบบพร้อมกัน

### 2.1 Customers
- **Duplicate key**: `df.drop_duplicates(subset="customer_id", keep="first")` — เก็บแถวแรกที่เจอ ทิ้งที่เหลือ
- **Standardize province**: ข้อมูลจริงมักเขียนไม่ตรงกัน (ตัวพิมพ์ใหญ่/เล็ก, ภาษาไทย/อังกฤษ, ตัวย่อ) วิธีที่ทำงานได้ดีคือสร้าง **mapping dictionary** (`PROVINCE_MAP`) โดย key เป็นตัวพิมพ์เล็กทั้งหมด แล้วก่อน lookup ให้ `.strip().lower()` ค่าที่จะเทียบเสมอ ค่าที่หาไม่เจอใน map ให้ fallback เป็น `.title()` แทนที่จะพัง
- **Missing values**: เช็คด้วย `pd.isna()` หรือค่าที่เป็น string ว่าง `""` แล้ว fill เป็นค่ากลาง เช่น `"Unknown"` — หลักการคือ **ห้ามปล่อยว่างเข้า data warehouse** เพราะจะ query/join ยากภายหลัง

### 2.2 Products
- Flatten ทำตั้งแต่ extract แล้ว (`json_normalize`) แต่ transform ต้อง **rename column** ให้ใช้ง่าย: `category.name → category`, `pricing.price → price` ด้วย `.rename(columns={...})`
- **Type casting ปัญหาคลาสสิก**: ราคาบางตัวเก็บเป็น string ที่มี comma คั่นหลักพัน เช่น `"1,299.00"` ถ้า `pd.to_numeric` ตรง ๆ จะ error/กลายเป็น NaN ต้อง **`.str.replace(",", "")` ก่อน** แล้วค่อย `pd.to_numeric(..., errors="coerce")` (coerce = แปลงไม่ได้ให้เป็น NaN แทนที่จะ error)
- **Missing category** (`null` ใน JSON) → fill เป็น `"Unknown"`

### 2.3 Orders — ส่วนที่ซับซ้อนสุด
- **Duplicate order_id**: `drop_duplicates` เหมือน customers
- **Mixed date formats**: ข้อมูลจริงมักมีวันที่หลายรูปแบบปนกันในคอลัมน์เดียว (`2026-08-01`, `2026/08/02`, `01/08/2026`, `03-Aug-2026`, และค่าขยะ `not-a-date`) วิธีแก้คือเขียนฟังก์ชัน parser ที่ **ลอง format ทีละแบบ** ด้วย `pd.to_datetime(text, format=fmt)` ใน try/except วนจนกว่าจะสำเร็จ ถ้าไม่มี format ไหน match เลยให้ return `pd.NaT` (Not-a-Time = ค่า null สำหรับ datetime) — อย่าใช้ `pd.to_datetime(..., errors="coerce")` เฉย ๆ เพราะ pandas เดา format อัตโนมัติได้ไม่แม่นกับข้อมูลกำกวมแบบ `01/08/2026` (วันที่ 1 เดือน 8 หรือเดือน 1 วันที่ 8?)
- **Normalize status**: `.str.strip().str.lower()` ให้ `PAID` และ `paid` กลายเป็นค่าเดียวกัน
- **Reject rule (สำคัญมาก)**: แถวที่เข้าเงื่อนไขต่อไปนี้ "ห้ามลบทิ้งเงียบ ๆ" ต้องแยกไปเก็บใน `rejects` DataFrame พร้อมเหตุผล:
  - `qty <= 0`
  - `unit_price <= 0`
  - `discount_pct < 0` หรือ `> 100`
  - `order_date` parse ไม่ได้ (เป็น `NaT`)

  ใช้ boolean mask รวมเงื่อนไขด้วย `|` (or) แล้วแยก DataFrame เป็น 2 ส่วนด้วย mask กับ `~mask`

### 2.4 Merge (รวมข้อมูล)
1. กรองเฉพาะ order ที่ `status` เป็น `paid` หรือ `completed` (ตัดพวก `pending`, `cancelled` ทิ้งตั้งแต่ต้น)
2. join กับ `customers` และ `products` ผ่าน key (`customer_id`, `product_id`)
3. **ถ้า customer_id หรือ product_id ไม่มีใน master data** (foreign key ไม่ตรง) → ห้าม join แบบเงียบ ๆ จน record หายไป ต้อง**ย้ายไป reject** เช่นกัน วิธีเช็คง่าย ๆ คือสร้าง `set()` ของ id ที่รู้จัก แล้ว `.isin()` เช็คทีละแถว

### 2.5 คำนวณยอดขาย
```
gross_amount    = qty * unit_price
discount_amount = gross_amount * discount_pct / 100
sales_amount    = gross_amount - discount_amount
```

**หลักคิดสำคัญของ Transform ทั้งหมด**: "ข้อมูลผิดไม่ควรหายเงียบ ๆ" — ทุกแถวที่ไม่ผ่านกฎต้องอธิบายได้ว่าทำไมถูก reject (เก็บไว้ใน `output/rejects.csv`) เพื่อให้ตรวจสอบย้อนหลังได้ นี่คือหลักการ **data lineage / auditability** ที่สำคัญมากในงาน data warehouse จริง

---

## PART 3 — Load (25 คะแนน)

**หลักการ**: โหลดข้อมูลที่สะอาดแล้วเข้า SQLite warehouse โดยแบ่งเป็น star-schema ง่าย ๆ:
- `dim_customer` (dimension: ข้อมูลลูกค้า)
- `dim_product` (dimension: ข้อมูลสินค้า)
- `fact_sales` (fact table: ยอดขายแต่ละ order — มี foreign key ไปยัง dimension)

**Requirement ที่ตรวจเข้มที่สุดของ Lab นี้คือ Idempotency**: รัน pipeline กี่ครั้งก็ตาม จำนวนแถวใน `fact_sales` ต้องไม่เพิ่ม (ไม่ insert ซ้ำ)

วิธีทำ:
1. สร้างตารางด้วย `order_id TEXT PRIMARY KEY` (และ `customer_id`/`product_id` เป็น PRIMARY KEY ใน dimension ของตัวเอง) — PRIMARY KEY บังคับ UNIQUE โดยอัตโนมัติใน SQLite
2. ตอน insert ใช้ **`INSERT OR IGNORE INTO ...`** แทน `INSERT INTO` ธรรมดา — ถ้าค่า key ซ้ำกับที่มีอยู่แล้ว SQLite จะข้ามแถวนั้นไปเฉย ๆ แทนที่จะ error หรือ insert ซ้ำ
3. ใช้ `cursor.executemany(sql, list_of_tuples)` แทนการ insert ทีละแถวในลูป Python — เร็วกว่ามาก

นี่คือ pattern พื้นฐานของการทำ **idempotent load** ใน ETL/ELT จริง ๆ (ทางเลือกอื่นคือ upsert ด้วย `INSERT ... ON CONFLICT DO UPDATE` ถ้าต้องการอัปเดตข้อมูลเก่าด้วย ไม่ใช่แค่ข้าม)

---

## PART 4 — Validate (15 คะแนน)

**หลักการ**: "Pipeline ที่รันจบไม่ได้แปลว่าถูกต้อง" ต้องมีตัวเลขพิสูจน์ว่าข้อมูลที่ transform แล้ว กับข้อมูลที่อยู่ใน warehouse จริง ตรงกัน

ต้องเช็คอย่างน้อย:
- จำนวนแถวที่ valid จากฝั่ง source (หลัง transform) เทียบกับจำนวนแถวใน warehouse
- นับ duplicate order_id ใน warehouse (ควรเป็น 0 เสมอถ้า schema/insert ถูกต้อง) — ใช้ `GROUP BY order_id HAVING COUNT(*) > 1`
- ผลรวม `sales_amount` สองฝั่งต้องตรงกัน (เทียบกันตรง ๆ อาจมี floating point คลาดเคลื่อนเล็กน้อย ควร `round()` หรือเทียบด้วย tolerance เช่น `abs(a-b) < 0.01`)
- สรุปเป็น `status: PASS/FAIL`

Output เป็น `validation.json` แบบมีโครงสร้างชัดเจน อ่านง่าย ใช้เป็นหลักฐานส่งงานได้

---

## ประเด็นที่มักออกสอบ / ต้องเข้าใจให้ลึก

1. **ทำไมต้องใช้ `pd.json_normalize()` แทน `pd.read_json()`** — เพราะ JSON มี nested object (`category.name`) ถ้าไม่ flatten จะได้ column ที่เป็น dict ใช้งานต่อยาก
2. **ทำไม parse date ต้องลองหลาย format** — เพราะ `pd.to_datetime()` แบบ auto-detect ไม่แม่นยำเมื่อ format กำกวม (เช่น `01/08/2026` ตีความได้สองแบบ) การกำหนด format ชัดเจนทีละแบบปลอดภัยกว่า
3. **ความหมายของ Idempotent pipeline** — รันซ้ำได้โดยผลลัพธ์เหมือนเดิม ไม่สร้างข้อมูลซ้ำ เป็นคุณสมบัติที่ ETL pipeline ในโลกจริงต้องมี (เพราะ pipeline อาจถูกรันซ้ำเวลา retry หลัง error)
4. **ทำไมต้องมี rejects.csv แยกออกมา** — หลักการ data quality / lineage: ข้อมูลที่ไม่ผ่านกฎต้องตรวจสอบย้อนกลับได้ ไม่ใช่หายไปเฉย ๆ
5. **โครงสร้าง star schema แบบง่าย**: dimension tables (`dim_customer`, `dim_product`) เก็บ attribute อธิบาย, fact table (`fact_sales`) เก็บตัวเลข/measure ที่อ้างอิงถึง dimension ผ่าน key

---

## ผลลัพธ์จากการรันจริงของงานนี้ (อ้างอิง)

- Raw orders: 183 แถว → ลบ duplicate order_id (3 คู่) → 180 order ไม่ซ้ำ
- Raw customers: 62 แถว → ลบ duplicate customer_id (2 คู่) → 60 ลูกค้าไม่ซ้ำ
- Reject จากค่าผิดกฎ (qty/price/discount/date): 4 รายการ
- Reject จาก customer/product ไม่พบใน master: 0 รายการ
- Order ที่ผ่านทุกเงื่อนไข และ status เป็น paid/completed: 100 แถว
- ยอดขายรวม (source = warehouse): 192,074.66
- รัน pipeline ซ้ำ 2 ครั้ง → `fact_sales` ยังคงมี 100 แถวเท่าเดิม (validation status: PASS)
