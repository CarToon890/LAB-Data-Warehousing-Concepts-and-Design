# Omnichannel Retail ETL Pipeline

This repository contains the ETL pipeline for processing Omnichannel Retail orders into a Star Schema Data Warehouse.

## Prerequisites & Installation

To run this project, you need Python and a few dependencies. 
If you are using the `.venv` provided in this folder:
```bash
source .venv/bin/activate
pip install pandas openpyxl jupyter
```

## How to Run

1. Open the `pipeline.ipynb` in VSCode or Jupyter Notebook.
2. Select your Python kernel (e.g., the `.venv` in this folder).
3. Run all cells sequentially.
   
The pipeline will execute 4 test runs automatically:
- **Run 1:** Load `orders_batch_1`
- **Run 2:** Re-run `orders_batch_1` (Idempotency check - 0 rows will be inserted)
- **Run 3:** Load `orders_batch_2`
- **Run 4:** Load `orders_batch_3`

## Generated Outputs

After running the pipeline, the following files will be created/updated:
- `retail_dw.db`: SQLite database containing the data warehouse.
- `quarantine.csv`: Invalid records that failed data quality checks.
- Execution logs will be appended to the `pipeline_run_log` table inside the database.

---

## Star Schema Design

The Data Warehouse uses a Star Schema with 1 Fact table and 3 Dimension tables:

- **fact_sales**: The central fact table storing transaction details (Grain: one valid purchased item per order).
  - Contains foreign keys: `date_key`, `customer_key`, `product_key`.
  - Measures: `quantity`, `unit_price`, `discount_pct`, `gross_amount`, `net_amount`.
  - Degenerate dimensions: `payment_method`, `sales_channel`, `order_id`.
- **dim_customer**: Dimension storing customer details (`customer_name`, `province`, `segment`).
- **dim_product**: Dimension storing product details (`product_name`, `category`).
- **dim_date**: Dimension storing date hierarchy (`day`, `month`, `quarter`, `year`).

---

## Reflection

**Q: เหตุใด Availability จึงมักสำคัญกว่า Strictness ใน Production Pipeline?**

**A:** ใน Production Pipeline การทำระบบให้มี Availability สูงสำคัญกว่า Strictness (ความเข้มงวด) เพราะธุรกิจต้องอาศัยข้อมูลในการตัดสินใจแบบต่อเนื่อง หากระบบหยุดทำงาน (Fail-stop) เพียงเพราะข้อมูลไม่กี่แถวมีปัญหา (Strictness สูงเกินไป) จะทำให้ข้อมูลที่เหลือทั้งหมดล่าช้าและส่งผลกระทบเป็นวงกว้าง ดังนั้นแนวทางปฏิบัติที่ดีกว่าคือการปล่อยให้ข้อมูลส่วนใหญ่ที่ถูกต้องไหลเข้าสู่ระบบได้ตามปกติ (Availability) แล้วใช้หลักการ Quarantine เพื่อคัดกรองเฉพาะข้อมูลที่ผิดปกติแยกออกมารอการตรวจสอบหรือแก้ไขภายหลัง ซึ่งช่วยให้ระบบภาพรวมไม่หยุดชะงักและธุรกิจดำเนินการต่อไปได้ครับ
