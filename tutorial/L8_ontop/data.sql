INSERT INTO category VALUES (1, '运动户外', NULL), (2, '跑步装备', 1), (3, '跑步鞋', 2);
INSERT INTO brand VALUES (1, 'StrideMax', '美国'), (2, 'PaceFox', '中国');
INSERT INTO merchant VALUES (1, 'Alpha旗舰店'), (2, 'Beta专营店');
INSERT INTO brand_authorization VALUES
  (1, 1, 1, DATE '2027-06-30'),
  (2, 2, 2, DATE '2026-09-10');
INSERT INTO product VALUES
  (1, '闪电跑鞋', 1), (2, '清风跑鞋', 2), (3, '竞速碳板', 1);
INSERT INTO sku VALUES
  (101, 1, 3, 1, 499.00, 120, 20, 459.00, DATE '2026-05-11'),
  (102, 2, 3, 2, 299.00, 45,  30, 279.00, DATE '2025-11-02'),
  (103, 3, 3, 1, 899.00, 260, 15, 869.00, DATE '2026-08-10');
