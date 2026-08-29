-- 与 data/catalog.ttl 完全对齐的全量数据
INSERT INTO category VALUES (1, '运动户外', NULL), (2, '跑步装备', 1), (3, '跑步鞋', 2);

INSERT INTO brand VALUES (1, 'StrideMax', '美国'), (2, 'PaceFox', '中国');

INSERT INTO merchant VALUES (1, 'Alpha旗舰店'), (2, 'Beta专营店');

-- auth_alpha_stride / auth_beta_pace（注意：beta 的授权 2026-09-10 到期 → CQ4 预警对象）
INSERT INTO brand_authorization VALUES
  (1, 1, 1, DATE '2027-06-30'),
  (2, 2, 2, DATE '2026-09-10');

-- p7 在图谱里是"既在售又下架"的矛盾数据；关系库的唯一约束让这种矛盾根本无法存在
-- （这就是阻抗失配的教学点：矛盾只能出现在图谱这种开放世界载体里）
INSERT INTO product VALUES
  (1, '闪电跑鞋SPU', 1, 'ACTIVE'),
  (2, '清风跑鞋SPU', 2, 'ACTIVE'),
  (3, '疾风跑鞋SPU', 1, 'ACTIVE'),
  (4, '幻影竞速SPU', 2, 'ACTIVE'),
  (5, '晨曦跑鞋SPU', 1, 'ACTIVE'),
  (6, '赤兔跑鞋SPU', 2, 'ACTIVE'),
  (7, '磐石跑鞋SPU', 1, 'ACTIVE'),
  (8, '孤影跑鞋SPU', 2, 'ACTIVE');

-- 与 catalog.ttl 的 sku1~sku8 逐字段对齐（sku5 故意 NULL category_id 保留脏数据）
INSERT INTO sku VALUES
  (1, 1, 3,    1, 499.00, 120, 20,  459.00, DATE '2026-05-11'),
  (2, 2, 3,    2, 299.00, 5,   95,  279.00, DATE '2025-11-02'),
  (3, 3, 3,    1, 399.00, 80,  30,  379.00, DATE '2026-06-20'),
  (4, 4, 3,    2, 469.00, 260, 15,  439.00, DATE '2026-08-10'),
  (5, 5, NULL, 1, 359.00, 45,  40,  349.00, DATE '2026-07-01'),
  (6, 6, 3,    2, 329.00, 70,  25,  319.00, DATE '2026-04-15'),
  (7, 7, 3,    1, 259.00, 60,  50,  249.00, DATE '2026-03-08'),
  (8, 8, 3,    2, 199.00, 3,   120, 189.00, DATE '2025-09-20');

-- cert_q1 / cert_q2
INSERT INTO certification VALUES
  (1, '质检报告', DATE '2027-03-01'),
  (2, '质检报告', DATE '2026-12-31');

-- sku6 故意不挂任何资质（脏数据保留）
INSERT INTO sku_certification VALUES
  (1, 1), (2, 2), (3, 1), (4, 2), (8, 2);

-- enr1 合规（449 ≤ 459）；enr2 击穿价保（449 > 439）；enr3 报名的 sku6 无资质
INSERT INTO promo_enrollment VALUES
  (1, '618大促', 1, 449.00),
  (2, '618大促', 4, 449.00),
  (3, '618大促', 6, 309.00);
