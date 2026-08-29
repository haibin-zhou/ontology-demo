-- S7 适配：补毛利率字段 + GMV 视图（本体要 gmv30d，库里只有件数）
ALTER TABLE sku ADD COLUMN IF NOT EXISTS gross_margin DECIMAL(4,2);
UPDATE sku SET gross_margin = 0.22 WHERE id = 1;
UPDATE sku SET gross_margin = 0.18 WHERE id = 2;
UPDATE sku SET gross_margin = 0.10 WHERE id = 3;
UPDATE sku SET gross_margin = 0.31 WHERE id = 4;
UPDATE sku SET gross_margin = 0.25 WHERE id = 5;
UPDATE sku SET gross_margin = 0.20 WHERE id = 6;
UPDATE sku SET gross_margin = 0.19 WHERE id = 7;
UPDATE sku SET gross_margin = 0.12 WHERE id = 8;

-- GMV 视图：动销口径 = 近30天销量 × 现价（S3 裁决的 GMV 口径在此落地）
CREATE OR REPLACE VIEW sku_v AS
SELECT s.*, s.sales_30d * s.price AS gmv_30d FROM sku s;
